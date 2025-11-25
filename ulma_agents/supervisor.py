'''
This agent is the user-facing agent. Takes requests (e.g., email/ticket), parses it and also interacts with the user.
'''

import datetime
from google.adk.agents import Agent, LoopAgent
from google.adk.tools import FunctionTool
from .config import config
from .sub_agents.policy_agent import policy_agent
from .tools import save_flow_log, get_all_steps_status,db_tool

agent=Agent(
    name = 'supervisor_agent',
    model=config.supervisor_agent,
    description='The supervisor agent. Takes the output from the front agent and utilize the other subagents and tools to fulfill the user request',
    instruction=f'''
    You are the supervisor/coordinator agent that utilize the given tools to successfully complete the user request received via the user facing agent.

    Your workflow is as follows:
    1. **Start:**Take the input and make sure it is of the form of a dictionary. This is the ground truth that should be used for comparing the success.
    3. **Validate:**Confirm that 'goal','user_name' and 'policy_doc' fields are not NULL or empty. DO NOT continue if they are NULL or empty and send an error message to 'front_agent' tool. 
    2. **Categorize the goal:**Take the value of the field 'goal' from the input and map it to ONLY one of the categories. 
       1. Onboard
       2. Offboard
       3. Access - App
       4. Access - Role
       5. Access - Group
       4. Password
       5. Other
    3. **Detemine information completeness:**Based on the category you obtained in step 2, determine if all the necessary information are present in the input you received from step 1. If anything is missing DO NOT continue and send an error message to 'front_agent' tool.
    4. **Plan**:Based on the category of the goal, multiple steps may be needed to complete the goal. Following is a general plan for any task.
            1. Update the local database by calling 'db_tool' to ensure that correct information about the user state is present.
            2. Based on the category, determine the flow of the tools required. Below is a summary of the capabilities of the relevant tools available to you.
                a. 'policy_agent': provides the policy constraints required for any goal. INPUT: 'policy_doc', OUTPUT: a list of constraints
                b. 'identity_agent': has access to the organization's active directory, and can retrieve information or modify from it. INPUT: a list of constraints, 'user_name','role', etc. OUTPUT: the status of the task (success/failure).
                c. 'teams_agent': has access to organization's Teams app, and it posts logs, updates regarding a user_request. INPUT: the state of the task from 'identity_agent' and other information, OUTPUT: post a detailed log in the Teams app.
                d. 'db_tool': provides the latest state of a 'user_name'. INPUT: 'user_name', OUTPUT: role, access privileges to apps/groups.
                e. 'front_agent': interacts with the user. INPUT: a list of constraints or a request for missing information or a status update. OUTPUT: approval state (APPROVED/NOT APPROVED) or the requested information.
                f. 'save_flow_log': saves the records of the tool call outputs throughout the plan execution.
                d. 'get_all_step_status': you can call this to check if every other tool (identity, teams, policy) did their job correctly. The tool will return boolean flags showing the success of each tool and the whole operation. 
            3. DO NOT execute the plan yet.
    4. **Determine the permissions:** Format your plan of tool calls to a concise list. Determine if human approval is required before continuing with the plan. Send the concise list to 'front_agent' tool. Await for the confirmation from 'front_agent' tool.
    5. **Execute plan:** If the confirmation (APPROVED) is received from the 'front_agent' tool, execute the plan.
    6. **Monitor tools:**Closely monitor the outputs from the tools as you execute the plan'. You can use 'get_all_step_status' tool for this. Create a record of the flow of tool outputs and save it using 'save_flow_log' tool. For the filename, use the format 'user_name__goal.txt'.
    7. **Update**: Determine the state of the execution at the end of the plan (SUCCESS/FAILURE). Send this status to 'front_agent' tool in json format.
    8. **End**: Your workflow ends after the previous step.
    ''',
    sub_agents = [
        # identity_agent,
        # teams_agent,
        policy_agent,
    ],
    # max_iterations=2,
    tools=[FunctionTool(db_tool),
           FunctionTool(save_flow_log),
           FunctionTool(get_all_steps_status)],
    output_key='supervisor_updates'
)

supervisor_agent = agent