import os
import glob
import datetime
import sqlite3
from typing import List, Dict, Any
from pypdf import PdfReader
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv
from .create_db import get_db_path


def save_flow_log(flow_updates:str,filename:str) -> Dict:
    '''writes and saves exection updates to a log file
    
    Args:
        flow_updates:each update in the flow.
        filename:the filename (with extension) to be written.
    '''
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    path=os.path.join(root_dir,'logs')
    os.makedirs(path, exist_ok=True)
    full_path=os.path.join(path,filename)
    if not os.path.exists(full_path):
        with open(full_path,'w+') as f:
            f.write('Log of the tool calls....Date:{}\n'.format(datetime.datetime.now()))

    with open(full_path,'a') as f:
        f.write(flow_updates)

    return {'log_status':'saved','file':full_path}

def read_doc(filename:str) -> Dict:
    '''reads the given filename and returns its content as a string object
    
    Args: 
        filename: the filename (with or without .pdf extension) to be read from.
    '''
    base_dir=os.path.dirname(__file__)
    policy_dir=os.path.join(base_dir,'policy')
    base_name=os.path.splitext(filename)[0]
    pdf_path=os.path.join(policy_dir,base_name+'.pdf')
    if not os.path.exists(pdf_path):
        return {'text':''}
    reader = PdfReader(pdf_path)
    text_parts=[]
    for page in reader.pages:
        text_parts.append(page.extract_text() or "")
    return {'text':"\n".join(text_parts)}
    
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
    db_path=get_db_path()
    if not os.path.exists(db_path):
        sqlite3.connect(db_path).close()
    conf=[McpToolset(
            connection_params=StdioConnectionParams(
                server_params=StdioServerParameters(
                    command="npx",
                    args=[
                        "-y",
                        "@modelcontextprotocol/server-sqlite",
                        db_path,
                    ],
                )
            ),
            
        )]

    return conf
    


