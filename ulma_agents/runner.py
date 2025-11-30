from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.adk.plugins.logging_plugin import (
    LoggingPlugin,
)
import uuid
import inspect
import os
from .tools import load_session_memory, save_session_memory

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
                    yield event
            finally:
                try:
                    await self._persist_session_state()
                except Exception as exc:
                    print(f"[memory] failed to persist after run: {exc}")

        return _stream()


