'''
This agent is the user-facing agent. Takes requests (e.g., email/ticket), parses it and also interacts with the user.
'''

import datetime
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from .config import config
from front import front_agent
from .tools import read_doc, save_step_status




agent=Agent(
    name = 'policy_agent',
    model=config.supervisor_agent,
    description='The policy agent. Takes the goal, poilcy document name, reads and outputs its content as constraints',
    instruction=f'''
    You read policy documents, understands its content in relation to the required goal and provides a set of policy constraints related to the goal.

    Your workflow is as follows:
    1. **Start:**Take the policy document name and use the document_reader tool to extract its content.
    2. **Understand the policies:**The policy document contains different policies and constraints related to user lice cycle management. You must extract the policies that are relevant to the given goal. For example, 'The onboarding user must not have access to application x'.
    3. **Format the constraints:**Format the extracted constraints in the previous step as a concise list of constraints. Make sure there are no conflicting or ambiguous constraints. 
    4. **Set status:** If you successfully extracted the relevant policies, call "save_step_status" tool with step="policy" and done=True. If it failed, call it with done=False.
    5. **End**: Your workflow ends after the previous step.
    '''
    tools=[FunctionTool(read_doc),FunctionTool(save_step_status)],
    output_key='policy_constraints'
)

policy_agent = agent