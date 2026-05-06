# databricks-agent-on-apps-mcp-blog

<p align="center">
  <img src="assets/databricks-mark.svg" alt="Databricks" height="40" />
  &nbsp;&nbsp;<strong>×</strong>&nbsp;&nbsp;
  <img src="assets/asana-logo.svg" alt="Asana" height="36" />
</p>

https://github.com/user-attachments/assets/9c6b6342-5e52-4921-947b-ea2e8c85c06a

Based on the [agent-langgraph-advanced app template](https://github.com/databricks/app-templates/tree/main/agent-langgraph-advanced).

## Asana OAuth app setup

Before running `setup-asana-mcp`, create an OAuth application in the [Asana developer console](https://app.asana.com/0/my-apps) and set the **redirect URL** to:

```
<workspaceurl>/login/oauth/http.html
```

Replace `<workspaceurl>` with your Databricks workspace host (e.g. `https://example.cloud.databricks.com`). Save the resulting `client_id` and `client_secret` — `setup-asana-mcp` will prompt for them when wiring up the UC HTTP connection.

## Local development

### Prerequisites

- Python 3.11+ and [`uv`](https://docs.astral.sh/uv/)
- The [Databricks CLI](https://docs.databricks.com/aws/en/dev-tools/cli/install) authenticated with a profile (`databricks auth login --profile <profile>`)
- A Lakebase instance (autoscaling) — required for agent memory

### 1. Bootstrap the environment

`quickstart` writes a `.env`, configures auth, and points the agent at your Lakebase.

```bash
uv run quickstart
```

Arguments:

- `--profile <profile>` — Databricks CLI profile to write into `.env`
- `--lakebase-autoscaling-project <project>` — Lakebase autoscaling project name
- `--lakebase-autoscaling-branch <branch>` — branch within the autoscaling project

Verify the profile is valid afterwards:

```bash
databricks auth profiles
```

> All `databricks` CLI commands need the profile from `.env` — either `--profile <name>` or `DATABRICKS_CONFIG_PROFILE=<name> databricks ...`.

### 2. Wire up the MCP tools (optional)

Asana MCP (UC HTTP connection + `databricks.yml` + `utils.py` wiring):

```bash
uv run setup-asana-mcp
```

Arguments:

- `--profile <profile>` — Databricks CLI profile
- `--app-name <app>` — Databricks app that gets `USE_CONNECTION` on the new UC connection
- `--connection-name <name>` — UC HTTP connection name to create (e.g. `mcp_agent_asana`)

**Make sure to Login to the Asana MCP Connection to auth the OAuth user to machine per user**

Genie space (creates or reuses, then rewrites `databricks.yml` + `utils.py` URL):

```bash
uv run create-genie-space
```

Arguments:

- `--profile <profile>` — Databricks CLI profile
- `--title "<space title>"` — Genie space title to create or reuse
- `--warehouse-id <id>` *(optional)* — SQL warehouse ID; falls back to the workspace default

> After `uv run setup-asana-mcp` finishes, complete the OAuth handshake in the Databricks UI: open the new UC connection in **Catalog Explorer → External Data → Connections**, click **Login**, and approve the scopes in the Asana popup (if needed). Until that login is done the connection has credentials but no user token, so MCP tool calls will fail with 401s.

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

Deploy the bundle:

```bash
databricks bundle deploy
```

Arguments:

- `--profile <profile>` — Databricks CLI profile

Grant the app's SP the Lakebase grants it needs for memory tables:

```bash
uv run grant-lakebase-permissions
```

Arguments:

- `--profile <profile>` — Databricks CLI profile
- `--app-name <app>` — the app whose service principal gets the grants
- `--memory-type langgraph` — schema set to grant against (matches this template)

Run the bundle:

```bash
databricks bundle run
```

Arguments:

- `agent_langgraph_advanced_mcp` *(positional)* — bundle resource name to run
- `--profile <profile>` — Databricks CLI profile

> `grant-lakebase-permissions` has to run *after* the bundle deploy because the app's service principal client ID only exists once the app is created.
