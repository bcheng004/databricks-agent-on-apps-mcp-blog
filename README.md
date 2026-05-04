# databricks-agent-on-apps-mcp-blog

<p align="center">
  <img src="assets/databricks-mark.svg" alt="Databricks" height="40" />
  &nbsp;&nbsp;<strong>×</strong>&nbsp;&nbsp;
  <img src="assets/asana-logo.svg" alt="Asana" height="36" />
</p>

Based on the [agent-langgraph-advanced app template](https://github.com/databricks/app-templates/tree/main/agent-langgraph-advanced).

## Local development

### Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- The [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) authenticated with a profile (`databricks auth login --profile <profile>`)
- A Lakebase instance (autoscaling) — required for agent memory

### 1. Bootstrap the environment

`quickstart` writes a `.env`, configures auth, and points the agent at your Lakebase

**Autoscaling Lakebase (project + branch):**

```bash
uv run quickstart \
  --profile <profile> \
  --lakebase-autoscaling-project <project> \
  --lakebase-autoscaling-branch <branch>
```

Verify the profile is valid afterwards:

```bash
databricks auth profiles
```

> All `databricks` CLI commands need the profile from `.env` — either `--profile <name>` or `DATABRICKS_CONFIG_PROFILE=<name> databricks ...`.

### 2. Wire up the MCP tools (optional)

```bash
# Asana MCP (UC HTTP connection + databricks.yml + utils.py wiring)
uv run setup-asana-mcp --profile <profile> --app-name <app> --connection-name <name>

# Genie space (creates or reuses, then rewrites databricks.yml + utils.py URL)
uv run create-genie-space --profile <profile> --title "<space title>"
```

Each script edits `databricks.yml` (replaces the matching resource block) and `agent_server/utils.py` (rewrites the URL on the matching `DatabricksMCPServer` entry) in place — reruns are idempotent.

### 3. Run the agent locally

```bash
uv run start-app
```

This starts the FastAPI agent server on port 8000 and the chat UI on port 3000. With `DATABRICKS_APP_NAME` unset, the user workspace client falls back to the `DATABRICKS_CONFIG_PROFILE` profile from `.env`, so you can talk to MCP tools end-to-end without the Apps OBO header.

To explore what tools/resources are available in the workspace:

```bash
uv run discover-tools
```

### 4. Deploy to Databricks Apps

```bash
databricks bundle deploy --profile <profile>
databricks bundle run agent_langgraph_advanced_mcp --profile <profile>
```

