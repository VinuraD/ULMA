from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ..config import config
from ..tools import save_step_status

teams_agent = Agent(
    name="teams_agent",
    model=config.teams_agent,
    description="Stub Teams/notification agent that records status.",
    instruction="""
    You are the Teams/notification agent stub. Summarize the user lifecycle
    update you would post to the collaboration tool. When done, call
    save_step_status with step="teams" and done=True. If you cannot post,
    call it with done=False and explain.
    """,
    tools=[FunctionTool(save_step_status)],
    output_key="teams_updates",
)
