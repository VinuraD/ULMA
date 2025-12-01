import httpx
import json
from typing import Dict, Any

def talk_to_branch_b(message: str, session_id: str = "default") -> str:
    """
    Sends a message to the remote Branch B agent server and returns the response.
    
    Args:
        message: The instruction or query for Branch B.
        session_id: Session identifier.
    """
    url = "http://localhost:8002/agent"
    try:
        # Use synchronous Client for compatibility with standard FunctionTool execution
        with httpx.Client() as client:
            response = client.post(
                url, 
                json={"input": message, "session_id": session_id},
                timeout=60.0 
            )
            response.raise_for_status()
            data = response.json()
            return data.get("response", "No response text received from remote agent.")
            
    except Exception as e:
        return f"Error communicating with Branch B Server: {str(e)}. Is the server running on port 8002?"
