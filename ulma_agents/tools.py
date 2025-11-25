import os
import glob
import datetime
from typing import List, Dict, Any
from pypdf import PdfReader
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv


def save_flow_log(flow_updates:str,filename:str) -> Dict:
    '''writes and saves exection updates to a log file
    
    Args:
        flow_updates:each update in the flow.
        filename:the filename (with extension) to be written.
    '''
    path='./logs'
    if not (filename in os.listdir(path)):
        with open(filename,'w+') as f:
            f.write('Log of the tool calls....Date:{}'.format(datetime.datetime.now()))

    with open(filename,'a') as f:
        f.write(flow_updates)

    return {'log_status':'saved'}

def read_doc(filename:str) -> Dict:
    '''reads the given filename and returns its content as a string object
    
    Args: 
        filename: the filename (without extension) to be read from.
    '''
    path='./policy'
    if filename in os.listdir(path):
        reader = PdfReader(path+filename+'.pdf')
        page = reader.pages
        return {'text':page}
    else:
        return {'text':''}
    
###Session Context Tools###

def save_step_status(
    tool_context: ToolContext, step: str, done: bool
) -> Dict[str, Any]:
    """
    Tool called by sub-agents to record whether their step succeeded.

    Args:
        step: The step taken by the sub-agent
        done: If the step was successfully completed
    """
    state = tool_context.state  # session state dict
    if step == "policy":
        state["STATE_POLICY_OK"] = done
    elif step == "identity":
        state["STATE_IDENTITY_OK"] = done
    elif step == "teams":
        state["STATE_TEAMS_OK"] = done

    return {"step": step, "done": done}


# This demonstrates how tools can read from session state.
def get_all_steps_status(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Reads state flags and, if ALL are True, escalates to tell LoopAgent to stop
    """
    state = tool_context.state

    policy_ok = bool(state.get("STATE_POLICY_OK", False))
    identity_ok = bool(state.get("STATE_IDENTITY_OK", False))
    teams_ok = bool(state.get("STATE_TEAMS_OK", False))

    all_done = policy_ok and identity_ok and teams_ok

    if all_done:
        print("[checker] all steps succeeded, ending loop")
        tool_context.actions.escalate = True
    else:
        print("[checker] still incomplete, continue loop")

    return {
        "policy_ok": policy_ok,
        "identity_ok": identity_ok,
        "teams_ok": teams_ok,
        "all_ok": all_done,
    }

###MCP tools###
    
def db_tool():
    load_dotenv()
    DATABASE = os.getenv("DATABASE_NAME")
    conf=[McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-sqlite",
                        "local_addb",
                    ],
                )
            ),
            
        )]

    return conf
    


