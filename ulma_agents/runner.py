from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.plugins.logging_plugin import (
    LoggingPlugin,
)
from google.genai import types
import uuid
import inspect
import os
import asyncio
import datetime
import time
from .tools import load_session_memory, save_session_memory, read_teams_reply

class agent_sessions:
    def __init__(self,agent):
        self.events=[]
        self.agent=agent
        self.session_id=os.getenv("ULMA_SESSION_ID", f"ulma_{uuid.uuid4().hex[:8]}")
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent, app_name="app", session_service=self.session_service, plugins=[LoggingPlugin()]
        )
        self._session_ready = False
        return

    async def _fetch_session(self):
        """
        Retrieve the underlying session object from the session service (sync or async).
        """
        getter = getattr(self.session_service, "get_session", None)
        if not getter:
            return None
        try:
            result = getter(app_name="app", user_id="user", session_id=self.session_id)
        except TypeError:
            try:
                result = getter(self.session_id)
            except Exception:
                return None
        except Exception:
            return None

        if inspect.isawaitable(result):
            try:
                result = await result
            except Exception:
                return None
        return result

    async def _hydrate_session_state(self):
        """
        Loads persisted session state (if any) into the in-memory session.
        """
        persisted = load_session_memory(self.session_id)
        if not persisted:
            return
        session = await self._fetch_session()
        if session and hasattr(session, "state") and isinstance(session.state, dict):
            session.state.update(persisted)

    async def _persist_session_state(self):
        """
        Persists the current session state to durable storage.
        """
        session = await self._fetch_session()
        state = getattr(session, "state", None) if session else None
        if isinstance(state, dict):
            save_session_memory(self.session_id, state)

    async def _ensure_session(self):
        if self._session_ready:
            return
        await self.session_service.create_session(
            app_name="app", user_id="user", session_id=self.session_id
        )
        await self._hydrate_session_state()
        self._session_ready = True

    def _get_session_events(self):
        return self.events

    def _extract_confirmation(self, event):
        """
        Detect ADK pause requests emitted via tool_context.request_confirmation.
        """
        content = getattr(event, "content", None)
        if not content or not getattr(content, "parts", None):
            return None
        for part in content.parts:
            func_call = getattr(part, "function_call", None)
            if func_call and getattr(func_call, "name", "") == "adk_request_confirmation":
                return {
                    "approval_id": getattr(func_call, "id", None) or getattr(func_call, "call_id", None),
                    "invocation_id": getattr(event, "invocation_id", None),
                }
        return None

    def _get_pending_approval_file(self):
        state = load_session_memory(self.session_id) or {}
        return state.get("APPROVAL_FILENAME")

    def _update_approval_state(self, approved: bool, filename: str):
        state = load_session_memory(self.session_id) or {}
        state["WAITING_FOR_APPROVAL"] = False
        state["APPROVAL_STATUS"] = "APPROVED" if approved else "REJECTED"
        state["APPROVAL_TS"] = datetime.datetime.utcnow().isoformat()
        state["APPROVAL_FILENAME"] = filename
        save_session_memory(self.session_id, state)

    async def _wait_for_file_approval(self, timeout_seconds: int = 300, poll_seconds: int = 5):
        """
        Poll the outgoing approvals folder until an approval/rejection is found.
        """
        filename = self._get_pending_approval_file()
        if not filename:
            return None, "no approval filename found in session state"

        deadline = time.monotonic() + timeout_seconds
        last_reason = ""
        while time.monotonic() < deadline:
            reply = read_teams_reply(filename)
            last_reason = reply.get("reason", "")
            if reply.get("done"):
                decision = reply.get("decision")
                approved = decision == "approved"
                self._update_approval_state(approved, filename)
                return approved, decision
            await asyncio.sleep(poll_seconds)

        return None, last_reason or "timeout waiting for approval reply"

    def _create_approval_response(self, approval_info, approved: bool):
        confirmation_response = types.FunctionResponse(
            id=approval_info.get("approval_id"),
            name="adk_request_confirmation",
            response={"confirmed": bool(approved)},
        )
        return types.Content(role="user", parts=[types.Part(function_response=confirmation_response)])

    def _text_event(self, text: str):
        """
        Create a lightweight event with text so the CLI printer can surface status updates.
        """
        class _Evt:
            def __init__(self, content):
                self.content = content
                self.invocation_id = None
        return _Evt(types.Content(role="assistant", parts=[types.Part(text=text)]))
    
    async def execute(self, input_text: str):
        """Executes the agent with the given input text"""
        await self._ensure_session()
        response = self.runner.run_async(
            session_id=self.session_id, new_message=input_text, user_id="user"
        )
        self.events.append(response)

        async def _stream():
            try:
                async for event in response:
                    approval_info = self._extract_confirmation(event)
                    if approval_info:
                        # Pause here until the human reply is found in the outgoing folder
                        yield self._text_event("High-risk operation paused: waiting for approval reply in logs/teams/outgoing...")
                        approved, decision = await self._wait_for_file_approval()
                        if approved is None:
                            yield self._text_event(f"Approval still pending ({decision}). Please add the reply file then ask to 'check again'.")
                            break

                        # Resume the same invocation with the human decision
                        approval_response = self._create_approval_response(approval_info, approved)
                        resumed = self.runner.run_async(
                            session_id=self.session_id,
                            new_message=approval_response,
                            user_id="user",
                            invocation_id=approval_info.get("invocation_id"),
                        )
                        async for resumed_event in resumed:
                            yield resumed_event
                        break

                    yield event
            finally:
                try:
                    await self._persist_session_state()
                except Exception as exc:
                    print(f"[memory] failed to persist after run: {exc}")

        return _stream()


