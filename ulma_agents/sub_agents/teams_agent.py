teams_agent = Agent(
    name="TeamsAgent",
    model=,
    include_contents="none",
    instruction="""
You are the Teams/Notification sub-agent.
- Pretend to send notifications / Teams messages.
- If notifications succeed, call 'set_step_status' with step="teams" and ok=true.
- If they fail, call 'set_step_status' with ok=false and explain.
""",
    description="Sends notifications and records status.",
    tools=[save_step_status],
)