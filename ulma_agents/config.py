'''
This holds configurations for all agents including subagents
# To use AI Studio credentials:
# 1. Create a .env file in the /app directory with:
#    GOOGLE_GENAI_USE_VERTEXAI=FALSE
#    GOOGLE_API_KEY=PASTE_YOUR_ACTUAL_API_KEY_HERE
# 2. This will override the default Vertex AI configuration

'''

import os
from dataclasses import dataclass
import google.auth
from google.genai import types


_, project_id = google.auth.default()
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", project_id)
os.environ.setdefault("GOOGLE_CLOUD_LOCATION", "global")
os.environ.setdefault("GOOGLE_GENAI_USE_VERTEXAI", "True")


@dataclass
class ResearchConfiguration:
    """Configuration for research-related models and parameters.

    Attributes:
        critic_model (str): Model for evaluation tasks.
        worker_model (str): Model for working/generation tasks.
        max_search_iterations (int): Maximum search iterations allowed.
    """

    supervisor_agent: str = "gemini-2.5-pro"
    front_agent: str = "gemini-2.5-flash-lite"
    policy_agent: str = "gemini-2.5-flash-lite"
    identity_agent: str = "gemini-2.5-flash"
    teams_agent: str = "gemini-2.5-flash-lite" #should revise
    max_search_iterations: int = 5


config = ResearchConfiguration()

###Configurations for MCP servers###

retry_config = types.HttpRetryOptions(
    attempts=5,  # Maximum retry attempts
    exp_base=7,  # Delay multiplier
    initial_delay=1,
    http_status_codes=[429, 500, 503, 504],  # Retry on these HTTP errors
)
