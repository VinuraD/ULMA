import os
import re
import glob
import datetime
import sqlite3
import json
from typing import List, Dict, Any, Optional
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

### Paths/helpers for simulated Teams messaging ###
def _ensure_teams_dirs() -> Dict[str, str]:
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    base = os.path.join(root_dir, "logs", "teams")
    incoming = os.path.join(base, "incoming")
    outgoing = os.path.join(base, "outgoing")
    incoming_approvals = os.path.join(incoming, "approvals")
    incoming_summaries = os.path.join(incoming, "summaries")
    for path in (base, incoming, outgoing, incoming_approvals, incoming_summaries):
        os.makedirs(path, exist_ok=True)
    return {
        "base": base,
        "incoming": incoming,
        "incoming_approvals": incoming_approvals,
        "incoming_summaries": incoming_summaries,
        "outgoing": outgoing,
    }


def _slugify_name(name: str) -> str:
    """Convert user-provided names into a filesystem-safe slug."""
    if not name:
        return "user"
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    slug = slug.strip("_")
    return slug or "user"


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


def _write_approval_log(session_id: str, approved: bool, plan_summary: str, note: str = "") -> str:
    """
    Writes an approval event to a log file.
    """
    root_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
    out_dir = os.path.join(root_dir, "logs", "approvals")
    os.makedirs(out_dir, exist_ok=True)
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    filename = f"{session_id}_approvals.txt"
    filepath = os.path.join(out_dir, filename)
    with open(filepath, "a", encoding="utf-8") as f:
        f.write(f"{stamp} | APPROVED={approved} | PLAN={plan_summary}\n")
        if note:
            f.write(f"note: {note}\n")
    return filepath


def set_approval_status(
    tool_context: ToolContext, approved: bool, plan_summary: str = "", note: str = ""
) -> Dict[str, Any]:
    """
    Records a human approval decision and persists it.
    """
    state = tool_context.state
    state["APPROVAL_STATUS"] = "APPROVED" if approved else "REJECTED"
    state["APPROVAL_TS"] = datetime.datetime.utcnow().isoformat()
    if plan_summary:
        state["APPROVAL_PLAN"] = plan_summary[:2000]
    if note:
        state["APPROVAL_NOTE"] = note[:1000]

    session_id = getattr(tool_context, "session_id", None)
    logfile = None
    if session_id:
        try:
            save_session_memory(session_id, state)
            logfile = _write_approval_log(
                session_id=session_id, approved=approved, plan_summary=plan_summary, note=note
            )
        except Exception as exc:
            print(f"[approval] failed to persist approval: {exc}")
    return {
        "approved": approved,
        "plan_summary": plan_summary,
        "note": note,
        "logfile": logfile,
    }


def get_approval_status(tool_context: ToolContext) -> Dict[str, Any]:
    """
    Returns the current approval status from session state.
    """
    state = tool_context.state
    status = state.get("APPROVAL_STATUS")
    return {
        "status": status,
        "approved": status == "APPROVED",
        "rejected": status == "REJECTED",
        "plan_summary": state.get("APPROVAL_PLAN"),
        "note": state.get("APPROVAL_NOTE"),
        "ts": state.get("APPROVAL_TS"),
    }


def send_teams_message(kind: str, message: str, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Simulates sending a Teams message by writing to an incoming folder.

    Args:
        kind: "approvals" or "summaries".
        message: Text to write.
        filename: Optional base filename (without path). Defaults to timestamped name.
    """
    paths = _ensure_teams_dirs()
    now = datetime.datetime.utcnow()
    stamp = now.strftime("%Y%m%d_%H%M%S")
    if filename:
        base_name = os.path.splitext(filename)[0] + ".txt"
    else:
        base_name = f"{kind}_{stamp}.txt"

    if kind == "approvals":
        incoming_dir = paths["incoming_approvals"]
    else:
        incoming_dir = paths["incoming_summaries"]

    incoming_path = os.path.join(incoming_dir, base_name)
    outgoing_path = os.path.join(paths["outgoing"], base_name)

    with open(incoming_path, "w", encoding="utf-8") as f:
        f.write(f"Timestamp: {now.isoformat()}Z\n")
        f.write(f"Type: {kind}\n")
        f.write("Content:\n")
        f.write(message.strip() + "\n")
        f.write("\n--- Reply in outgoing folder with the same filename. End message with 'over'. ---\n")

    print(f"[Teams simulated] wrote incoming {kind} message to {incoming_path}")
    return {
        "incoming_file": incoming_path,
        "outgoing_file": outgoing_path,
        "filename": base_name,
        "kind": kind,
    }


def read_teams_reply(filename: str) -> Dict[str, Any]:
    """
    Checks for a reply file in the outgoing folder and reports completion if it contains
    an approval decision plus the sentinel line 'over'.

    Args:
        filename: The base filename to look for (e.g., from send_teams_message).
    """
    paths = _ensure_teams_dirs()
    base_name = os.path.splitext(filename)[0] + ".txt"
    outgoing_path = os.path.join(paths["outgoing"], base_name)

    if not os.path.exists(outgoing_path):
        return {
            "status": "pending",
            "filename": base_name,
            "outgoing_file": outgoing_path,
            "message": "",
            "done": False,
            "reason": "no reply yet",
        }

    with open(outgoing_path, "r", encoding="utf-8") as f:
        content = f.read()

    lines = [ln.strip() for ln in content.splitlines() if ln.strip()]
    lowered = "\n".join(lines).lower()
    has_over = any(ln.lower() == "over" for ln in lines)
    has_not_approved = "not approved" in lowered or "rejected" in lowered
    has_approved = "approved" in lowered and not has_not_approved

    decision = "pending"
    done = False
    reason = ""
    if has_over and (has_approved or has_not_approved):
        done = True
        decision = "approved" if has_approved else "rejected"
    else:
        reason = "no clear approval decision or missing 'over' marker"

    return {
        "status": decision,
        "filename": base_name,
        "outgoing_file": outgoing_path,
        "message": content,
        "done": done,
        "decision": decision,
        "reason": reason,
    }


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
    elif step == "approval_request":
        state["WAITING_FOR_APPROVAL"] = True
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
    Simulates sending a manager summary by writing a text file to the Teams incoming/summaries folder; also prints to console.
    
    Args:
        message: The summary text to send.
    """
    result = send_teams_message(kind="summaries", message=message, filename=None)
    print(f"\n[Teams Manager DM] (simulated) >>> {message}\n")
    print(f"[Teams Manager DM] Saved summary to {result['incoming_file']}\n")

    return {
        "status": "sent",
        "recipient": "Manager",
        "content": message,
        "file": result["incoming_file"],
        "reply_file": result["outgoing_file"],
    }


def queue_high_risk_approval(
    tool_context: ToolContext, user_name: str, action: str = "deletion"
) -> Dict[str, Any]:
    """
    Creates an approval request file in the approvals folder and records the filename in session state.

    Args:
        user_name: Name of the user being acted on (used for filename clarity).
        action: Description of the high-risk action (default: deletion).
    """
    stamp = datetime.datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    slug = _slugify_name(user_name)
    base_name = f"approvals_{slug}_{stamp}.txt"
    message = (
        f"High-risk {action} requested for '{user_name}'. "
        "Reply in the outgoing folder with 'Approved' or 'Not Approved' and add a line with 'over'."
    )
    result = send_teams_message(kind="approvals", message=message, filename=base_name)

    state = tool_context.state
    state["WAITING_FOR_APPROVAL"] = True
    state["APPROVAL_FILENAME"] = result["filename"]

    session_id = getattr(tool_context, "session_id", None)
    if session_id:
        try:
            save_session_memory(session_id, state)
        except Exception as exc:
            print(f"[memory] failed to persist approval filename: {exc}")

    return {
        "status": "queued",
        "filename": result["filename"],
        "incoming_file": result["incoming_file"],
        "outgoing_file": result["outgoing_file"],
        "instruction": "Reply with Approved/Not Approved and 'over' on the next line.",
    }


def check_approval_status(
    tool_context: ToolContext, filename: Optional[str] = None
) -> Dict[str, Any]:
    """
    Checks the approval reply for the given filename (or the last queued approval in state).
    Returns pending if no decision is present or if 'over' is missing.
    """
    state = tool_context.state
    target_file = filename or state.get("APPROVAL_FILENAME")
    if not target_file:
        return {
            "status": "pending",
            "done": False,
            "reason": "no approval filename found in state",
        }

    reply = read_teams_reply(target_file)
    decision = reply.get("decision", "pending")
    done = reply.get("done", False)
    reason = reply.get("reason", "")

    if done and decision in {"approved", "rejected"}:
        state["WAITING_FOR_APPROVAL"] = False
        state["APPROVAL_STATUS"] = "APPROVED" if decision == "approved" else "REJECTED"
        state["APPROVAL_TS"] = datetime.datetime.utcnow().isoformat()
    else:
        state["WAITING_FOR_APPROVAL"] = True

    session_id = getattr(tool_context, "session_id", None)
    if session_id:
        try:
            save_session_memory(session_id, state)
        except Exception as exc:
            print(f"[memory] failed to persist approval status: {exc}")

    return {
        **reply,
        "status": decision,
        "done": done,
        "reason": reason,
        "approval_filename": target_file,
    }


def request_approval(tool_context: ToolContext, description: str) -> Dict[str, Any]:
    """
    Sends an approval request via simulated Teams folders and sets the session to wait.
    
    Args:
        description: Description of the high-risk action requiring approval.
    """
    result = send_teams_message(kind="approvals", message=description)
    print(f"\n[Teams Approval] >>> wrote request to {result['incoming_file']}")
    print(f"[Teams Approval] Awaiting reply in {result['outgoing_file']} (end with 'over')\n")

    tool_context.state["WAITING_FOR_APPROVAL"] = True

    return {
        "status": "sent",
        "type": "approval_card",
        "content": description,
        "incoming_file": result["incoming_file"],
        "outgoing_file": result["outgoing_file"],
        "action_required": "Manager Approval",
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
    


