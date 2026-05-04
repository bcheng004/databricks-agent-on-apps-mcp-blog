#!/usr/bin/env python3
"""
Create a Databricks Genie space from a serialized space definition.

Reuses the workspace's default SQL warehouse and registers a single example
table (samples.nyctaxi.trips) as the data source. Adjust the
``serialized_space`` dict to point at your own tables/columns.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv
from ruamel.yaml import YAML

load_dotenv()

DATABRICKS_YML = Path(__file__).resolve().parent.parent / "databricks.yml"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--profile",
        default=os.getenv("DATABRICKS_CONFIG_PROFILE"),
        help="Databricks config profile (default: DATABRICKS_CONFIG_PROFILE from .env)",
        metavar="NAME",
    )
    parser.add_argument(
        "--title",
        help="Title of the Genie space (prompted if omitted)",
    )
    parser.add_argument(
        "--warehouse-id",
        help="SQL warehouse ID (prompted if workspace has no default)",
    )
    parser.add_argument(
        "--description",
        default="This is a genie space for the demo",
        help="Description of the Genie space (default: %(default)s)",
    )
    return parser.parse_args()


RESOURCE_NAME_MAX_LEN = 30


def add_genie_space_to_app(space_id: str, title: str) -> None:
    """Replace all genie_space resources in ``databricks.yml`` with this one.

    Strips every existing entry that has a ``genie_space`` key and appends
    a single fresh entry — so reruns don't accumulate stale spaces from
    prior runs. Mirrors the ``uc_securable`` handling in
    ``setup_asana_mcp_connection._add_uc_connection_to_bundle``.
    """
    from ruamel.yaml.comments import CommentedMap

    yaml = YAML()
    yaml.preserve_quotes = True
    yaml.indent(mapping=2, sequence=4, offset=2)
    with DATABRICKS_YML.open() as f:
        cfg = yaml.load(f)

    apps = cfg.get("resources", {}).get("apps", {})
    if not apps:
        print(
            f"Warning: no resources.apps in {DATABRICKS_YML}, skipping update",
            file=sys.stderr,
        )
        return

    app_key = next(iter(apps))
    app = apps[app_key]
    resources = app.setdefault("resources", [])

    base = re.sub(r"[^a-z0-9_]+", "_", title.lower()).strip("_") or "genie_space"
    resource_name = base[:RESOURCE_NAME_MAX_LEN].rstrip("_") or "genie_space"

    new_entry = CommentedMap()
    new_entry["name"] = resource_name
    genie = CommentedMap()
    genie["name"] = title
    genie["space_id"] = space_id
    genie["permission"] = "CAN_RUN"
    new_entry["genie_space"] = genie

    removed = [
        r.get("name", "<unnamed>")
        for r in resources
        if isinstance(r, dict) and "genie_space" in r
    ]
    indices_to_drop = [
        i
        for i, r in enumerate(resources)
        if isinstance(r, dict) and "genie_space" in r
    ]
    for i in reversed(indices_to_drop):
        del resources[i]

    resources.append(new_entry)
    with DATABRICKS_YML.open("w") as f:
        yaml.dump(cfg, f)

    if removed:
        print(
            f"  -> replaced {len(removed)} existing genie_space entr"
            f"{'y' if len(removed) == 1 else 'ies'} "
            f"({', '.join(removed)}) with {resource_name!r} ({space_id}) in "
            f"{DATABRICKS_YML} (under app '{app_key}')"
        )
    else:
        print(
            f"  -> added genie_space resource {resource_name!r} ({space_id}) "
            f"to {DATABRICKS_YML} (under app '{app_key}')"
        )


def find_existing_space(w: WorkspaceClient, name: str):
    page_token = None
    while True:
        resp = w.genie.list_spaces(page_token=page_token)
        for space in resp.spaces or []:
            if space.title == name:
                return space
        page_token = resp.next_page_token
        if not page_token:
            return None


def main() -> None:
    args = parse_args()

    if not args.profile:
        print(
            "Error: --profile not provided and DATABRICKS_CONFIG_PROFILE not set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    use_existing = input("Use an existing Genie space? [y/N]: ").strip().lower() in {
        "y",
        "yes",
    }

    if not args.title:
        prompt = (
            "Existing Genie space title: " if use_existing else "Genie space title: "
        )
        args.title = input(prompt).strip()
        if not args.title:
            print("Error: title is required", file=sys.stderr)
            sys.exit(1)

    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile
    w = WorkspaceClient(profile=args.profile)

    if use_existing:
        match = find_existing_space(w, args.title)
        if not match:
            print(
                f"Error: no Genie space found with title {args.title!r}",
                file=sys.stderr,
            )
            sys.exit(1)
        full = w.genie.get_space(match.space_id, include_serialized_space=True)
        print(f"Found Genie space {full.space_id}: {full.serialized_space}")
        add_genie_space_to_app(full.space_id, full.title or args.title)
        return

    warehouse_id = args.warehouse_id
    if not warehouse_id:
        default = w.settings.default_warehouse_id.get().string_val
        warehouse_id = default.value if default else None
    if not warehouse_id:
        warehouse_id = input("SQL warehouse ID: ").strip()
        if not warehouse_id:
            print("Error: warehouse_id is required", file=sys.stderr)
            sys.exit(1)
    print(f"Using warehouse_id: {warehouse_id}")

    serialized_space = {
        "version": 2,
        "data_sources": {
            "tables": [
                {
                    "identifier": "system.billing.usage",
                    "column_configs": [
                        {"column_name": "account_id", "enable_format_assistance": True},
                        {
                            "column_name": "billing_origin_product",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {
                            "column_name": "cloud",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {"column_name": "custom_tags"},
                        {"column_name": "identity_metadata"},
                        {
                            "column_name": "ingestion_date",
                            "enable_format_assistance": True,
                        },
                        {"column_name": "product_features"},
                        {"column_name": "record_id", "enable_format_assistance": True},
                        {
                            "column_name": "record_type",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {
                            "column_name": "sku_name",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {"column_name": "usage_date", "enable_format_assistance": True},
                        {
                            "column_name": "usage_end_time",
                            "enable_format_assistance": True,
                        },
                        {"column_name": "usage_metadata"},
                        {
                            "column_name": "usage_quantity",
                            "enable_format_assistance": True,
                        },
                        {
                            "column_name": "usage_start_time",
                            "enable_format_assistance": True,
                        },
                        {
                            "column_name": "usage_type",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {
                            "column_name": "usage_unit",
                            "enable_format_assistance": True,
                            "enable_entity_matching": True,
                        },
                        {
                            "column_name": "workspace_id",
                            "enable_format_assistance": True,
                        },
                    ],
                }
            ]
        },
    }

    space = w.genie.create_space(
        warehouse_id=warehouse_id,
        serialized_space=json.dumps(serialized_space),
        description=args.description,
        title=args.title,
    )
    print(f"Created Genie space: {space.serialized_space}")
    add_genie_space_to_app(space.space_id, args.title)


if __name__ == "__main__":
    main()
