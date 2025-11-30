import asyncio
import os
import ulma_agents
from google.genai import types
import warnings

async def main():
    
# Suppress all UserWarnings
    warnings.filterwarnings("ignore", category=UserWarning)
    agent=ulma_agents.agent_sessions(ulma_agents.front_agent)
    print("Welcome to the ULMA Agent CLI! Type 'exit' or 'quit' to leave.")
    while True:
        try:
            user_input = input("\nYou: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n\nExiting…")
            break

        if user_input.lower() in {"exit", "quit"}:
            print("Goodbye!")
            break

        if not user_input:
            continue

        # call the ADK agent; .run() returns a message-like object
        try:
            user_input=types.Content(role='user', parts=[types.Part(text=user_input)])
            response = await agent.execute(user_input)
        except Exception as e:
            print(f"Agent error: {e}")
            continue

        # ADK normally returns a string or a structured response;
        # adjust this if your agent uses a different API
        # print("\nAgent:", response)
        async for event in response:
             if event.content and event.content.parts:
                    # Filter out empty or "None" responses before printing
                    if (
                        event.content.parts[0].text != "None"
                        and event.content.parts[0].text
                    ):
                        print(f"Agent-ULMA> ", event.content.parts[0].text)
                        # print(f"Agent-ULMA> ", event.content.parts[0])


if __name__ == "__main__":
    asyncio.run(main())
