import asyncio
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from front import front_agent
from google.genai import types as genai_types
import uuid

class agent_sessions:
    def __init__(self):
        return
    
    @staticmethod
    def get_session_id():
        session_id=f"ulma_{uuid.uuid4().hex[:8]}"
        return session_id
    
    async def run(self):
        """Runs the agent"""
        session_service = InMemorySessionService()
        await session_service.create_session(
            app_name="app", user_id="admin_user", session_id=self.get_session_id()
        )
        runner = Runner(
            agent=front_agent, app_name="app", session_service=session_service
        )



