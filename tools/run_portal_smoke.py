"""FS-017c: exclusive browser smoke on factory_studio_fs017_test only.

Run from repository root through uv --env-file .env. The fixed test database is
reset before each run; the application database from .env is never modified.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import time
from datetime import datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen
from zoneinfo import ZoneInfo

from seed.generate import create_template
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    node_major = subprocess.check_output(["node", "--version"], text=True).strip()
    if not node_major.startswith("v24."):
        raise SystemExit("Node 24 PATH is required")
    # 기존 개발 서버를 잘못 테스트하거나 종료하지 않는다.
    for port in (8000, 5173):
        with socket.socket() as probe:
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                raise SystemExit(f"Stop the existing server on port {port}") from error
    url = make_url(os.environ["DATABASE_URL"]).set(database="factory_studio_fs017_test")
    assert url.database == "factory_studio_fs017_test"
    env = {
        **os.environ,
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "SESSION_SECRET": secrets.token_urlsafe(48),
        # 테스트마다 새 게스트를 만든다. 제품 기본 상한(20)과 무관하게 스모크 전체를 수용한다.
        "GUEST_LIMIT": "200",
    }
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if not connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:name"),
            {"name": url.database},
        ).scalar():
            connection.execute(text("CREATE DATABASE factory_studio_fs017_test"))
    admin.dispose()
    subprocess.run(
        [
            "uv",
            "run",
            "--project",
            "backend",
            "alembic",
            "-c",
            "backend/alembic.ini",
            "upgrade",
            "head",
        ],
        env=env,
        check=True,
    )
    engine = create_engine(url)
    with engine.begin() as connection:
        names = [
            f'"{schema}"."{table}"'
            for schema in ("core", "mes", "erp", "fems")
            for table in inspect(connection).get_table_names(schema=schema)
        ]
        connection.execute(text(f"TRUNCATE {','.join(names)} RESTART IDENTITY CASCADE"))
        _, _, counts = create_template(
            connection, datetime.now(ZoneInfo("Asia/Seoul")).date()
        )
        print(
            f"DB={url.database}; PostgreSQL={connection.execute(text('SHOW server_version')).scalar_one()}; template={sum(counts.values())}",
            flush=True,
        )
    engine.dispose()
    log_path = root / "work/fs017c/backend-smoke.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("w") as log:
        server = subprocess.Popen(
            [
                "uv",
                "run",
                "--project",
                "backend",
                "uvicorn",
                "fs.main:app",
                "--host",
                "127.0.0.1",
                "--port",
                "8000",
            ],
            env=env,
            stdout=log,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        try:
            for _ in range(100):
                if server.poll() is not None:
                    raise RuntimeError(
                        "Backend exited; see work/fs017c/backend-smoke.log"
                    )
                try:
                    urlopen(
                        "http://127.0.0.1:8000/api/v1/core/sessions/current", timeout=1
                    ).close()
                except HTTPError as error:
                    if error.code == 401:
                        break
                except URLError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Backend startup timed out")
            subprocess.run(
                ["npm", "--prefix", "frontend", "run", "test:e2e"], env=env, check=True
            )
        finally:
            import signal

            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=15)


if __name__ == "__main__":
    main()
