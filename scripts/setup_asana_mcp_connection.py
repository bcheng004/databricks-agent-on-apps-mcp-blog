"""Set up the Asana MCP Unity Catalog HTTP connection interactively.

Python port of the ``04-external-asana-connection-mcp`` notebook. Prompts the
terminal for the Asana OAuth M2M ``client_id``/``client_secret``, stores them
in a Databricks secret scope, creates the UC HTTP connection pointed at
Asana's MCP endpoint, and grants ``USE_CONNECTION`` to the agent app's
service principal.

Usage:
    uv run python scripts/setup_asana_mcp_connection.py \\
        --profile fevm \\
        --app-name bo-agents-on-apps \\
        --connection-name asana_bohao

Flags that are omitted are prompted for interactively. ``client_secret`` is
always read via ``getpass`` so it is not echoed or saved to shell history.
"""

from __future__ import annotations

import argparse
import getpass
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

DEFAULT_CONNECTION = "asana_bohao"
DEFAULT_APP_NAME = "bo-agents-on-apps"
DEFAULT_BUNDLE_YAML = "databricks.yml"
DEFAULT_UTILS_PY = "agent_server/utils.py"

ASANA_HOST = "https://mcp.asana.com"
ASANA_BASE_PATH = "/v2/mcp"
ASANA_TOKEN_ENDPOINT = "https://app.asana.com/-/oauth_token"
ASANA_AUTHORIZATION_ENDPOINT = "https://app.asana.com/-/oauth_authorize"
ASANA_OAUTH_SCOPE = "default"


def _prompt(message: str, *, default: str = "", secret: bool = False) -> str:
    suffix = f" [{default}]" if default and not secret else ""
    if secret:
        value = getpass.getpass(f"{message}{suffix}: ")
    else:
        value = input(f"{message}{suffix}: ").strip()
    return value or default


def _prompt_yes_no(message: str, *, default: bool = False) -> bool:
    hint = "Y/n" if default else "y/N"
    value = input(f"{message} [{hint}]: ").strip().lower()
    if not value:
        return default
    return value in ("y", "yes")


def _add_uc_connection_to_bundle(
    connection_name: str,
    app_name: str,
    yaml_path: str = DEFAULT_BUNDLE_YAML,
) -> None:
    """Add or replace the UC connection resource for this connection in ``databricks.yml``."""
    from ruamel.yaml import YAML
    from ruamel.yaml.comments import CommentedMap

    path = Path(yaml_path)
    if not path.exists():
        print(f"  (no {yaml_path} found; skipping bundle update)")
        return

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)

    with path.open("r") as f:
        data = yaml.load(f)

    apps = (data or {}).get("resources", {}).get("apps", {}) or {}
    if not apps:
        print(f"  (no apps defined in {yaml_path}; skipping bundle update)")
        return

    target_key = None
    for key, app_cfg in apps.items():
        if isinstance(app_cfg, dict) and app_cfg.get("name") == app_name:
            target_key = key
            break
    if target_key is None:
        target_key = next(iter(apps))
        print(
            f"  (app '{app_name}' not found in {yaml_path}; "
            f"using first app '{target_key}')"
        )

    app_entry = apps[target_key]
    resources = app_entry.setdefault("resources", [])

    new_entry = CommentedMap()
    new_entry["name"] = connection_name
    uc_sec = CommentedMap()
    uc_sec["securable_full_name"] = connection_name
    uc_sec["securable_type"] = "CONNECTION"
    uc_sec["permission"] = "USE_CONNECTION"
    new_entry["uc_securable"] = uc_sec

    # Replace any existing uc_securable entry with name matching connection_name
    for i, r in enumerate(resources):
        if not isinstance(r, dict):
            continue
        if r.get("name") == connection_name and "uc_securable" in r:
            resources[i] = new_entry
            with path.open("w") as f:
                yaml.dump(data, f)
            print(
                f"  -> replaced UC connection resource '{connection_name}' in "
                f"{yaml_path} (under app '{target_key}')"
            )
            return

    resources.append(new_entry)
    with path.open("w") as f:
        yaml.dump(data, f)
    print(
        f"  -> added UC connection resource '{connection_name}' to "
        f"{yaml_path} (under app '{target_key}')"
    )


def _add_asana_mcp_server_to_agent(
    connection_name: str,
    utils_path: str = DEFAULT_UTILS_PY,
) -> None:
    """Insert or update an ``asana`` DatabricksMCPServer entry in ``init_mcp_client``.

    If a server with ``name="asana"`` is already present, its URL is updated
    in place to point at ``{host_name}/api/2.0/mcp/external/{connection_name}``
    — so reruns with a different connection name stay in sync. Otherwise a new
    entry is appended to the MCP server list. Skips cleanly when the expected
    insertion anchor cannot be located, so manual edits won't be clobbered.
    """
    import re

    path = Path(utils_path)
    if not path.exists():
        print(f"  (no {utils_path} found; skipping agent update)")
        return

    text = path.read_text()
    new_url = f'url=f"{{host_name}}/api/2.0/mcp/external/{connection_name}"'

    if 'name="asana"' in text:
        url_pattern = re.compile(
            r'(name="asana",\s*\n\s*)url=f"\{host_name\}/api/2\.0/mcp/external/[^"]*"'
        )
        new_text, count = url_pattern.subn(rf"\g<1>{new_url}", text, count=1)
        if count == 0:
            print(
                f"  ('asana' MCP server present in {utils_path} but URL line "
                "didn't match expected shape; manual edit needed)"
            )
            return
        if new_text == text:
            print(
                f"  ('asana' MCP server already points at '{connection_name}' "
                f"in {utils_path})"
            )
            return
        path.write_text(new_text)
        print(
            f"  -> updated 'asana' DatabricksMCPServer URL to "
            f".../mcp/external/{connection_name} in {utils_path}"
        )
        return

    anchor = "            ),\n        ]"
    if text.count(anchor) != 1:
        print(
            f"  (could not find unique insertion anchor in {utils_path}; "
            "manual edit needed)"
        )
        return

    insertion = (
        "            ),\n"
        "            DatabricksMCPServer(\n"
        '                name="asana",\n'
        f"                {new_url},\n"
        "                workspace_client=workspace_client,\n"
        "            ),\n"
        "        ]"
    )

    new_text = text.replace(anchor, insertion, 1)
    path.write_text(new_text)
    print(
        f"  -> added 'asana' DatabricksMCPServer "
        f"(url .../mcp/external/{connection_name}) to {utils_path}"
    )


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Set up the Asana MCP UC HTTP connection.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p.add_argument(
        "--profile",
        help="Databricks CLI profile (defaults to DATABRICKS_CONFIG_PROFILE env).",
    )
    p.add_argument(
        "--connection-name",
        default=None,
        help=f"UC HTTP connection name. Prompted if omitted (default: {DEFAULT_CONNECTION}).",
    )
    p.add_argument(
        "--app-name",
        default=None,
        help=f"Databricks App that gets USE CONNECTION. Prompted if omitted (default: {DEFAULT_APP_NAME}).",
    )
    p.add_argument(
        "--asana-client-id",
        help="Asana OAuth client_id. Prompted if omitted.",
    )
    p.add_argument(
        "--asana-client-secret",
        help=(
            "Asana OAuth client_secret. Prompted via getpass if omitted — "
            "prefer the prompt so it isn't saved to shell history."
        ),
    )
    p.add_argument(
        "--skip-grant",
        action="store_true",
        default=None,
        help=(
            "Skip granting USE_CONNECTION to the app's service principal. "
            "Prompted (y/N) if the flag is not passed."
        ),
    )
    p.add_argument(
        "--skip-self-grant",
        action="store_true",
        help=(
            "Skip granting ALL_PRIVILEGES on the connection to the user "
            "running this script. Default: self-grant is applied."
        ),
    )
    p.add_argument(
        "--existing-connection",
        action="store_true",
        default=None,
        help=(
            "Use an existing UC HTTP connection instead of creating a new one. "
            "Skips credential prompts and the create step. Prompted (y/N) if omitted."
        ),
    )
    return p.parse_args()


def main() -> int:
    args = _parse_args()

    from databricks.sdk.errors import ResourceAlreadyExists
    from databricks.sdk.service import catalog

    from scripts.quickstart import get_workspace_client

    profile_name = args.profile or os.environ.get("DATABRICKS_CONFIG_PROFILE", "")
    if not profile_name:
        print(
            "Error: no Databricks profile set. Pass --profile or set "
            "DATABRICKS_CONFIG_PROFILE.",
            file=sys.stderr,
        )
        return 1

    w = get_workspace_client(profile_name)
    if w is None:
        print(
            f"Error: could not create WorkspaceClient for profile '{profile_name}'.",
            file=sys.stderr,
        )
        return 1
    print(f"Connected to: {w.config.host}")

    use_existing = (
        args.existing_connection
        if args.existing_connection is not None
        else _prompt_yes_no(
            "Do you have an existing Asana MCP UC connection you want to use?",
            default=False,
        )
    )

    connection_name = args.connection_name or _prompt(
        "UC HTTP connection name", default=DEFAULT_CONNECTION
    )

    if use_existing:
        print(f"Using existing connection '{connection_name}' — skipping create step.")
    else:
        client_id = args.asana_client_id or _prompt("Asana client_id", secret=True)
        if not client_id:
            print("Error: Asana client_id is required.", file=sys.stderr)
            return 1
        client_secret = args.asana_client_secret or _prompt(
            "Asana client_secret", secret=True
        )
        if not client_secret:
            print("Error: Asana client_secret is required.", file=sys.stderr)
            return 1

        options = {
            "host": ASANA_HOST,
            "port": "443",
            "base_path": ASANA_BASE_PATH,
            "client_id": client_id,
            "client_secret": client_secret,
            "token_endpoint": ASANA_TOKEN_ENDPOINT,
            "authorization_endpoint": ASANA_AUTHORIZATION_ENDPOINT,
            "oauth_scope": ASANA_OAUTH_SCOPE,
            "is_mcp_connection": "true",
        }

        print(f"Creating UC HTTP connection '{connection_name}'...")
        try:
            w.connections.create(
                name=connection_name,
                connection_type=catalog.ConnectionType.HTTP,
                options=options,
            )
            print(f"  -> created '{connection_name}'")
        except ResourceAlreadyExists:
            print(f"  -> '{connection_name}' already exists; leaving it in place")

    skip_grant = (
        args.skip_grant
        if args.skip_grant is not None
        else _prompt_yes_no(
            "Skip granting USE_CONNECTION to the app's service principal?",
            default=False,
        )
    )

    if not args.skip_self_grant:
        me = w.current_user.me().user_name
        if me:
            print(
                f"Granting ALL_PRIVILEGES on '{connection_name}' to "
                f"current user '{me}'..."
            )
            w.grants.update(
                securable_type="CONNECTION",
                full_name=connection_name,
                changes=[
                    catalog.PermissionsChange(
                        add=[catalog.Privilege.ALL_PRIVILEGES],
                        principal=me,
                    )
                ],
            )
            print("Granted ALL_PRIVILEGES to current user.")
        else:
            print("  (could not resolve current user; skipping self-grant)")

    app_name = args.app_name or _prompt("Databricks app name", default=DEFAULT_APP_NAME)

    print(f"Updating {DEFAULT_BUNDLE_YAML} with UC connection resource...")
    _add_uc_connection_to_bundle(connection_name, app_name)

    print(f"Updating {DEFAULT_UTILS_PY} with 'asana' DatabricksMCPServer...")
    _add_asana_mcp_server_to_agent(connection_name)

    if skip_grant:
        print("Skipping USE_CONNECTION grant.")
        return 0

    print(f"Looking up app '{app_name}'...")
    app = w.apps.get(app_name)
    sp_client_id = app.service_principal_client_id
    if not sp_client_id:
        print(
            f"Error: app '{app_name}' has no service_principal_client_id "
            "— is the app deployed?",
            file=sys.stderr,
        )
        return 1

    print(
        f"Granting USE_CONNECTION on '{connection_name}' to SP "
        f"{sp_client_id}..."
    )
    w.grants.update(
        securable_type="CONNECTION",
        full_name=connection_name,
        changes=[
            catalog.PermissionsChange(
                add=[catalog.Privilege.USE_CONNECTION],
                principal=sp_client_id,
            )
        ],
    )
    print("Granted USE_CONNECTION.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
