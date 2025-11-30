import os
import glob
import datetime
import sqlite3
import json
from typing import List, Dict, Any
from pypdf import PdfReader
from google.adk.tools.mcp_tool.mcp_toolset import McpToolset
from google.adk.tools.tool_context import ToolContext
from google.adk.tools.mcp_tool.mcp_session_manager import StdioConnectionParams
from mcp import StdioServerParameters
from dotenv import load_dotenv
from .create_db import (
    get_db_path,
    save_memory_state,
    load_memory_state,
    ensure_memory_table,
)


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

def _json_safe_state(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Converts state into a JSON-safe dict (fallback to str on unsupported types).
    """
    try:
        return json.loads(json.dumps(state, default=str))
    except Exception:
        return {}


def load_session_memory(session_id: str) -> Dict[str, Any]:
    """
    Loads persisted session memory (if any).
    """
    ensure_memory_table()
    return load_memory_state(session_id)


def save_session_memory(session_id: str, state: Dict[str, Any]) -> None:
    """
    Persists the given session state to durable storage.
    """
    ensure_memory_table()
    safe_state = _json_safe_state(state)
    save_memory_state(session_id, safe_state)


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
    elif step == "teams_reporting":
        state["STATE_REPORTING_OK"] = done
    elif step == "remote_delegation":
        state["STATE_REMOTE_OK"] = done
    # Persist updated state for durability across sessions
    session_id = getattr(tool_context, "session_id", None)
    if session_id:
        try:
            save_session_memory(session_id, state)
        except Exception as exc:
            print(f"[memory] failed to persist session state: {exc}")
    return {"step": step, "done": done}


def send_manager_message(message: str) -> Dict[str, Any]:
    """
    Simulates sending a manager summary by writing a timestamped text file; also prints to console.
    
    Args:
        message: The summary text to send.
    """
    now = datetime.datetime.now()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    out_dir = os.path.join(root_dir, "logs", "manager_summaries")
    os.makedirs(out_dir, exist_ok=True)

    filename = f"manager_summary_{stamp}.txt"
    filepath = os.path.join(out_dir, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"Timestamp: {now.isoformat()}\n")
        f.write("Recipient: Manager\n")
        f.write("Content:\n")
        f.write(message.strip() + "\n")

    print(f"\n[Teams Manager DM] (simulated) >>> {message}\n")
    print(f"[Teams Manager DM] Saved summary to {filepath}\n")

    return {
        "status": "sent",
        "recipient": "Manager",
        "content": message,
        "file": filepath,
    }



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

    # Return only JSON-serializable metadata to avoid deepcopy/pickling errors in the ADK
    # pipeline. Returning the McpToolset instance leaks file handles (TextIOWrapper) which
    # breaks Pydantic deep copies.
    return {
        "status": "ready",
        "db_path": db_path,
        "message": "Local SQLite DB ensured; MCP toolset not returned to keep output JSON-safe.",
    }
    


