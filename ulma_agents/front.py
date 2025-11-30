'''
This agent is the user-facing agent. Takes requests (e.g., email/ticket), parses it and also interacts with the user.
'''


from .supervisor import supervisor_agent
import datetime
from google.adk.agents import Agent
from google.adk.tools import FunctionTool
from .config import config
import vertexai
import os
import dotenv

dotenv.load_dotenv()

def _init_client():
    """Initialize Vertex or fall back to API-key path if env vars are missing."""
    project = os.getenv("GOOGLE_CLOUD_PROJECT")
    location = os.getenv("GOOGLE_CLOUD_LOCATION")
    api_key = os.getenv("GOOGLE_API_KEY")
    use_vertex = os.getenv("GOOGLE_GENAI_USE_VERTEXAI", "").lower()

    if use_vertex != "false" and project and location:
        vertexai.init(project=project, location=location)
        return

    if api_key:
        os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "FALSE")
        return

    raise RuntimeError(
        "Missing configuration: set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION "
        "for Vertex, or provide GOOGLE_API_KEY for the API-key path."
    )

_init_client()

agent=Agent(
    name = 'user_facing_agent',
    model=config.front_agent,
    description='The user facing agent. Takes requests from the user and parses. Updates the user at the end of the operations.',
    instruction='''
    You are the front face of a user lice cycle management system. Your primary function is to take user requests in, parse them and
    to be forwarded to the next tool.

    Your workflow is as follows:
    1. **Start:**Ask and take the user input in.
    2. **Parse:** Remove any erroneous words and clearly separate components in the user request to following key fields. If any information is
    not given by the user, set its value to NULL. 
        1. goal - the purpose of the request. e.g., onboarding/offboarding a user (MANDATORY) 
        2. user_name - the user_name mentioned in the request body (MANDATORY)
        3. role - the intended role for the user_name (OPTIONAL)
        4. apps - the apps that should be accessible by the user_name (OPTIONAL)
        5. policy_doc - the poilcy document name mentioned in the request (MANDATORY)
        6. extra - any other information that is not generic or filler words (OPTIONAL)
    3. **Confirmation of information:** Ask the user to confirm the information. Notify the user of any missing value. goal and user_name are MANDATORY. DO NOT continue if any of themy are missing. OPTIONAL keys may have missing values. If user updates with new information, update the current input and continue to the next step.
    4. **Refine:** Ensure that the parsed information from step 2 are correctly formatted as a dictionary. There must be a dictionary per user_name. An example is, {{'user_name':'John Doe','data':{'goal': 'onboarding the user', 'role': 'admin', 'apps':['Adobe Photoshop'],'policy_doc':'document_A.pdf'}}}. 
    6. **Await:** Await for an update from the 'supervisor_agent'. Notify the user that you are waiting for an update.
    7. **Update**: Update the user with the information received from the 'supervisor_agent'. Be clear and concise.
        1. If the 'supervisor_agent' sent a plan to be approved, request the user approval.
        2. If the 'supervisor_agent' asked for missing information, check if it is already provided by the user. If not, request the information from the user.
        3. If the 'supervisor_agent' sent an update of the operation (SUCCESS/FAILURE) notify the user.
    8. **End**: If the user agrees with the update, end the user session with a goodbye message.

    When asked who you are, respond with a brief description of your puprspose - "User-Life Cycle Management:".
    ''',
    sub_agents = [supervisor_agent],
    output_key='parsed_user_request'
)

front_agent = agent
