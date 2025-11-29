from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
import uuid

class agent_sessions:
    def __init__(self,agent):
        self.events=[]
        self.agent=agent
        self.session_id=f"ulma_{uuid.uuid4().hex[:8]}"
        self.session_service = InMemorySessionService()
        self.runner = Runner(
            agent=self.agent, app_name="app", session_service=self.session_service
        )
        self._session_ready = False
        return

    async def _ensure_session(self):
        if self._session_ready:
            return
        await self.session_service.create_session(
            app_name="app", user_id="admin_user", session_id=self.session_id
        )
        self._session_ready = True

    def _get_session_events(self):
        return self.events
    
    async def execute(self, input_text: str):
        """Executes the agent with the given input text"""
        await self._ensure_session()
        response = await self.runner.run_async(
            session_id=self.session_id, new_message=input_text
        )
        self.events.append(response)
        return response


