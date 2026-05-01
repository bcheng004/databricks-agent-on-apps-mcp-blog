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
import sys

from databricks.sdk import WorkspaceClient
from dotenv import load_dotenv

load_dotenv()


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


def main() -> None:
    args = parse_args()

    if not args.profile:
        print(
            "Error: --profile not provided and DATABRICKS_CONFIG_PROFILE not set in .env",
            file=sys.stderr,
        )
        sys.exit(1)

    if not args.title:
        args.title = input("Genie space title: ").strip()
        if not args.title:
            print("Error: title is required", file=sys.stderr)
            sys.exit(1)

    os.environ["DATABRICKS_CONFIG_PROFILE"] = args.profile
    w = WorkspaceClient(profile=args.profile)

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
                    "identifier": "samples.nyctaxi.trips",
                    "column_configs": [
                        {
                            "column_name": "dropoff_zip",
                            "enable_format_assistance": True,
                        },
                        {
                            "column_name": "fare_amount",
                            "enable_format_assistance": True,
                        },
                        {"column_name": "pickup_zip", "enable_format_assistance": True},
                        {
                            "column_name": "tpep_dropoff_datetime",
                            "enable_format_assistance": True,
                        },
                        {
                            "column_name": "tpep_pickup_datetime",
                            "enable_format_assistance": True,
                        },
                        {
                            "column_name": "trip_distance",
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


if __name__ == "__main__":
    main()
