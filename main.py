import asyncio
import os
import ulma_agents

def main():
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
            response = ulma_agents.run(user_input)
        except Exception as e:
            print(f"Agent error: {e}")
            continue

        # ADK normally returns a string or a structured response;
        # adjust this if your agent uses a different API
        print("\nAgent:", response)


if __name__ == "__main__":
    main()