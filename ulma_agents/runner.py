import asyncio
from unittest import runner
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from .front import front_agent
from google.genai import types as genai_types
import uuid

class agent_sessions:
    def __init__(self,agent):
        self.events=[]
        self.agent=agent
        self.in_session=False
        self.session_id=None
        self.session_service = None
        self.runner = None
        return
    
    async def get_session_id(self):
        if not(self.in_session):
            self.session_id=f"ulma_{uuid.uuid4().hex[:8]}"
            self.in_session=True
            self.session_service = InMemorySessionService()
            self.runner = await self.run()
        return self.session_id
    
    def _get_session_events(self):
        return self.events
    
    async def run(self):
        """Runs the agent"""
        await self.session_service.create_session(
            app_name="app", user_id="admin_user", session_id=self.get_session_id()
        )
        runner = Runner(
            agent=front_agent, app_name="app", session_service=self.session_service
        )
        return runner
    
    async def execute(self, input_text: str):
        """Executes the agent with the given input text"""
        session_id = self.get_session_id()
        if self.in_session:            
            response = await self.runner.run_async(
                session_id=session_id,new_message=input_text
            )
            self.events.append(response)
        return response


