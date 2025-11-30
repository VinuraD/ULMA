# ULMA (User Lifecycle Management Agent)

ULMA is an AI-powered IT administration assistant designed to automate user lifecycle management tasks such as onboarding, offboarding, and access control (groups, roles, apps).

It leverages the **Google Agent Development Kit (ADK)** and **Google Gemini Models** to interpret natural language requests, validate policies, and execute simulated administrative actions.

---

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
    *   Create a `.env` file in `ulma_agents/` (or root) if you need to override default database paths or API keys.
    *   Ensure you have authentication set up for Google Cloud (e.g., `gcloud auth application-default login`) or set `GOOGLE_API_KEY`.

4.  **Initialize Database:**
    Run the database creation script to set up the local SQLite tables (`users` and `agent_memory`):
    ```bash
    python ulma_agents/create_db.py
    ```

---

## ▶️ Usage

Start the agent CLI:
```bash
.\start.bat
```

### Example Scenarios

#### 1. Standard Onboarding (Local)
**User:** *"Please onboard a new employee named Sarah. Check the General_Policies_for_Time_Travelers_Inc policy."*

**Agent Workflow:**
1.  **Supervisor** categorizes task as "Onboard".
2.  **Policy Agent** reads the PDF and extracts constraints.
3.  **Identity Agent** creates the user stub.
4.  **Teams Agent** logs the technical details and sends a summary to the manager.

#### 2. Remote Delegation (Agent-to-Agent POC)
**User:** *"Onboard John Doe for Branch B."*

**Agent Workflow:**
1.  **Supervisor** detects "Branch B" is out of local scope.
2.  **Supervisor** delegates the task to the **Remote Branch Agent**.
3.  **Remote Agent** confirms execution.
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
└── azure_mcp_server/       # (Optional) Standalone MCP server components
```

---

## 🧠 Memory System

ULMA uses a dual-layer memory approach:
1.  **Short-term:** In-memory context during the active run.
2.  **Long-term:** SQLite-backed `agent_memory` table.
    *   State is hydrated at the start of a session.
    *   State is persisted automatically after every turn or critical tool usage.

---

## 🤝 Contributing

1.  Fork the repo.
2.  Create a feature branch.
3.  Submit a Pull Request.

---
*Built with Google ADK & Gemini.*
