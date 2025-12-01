from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from ulma_agents.config import config
from .remote_client_tool import talk_to_branch_b

# This agent runs in HQ (Client side)
# It acts as a proxy, forwarding requests to the real Branch B agent via HTTP.
remote_branch_agent = Agent(
    name="branch_b_agent", # Keep same name for supervisor compatibility
    model=config.remote_agent,
    description="Proxy agent for Branch B. Forwards all requests to the remote server.",
    instruction="""
    You are a proxy for the Remote Branch B Agent.
    
    Your ONLY job is to forward the user's message to the remote server using the `talk_to_branch_b` tool.
    
    1. Receive message from Supervisor.
    2. Call `talk_to_branch_b(message)`.
    3. Return the EXACT response you get from the tool.
    """,
    tools=[FunctionTool(talk_to_branch_b)],
    output_key="branch_b_proxy_response"
)
