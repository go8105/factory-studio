"""FS-017c: exclusive browser smoke on factory_studio_fs017_test only.

Run from repository root through uv --env-file .env. The fixed test database is
reset before each run; the application database from .env is never modified.
"""

from __future__ import annotations

import os
import secrets
import socket
import subprocess
import sys
import time
from datetime import date
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from seed.generate import create_template
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

# 템플릿·게스트 복사 기준일. 실제 날짜와 무관하게 e2e의 날짜가 유효하다(FS_TODAY로 서버에 전달).
SMOKE_DATE = date(2026, 9, 24)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    node_major = subprocess.check_output(["node", "--version"], text=True).strip()
    if not node_major.startswith("v24."):
        raise SystemExit("Node 24 PATH is required")
    # 기존 개발 서버를 잘못 테스트하거나 종료하지 않는다.
    api_port = int(os.environ.get("FS_SMOKE_API_PORT", "8000"))
    web_port = int(os.environ.get("FS_SMOKE_WEB_PORT", "5173"))
    if not all(1024 <= p <= 65535 for p in (api_port, web_port)) or api_port == web_port:
        raise SystemExit("Use distinct unprivileged smoke ports")
    db_name = os.environ.get("FS_SMOKE_DB", "factory_studio_fs017_test")
    if db_name != "factory_studio_fs017_test" and not (db_name.startswith("factory_studio_codex_") and db_name.endswith("_test") and db_name.replace("_", "").isalnum()):
        raise SystemExit("Use a dedicated factory_studio_codex_*_test DB")
    for port in (api_port, web_port):
        with socket.socket() as probe:
            # 직전 실행의 TIME_WAIT 소켓은 무시하고, 실제로 LISTEN 중인 서버만 막는다.
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError as error:
                raise SystemExit(f"Stop the existing server on port {port}") from error
    url = make_url(os.environ["DATABASE_URL"]).set(database=db_name)
    assert url.database == db_name
    env = {
        **os.environ,
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "SESSION_SECRET": secrets.token_urlsafe(48),
        "FS_SMOKE_API_PORT": str(api_port),
        "FS_SMOKE_WEB_PORT": str(web_port),
        # 테스트마다 새 게스트를 만든다. 제품 기본 상한(20)과 무관하게 스모크 전체를 수용한다.
        "GUEST_LIMIT": "400",  # 스모크는 테스트마다 새 게스트 공간(약 230개)
        # 템플릿과 게스트 복사 기준일을 고정한다. e2e의 날짜(09-07 결측, 8월 요금제 등)가 매일 유효하다.
        "FS_TODAY": SMOKE_DATE.isoformat(),
    }
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if not connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:name"),
            {"name": url.database},
        ).scalar():
            connection.execute(text("CREATE DATABASE " + db_name))
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
        _, _, counts = create_template(connection, SMOKE_DATE)
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
                str(api_port),
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
                        f"http://127.0.0.1:{api_port}/api/v1/core/sessions/current", timeout=1
                    ).close()
                except HTTPError as error:
                    if error.code == 401:
                        break
                except URLError:
                    pass
                time.sleep(0.1)
            else:
                raise RuntimeError("Backend startup timed out")
            # 인자를 주면 Playwright에 넘긴다(예: e2e/wms.spec.ts). 공식 스모크는 인자 없이 전체를 돌린다.
            extra = ["--", *sys.argv[1:]] if sys.argv[1:] else []
            subprocess.run(
                ["npm", "--prefix", "frontend", "run", "test:e2e", *extra],
                env=env,
                check=True,
            )
        finally:
            import signal

            os.killpg(server.pid, signal.SIGTERM)
            server.wait(timeout=15)


if __name__ == "__main__":
    main()
