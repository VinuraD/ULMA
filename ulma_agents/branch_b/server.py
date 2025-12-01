import uvicorn
from fastapi import FastAPI, Request
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from .agent import remote_branch_agent
import os
import json
from google.genai import types

app = FastAPI()

# Initialize the runner for the agent
session_service = InMemorySessionService()
runner = Runner(
    agent=remote_branch_agent,
    app_name="branch_b_server",
    session_service=session_service
)

@app.post("/agent")
async def run_agent(request: Request):
    """
    Endpoint to receive requests for the Branch B agent.
    Expects a JSON body with 'input' key.
    """
    data = await request.json()
    user_input = data.get("input") or data.get("message")
    
    if not user_input:
        return {"error": "No input provided"}

    print(f"[Branch B Server] Received: {user_input}")

    # Use a fixed session ID for the server demo or generate one
    session_id = data.get("session_id", "branch_b_session")

    # Ensure session exists
    # Handle both exception and None return from get_session
    session = None
    try:
        session = await session_service.get_session(app_name="branch_b_server", user_id="remote_user", session_id=session_id)
    except Exception:
        pass # Will create below

    if not session:
        print(f"[Branch B Server] Creating new session: {session_id}")
        await session_service.create_session(app_name="branch_b_server", user_id="remote_user", session_id=session_id)

    response_text = ""
    
    # Run the agent
    # Wrap input in types.Content as expected by ADK Runner
    formatted_input = types.Content(role='user', parts=[types.Part(text=user_input)])
    
    responses = runner.run_async(
        session_id=session_id,
        new_message=formatted_input,
        user_id="remote_user"
    )

    async for event in responses:
        # Robustly extract text from various event types
        
        # Case 1: Standard content parts
        if hasattr(event, 'content') and event.content:
            if hasattr(event.content, 'parts'):
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        response_text += part.text
            elif isinstance(event.content, str):
                response_text += event.content

        # Case 2: Direct text attribute (some events)
        elif hasattr(event, 'text') and event.text:
            response_text += event.text
            
        # Case 3: Tool output/Function response (capture if needed for debug)
        # We mainly want the final agent answer.

    if not response_text:
        response_text = "Task completed (No text output generated)."

    print(f"[Branch B Server] Response: {response_text}")
    return {"response": response_text}

@app.get("/health")
def health():
    return {"status": "ok", "branch": "Branch B"}

if __name__ == "__main__":
    print("Starting Branch B Server on port 8002...")
    uvicorn.run(app, host="0.0.0.0", port=8002)
