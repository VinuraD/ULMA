# ULMA (User Lifecycle Management Agent)

ULMA is an AI-powered IT administration assistant designed to automate user lifecycle management tasks such as onboarding, offboarding, and access control (groups, roles, apps).

It leverages the **Google Agent Development Kit (ADK)** and **Google Gemini Models** to interpret natural language requests, validate policies, and execute simulated administrative actions.

---

## Architecture

![ULMA Architecture](Overall_Summary.png)

---

## Highlights for Course Submission
- **Multi-agent system:** Front → Supervisor → Policy, Identity, Teams, and Remote Branch agents; includes delegation to Branch B (A2A).
- **Tools:** MCP (Azure MCP server + SQLite), custom tools for policy reading/approvals/logging, ADK built-ins.
- **Long-running operations:** ADK pause/resume via `request_confirmation` for high-risk deletes; resumes the same invocation after human decision.
- **Sessions & memory:** `InMemorySessionService` plus SQLite persistence for state/approvals.
- **Context engineering:** Policy parsing and compacted state passed across agents; approval filename stored/reused across turns.
- **Observability:** ADK `LoggingPlugin`, simulated Teams logs, Branch B local audit.
- **Deployment:** CLI runner with resumable sessions; FastAPI server for Branch B demo.

## Human-in-the-Loop Approvals (text files)
- High-risk delete/offboard requests call `queue_high_risk_approval`, which writes an approval card to `logs/teams/incoming/approvals/approvals_<user>_<timestamp>.txt` and issues an ADK `request_confirmation` pause event.
- Add the decision in `logs/teams/outgoing/<same filename>` containing “Approved” or “Not Approved/Rejected” plus a line with `over`.
- The runner polls the outgoing file and resumes the same `invocation_id` with a `FunctionResponse`, proceeding only if approved; rejection or missing reply stops execution.
- Approval status is persisted in session state, so you can restart and continue waiting.

## 🚀 Features

*   **Natural Language Interface:** Chat with the agent to request IT tasks (e.g., *"Onboard Adam using the standard policy"*).
*   **Multi-Agent Architecture:**
    *   **Supervisor Agent:** Orchestrates the workflow, validates inputs, and delegates tasks.
    *   **Policy Agent:** Reads and interprets PDF policy documents (e.g., `General_Policies_for_Time_Travelers_Inc.pdf`) to ensure compliance.
    *   **Identity Agent:** (Stub) Simulates Active Directory changes (User creation, Role assignment).
    *   **Teams Agent:** Handles communication, logs technical updates to Microsoft Teams, and sends **Executive Summaries** to managers.
    *   **Remote Branch Agent:** Demonstrates **Agent-to-Agent (A2A)** capabilities by accepting delegated tasks for out-of-scope branches.
*   **Persistent Memory:** Retains session state across restarts using a local SQLite database, solving the "amnesia" problem of typical LLM sessions.
*   **MCP Integration:** Uses the **Model Context Protocol (MCP)** to securely query local databases (SQLite) directly from the AI.

---

## 🛠️ Installation

### Prerequisites
*   **Python 3.11+**
*   **Conda** (recommended) or `venv`
*   **Google Cloud Project** with Vertex AI enabled (or an AI Studio API Key).

### Setup
1.  **Clone the repository:**
    ```bash
    git clone https://github.com/VinuraD/ULMA.git
    cd ULMA
    ```

2.  **Install Dependencies:**
    *   **Windows:** Run `.\setup.bat`
    *   **Linux/Mac:** Run `./setup.sh` (ensure it is executable: `chmod +x setup.sh`)

    Alternatively, manually install:
    ```bash
    conda create -n ulma python=3.11 -y
    conda activate ulma
    pip install -r requirements.txt
    ```

3.  **Configuration:**
    *   Create a `.env` file in `ulma_agents/` to setup API keys.
    *   Ensure you have authentication set up for Google Cloud (e.g., `gcloud auth application-default login`) or set `GOOGLE_API_KEY`.
    * Similarly, create an `.env` file in `azure_mcp_server/` to setup Azure/Entra ID related credentials (this is required by the agent to properly run).
    * It should have keys; `AZURE_TENANT_ID`,`AZURE_CLIENT_ID`,`AZURE_CLIENT_SECRET`.
    * The `azure_mcp_server/` should be run on a different terminal, using `.\server.bat` (Windows). 

4.  **Initialize Database:**
    Run the database creation script to set up the local SQLite tables (`users` and `agent_memory`):
    ```bash
    python ulma_agents/create_db.py
    ```

---

## ▶️ Usage

Start the agent CLI (Windows):
```bash
.\start.bat
```

### 🧪 Testing Remote Branch (Agent-to-Agent)

To test the "Remote Delegation" scenario (Branch B), you must start the secondary agent server which simulates the remote branch's IT system.

1.  **Open a new terminal window.**
2.  **Run the Branch B Server:**
    ```bash
    .\start_branch_b.bat
    ```
    *This starts a FastAPI server on `localhost:8002` that listens for delegated tasks.*

3.  **In your main terminal (CLI), ask for a remote task:**
    ```text
    User: "Update role for Adam Smith to Manager."
    ```
    *The Supervisor will detect that Adam Smith is a "Branch B" user (via `lookup_user_location`) and delegate the execution to the remote agent.*

### Example Scenarios

#### 1. Standard Onboarding (Local)
**User:** *"Please onboard a new employee named Sarah. Check the General_Policies_for_Onboarding_Offboarding."*

**Agent Workflow:**
1.  **Supervisor** categorizes task as "Onboard".
2.  **Policy Agent** reads the PDF and extracts constraints.
3.  **Identity Agent** creates the user stub.
4.  **Teams Agent** logs the technical details and sends a summary to the manager.

#### 2. Remote Delegation (Agent-to-Agent POC)
**User:** *"Update role for Adam Smith to Manager."*

**Agent Workflow:**
1.  **Supervisor** calls `lookup_user_location("Adam Smith")` and detects "Branch B".
2.  **Supervisor** delegates the task to the **Remote Branch Agent**.
3.  **Remote Agent** (Branch B) executes the role update locally.
4.  **Teams Agent** reports the successful delegation to the manager.

---

## 📂 Project Structure

```
d:\ULMA\ULMA\
├── main.py                 # CLI Entry point
├── start.bat               # Launcher script
├── setup.bat               # Installation script
├── ulma_agents/            # Core Agent Logic
│   ├── supervisor.py       # Main orchestrator agent
│   ├── config.py           # Model configurations
│   ├── runner.py           # Session execution & persistence logic
│   ├── tools.py            # Tools: DB access, Logging, MCP integration
│   ├── create_db.py        # Database setup utility
│   ├── sub_agents/         # Specialized Worker Agents
│   │   ├── identity_agent.py
│   │   ├── policy_agent.py
│   │   ├── teams_agent.py  # Handles Logging & Reporting
│   │   └── remote_agent.py # Simulates external branch A2A
│   └── policy/             # PDF Policy documents
└── azure_mcp_server/       # MCP server components
```

---

## 🧠 Memory System

ULMA uses a dual-layer memory approach:
1.  **Short-term:** In-memory context during the active run.
2.  **Long-term:** SQLite-backed `agent_memory` table.
    *   State is hydrated at the start of a session.
    *   State is persisted automatically after every turn or critical tool usage.

---

---
*Built with Google ADK & Gemini.*
