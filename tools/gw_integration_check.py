"""Run GW regression only on a new owned PG18 test database; never load preview data."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from uuid import uuid4
from xml.etree import ElementTree

from sqlalchemy import URL, create_engine, text
from sqlalchemy.exc import SQLAlchemyError

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--container", required=True)
    parser.add_argument("--expected-id-file", type=Path, required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--port", type=int, required=True)
    parser.add_argument("--private-output", type=Path, required=True)
    parser.add_argument("--test-node", action="append", default=[])
    args = parser.parse_args()
    private = args.private_output.resolve()
    # Full logs/URLs must stay under the ignored local work directory.
    if not private.is_relative_to(ROOT / "work"):
        raise ValueError("private output must be under repository work/")
    private.mkdir(parents=True, exist_ok=True, mode=0o700)
    private.chmod(0o700)
    expected = args.expected_id_file.read_text().strip()
    if not re.fullmatch(r"[0-9a-f]{64}", expected):
        raise ValueError("full container ID required")

    def owned():
        value = json.loads(
            subprocess.check_output(["docker", "inspect", args.container])
        )[0]
        if not (
            value["Id"] == expected
            and value["State"]["Running"]
            and value["Config"]["Labels"].get("factory-studio.owner") == args.owner
            and value["NetworkSettings"]["Ports"]["5432/tcp"]
            == [{"HostIp": "127.0.0.1", "HostPort": str(args.port)}]
        ):
            raise ValueError("owned container/loopback identity mismatch")
        return value

    container = owned()
    settings = dict(
        item.split("=", 1) for item in container["Config"]["Env"] if "=" in item
    )
    url = URL.create(
        "postgresql+psycopg",
        username=settings.get("POSTGRES_USER", "postgres"),
        password=settings["POSTGRES_PASSWORD"],
        host="127.0.0.1",
        port=args.port,
        database="postgres",
    )
    admin = create_engine(url, isolation_level="AUTOCOMMIT")
    database = "gw_integration_" + uuid4().hex + "_test"
    env = {
        k: v
        for k, v in os.environ.items()
        if not k.startswith(("FS_GW_", "FS_SECURITY_"))
        and k not in {"DATABASE_URL", "TEST_DATABASE_URL"}
    }
    target = url.set(database=database).render_as_string(hide_password=False)
    env.update(
        DATABASE_URL=target,
        TEST_DATABASE_URL=target,
        GW_BACKUP_TEST_CONTAINER=args.container,
        FS_GW_ROUTE_VERIFY_OWNER=args.owner,
        FS_GW_ROUTE_VERIFY_ADMIN_URL=url.render_as_string(hide_password=False),
    )
    report = {
        "kind": "GW_BRANCH_REGRESSION",
        "signedEvidence": False,
        "ready": False,
        "liveCompanyAcceptance": False,
        "releaseAuthorized": False,
        "database": database,
        "createdDatabaseRemoved": False,
        "stages": [],
    }
    created = False

    def stage(name, command):
        log = private / (name + ".log")
        with log.open("wb") as output:
            log.chmod(0o600)
            result = subprocess.run(
                command,
                cwd=ROOT,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
                check=False,
            )
        report["stages"].append({"name": name, "exitCode": result.returncode})
        print(f"{name}: exit {result.returncode}", flush=True)
        return result.returncode

    try:
        with admin.connect() as connection:
            if connection.scalar(text("SHOW server_version_num"))[:2] != "18":
                raise ValueError("PG18 required")
            before = set(connection.scalars(text("SELECT datname FROM pg_database")))
            connection.exec_driver_sql(
                f'CREATE DATABASE "{database}" TEMPLATE template0'
            )
            created = True
        print("Owned PG18 verified; new UUID test database created", flush=True)
        if stage(
            "migration",
            [
                sys.executable,
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "upgrade",
                "head",
            ],
        ):
            return 1
        if stage(
            "ddl",
            [
                sys.executable,
                "tools/verify_ddl_matches_schema.py",
                "--output",
                str(private / "ddl.json"),
            ],
        ):
            return 1
        tests = args.test_node or sorted(
            str(p.relative_to(ROOT))
            for p in (ROOT / "backend/tests").glob("test_gw*.py")
        )
        for node in tests:
            selected = (ROOT / node.split("::", 1)[0]).resolve()
            if (
                selected.parent != ROOT / "backend/tests"
                or not selected.name.startswith("test_gw")
                or selected.suffix != ".py"
                or not selected.is_file()
            ):
                raise ValueError("only repository GW test nodes allowed")
        report["testFiles"] = len({node.split("::", 1)[0] for node in tests})
        report["fullGwSelection"] = not bool(args.test_node)
        junit = private / "pytest.xml"
        code = stage(
            "gw-pytest",
            [
                sys.executable,
                "-m",
                "pytest",
                *tests,
                "-q",
                "-x",
                "--tb=short",
                f"--junitxml={junit}",
            ],
        )
        if junit.exists():
            suites = ElementTree.parse(junit).getroot()
            cases = list(suites.iter("testcase"))
            report["pytest"] = {
                "collectedExecuted": len(cases),
                "failures": sum(c.find("failure") is not None for c in cases),
                "errors": sum(c.find("error") is not None for c in cases),
                "skipped": sum(c.find("skipped") is not None for c in cases),
            }
            report["pytest"]["passed"] = len(cases) - sum(
                report["pytest"][k] for k in ("failures", "errors", "skipped")
            )
            print("pytest counts: " + json.dumps(report["pytest"]), flush=True)
        with admin.connect() as connection:
            after = set(connection.scalars(text("SELECT datname FROM pg_database")))
        report["unexpectedNewDatabaseCount"] = len(after - before - {database})
        if report["unexpectedNewDatabaseCount"]:
            print(
                "Unexpected new databases remain; do not delete unowned resources",
                flush=True,
            )
            return 1
        return 0 if code == 0 else 1
    finally:
        if created:
            owned()
            with admin.connect() as connection:
                connection.exec_driver_sql(f'DROP DATABASE "{database}" WITH (FORCE)')
                report["createdDatabaseRemoved"] = not connection.scalar(
                    text(
                        "SELECT EXISTS(SELECT 1 FROM pg_database WHERE datname=:name)"
                    ),
                    {"name": database},
                )
        admin.dispose()
        (private / "summary.json").write_text(json.dumps(report, indent=2) + "\n")
        (private / "summary.json").chmod(0o600)
        print(
            "Created test database removed: " + str(report["createdDatabaseRemoved"]),
            flush=True,
        )


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, SQLAlchemyError, subprocess.SubprocessError) as error:
        # Connection strings and full test tracebacks are intentionally not printed.
        print("GW integration check stopped: " + type(error).__name__, file=sys.stderr)
        raise SystemExit(1) from None
