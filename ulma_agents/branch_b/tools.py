import json
import os
import datetime
from typing import Dict, Any, List

def _get_db_path() -> str:
    """Internal helper to get the local JSON path."""
    base_dir = os.path.dirname(__file__)
    return os.path.join(base_dir, "users.json")

def branch_b_find_user(name: str) -> Dict[str, Any]:
    """
    Locates a user in the Branch B local database.
    """
    db_path = _get_db_path()
    try:
        with open(db_path, 'r') as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "Database not found or corrupt."}

    for user in users:
        if user.get('name', '').lower() == name.lower():
            return {"status": "found", "user": user}
    
    return {"status": "not_found"}

def branch_b_update_role(name: str, new_role: str) -> Dict[str, Any]:
    """
    Updates the role of a user in the Branch B local database.
    Preserves other fields and adds timestamp.
    """
    db_path = _get_db_path()
    try:
        with open(db_path, 'r') as f:
            users = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"error": "Database not found or corrupt."}

    updated = False
    target_user = None
    
    for user in users:
        if user.get('name', '').lower() == name.lower():
            user['role'] = new_role
            user['last_updated'] = datetime.datetime.utcnow().isoformat() + "Z"
            user['updated_by'] = "Branch B Autonomous Agent"
            target_user = user
            updated = True
            break
    
    if updated:
        with open(db_path, 'w') as f:
            json.dump(users, f, indent=2)
        
        # Log operation locally
        _log_local_audit(name, "role_change", f"Changed to {new_role}")
        
        return {
            "status": "success", 
            "message": f"Updated {name} to role '{new_role}'.",
            "user": target_user
        }
    
    return {"status": "error", "message": "User not found."}

def _log_local_audit(user: str, action: str, details: str):
    """Simple local file audit log for Branch B"""
    log_path = os.path.join(os.path.dirname(__file__), "local_audit.log")
    timestamp = datetime.datetime.utcnow().isoformat()
    with open(log_path, "a") as f:
        f.write(f"[{timestamp}] USER:{user} ACTION:{action} DETAILS:{details}\n")
