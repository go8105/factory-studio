from __future__ import annotations

import argparse
import os
from datetime import date

from sqlalchemy import create_engine

from seed.copy import copy_template
from seed.generate import create_template
from seed.validate import validate_all


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Factory Studio deterministic seed generator"
    )
    parser.add_argument("command", choices=("template", "copy", "validate"))
    parser.add_argument("--date", type=date.fromisoformat, required=True)
    parser.add_argument("--source-workspace", type=int)
    parser.add_argument("--source-generation", type=int)
    parser.add_argument("--workspace", type=int)
    parser.add_argument("--generation", type=int)
    parser.add_argument("--guest-session-key", default="fs015-cli-guest")
    args = parser.parse_args()
    engine = create_engine(os.environ["DATABASE_URL"])
    with engine.begin() as connection:
        if args.command == "template":
            print(create_template(connection, args.date))
        elif args.command == "copy":
            if args.source_workspace is None or args.source_generation is None:
                parser.error("copy requires --source-workspace and --source-generation")
            print(
                copy_template(
                    connection,
                    args.source_workspace,
                    args.source_generation,
                    args.date,
                    args.guest_session_key,
                )
            )
        else:
            if args.workspace is None or args.generation is None:
                parser.error("validate requires --workspace and --generation")
            for key, value in validate_all(
                connection, args.workspace, args.generation, args.date
            ).items():
                print(f"{key}: {value}")


if __name__ == "__main__":
    main()
