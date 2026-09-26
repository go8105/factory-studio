"""FS-021 로컬 성능 실측 (FS-012 §5-3): 게스트 복사 2초 · 첫 화면 3초 · 동시 게스트 20명.

전용 DB factory_studio_fs021_perf 와 전용 포트 8010을 쓴다(스모크 8000·5173·스모크 DB를 건드리지 않는다).
저장소 루트에서: uv run --project backend --env-file .env python tools/measure_fs021.py

- 복사: POST /guest-sessions 왕복 시간(템플릿 → 게스트 세대 복사 포함), 순차 10회.
- 첫 화면: 게스트 생성 직후 포털 홈이 부르는 API(sessions/current, workspace/modules)와
  세 솔루션 첫 화면 API(FEMS·MES·ERP dashboard)의 응답 시간. 브라우저 렌더·번들 다운로드는 포함하지 않는다.
- 동시 20명: 제품 기본 상한 GUEST_LIMIT=20 그대로 20개 스레드가 동시에 게스트 생성 → 세 대시보드 조회.
"""

from __future__ import annotations

import json
import os
import secrets
import signal
import statistics
import subprocess
import threading
import time
from datetime import date
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import HTTPCookieProcessor, Request, build_opener, urlopen
from uuid import uuid4

from seed.generate import create_template
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import make_url

BASE = "http://127.0.0.1:8010"
DB = "factory_studio_fs021_perf"
DAY = date(2026, 9, 24)
FIRST_SCREEN = [
    "/api/v1/core/sessions/current",
    "/api/v1/core/workspace/modules",
    "/api/v1/fems/dashboard",
    "/api/v1/mes/dashboard",
    "/api/v1/erp/dashboard",
]


def _prepare(env: dict[str, str]) -> None:
    url = make_url(env["DATABASE_URL"])
    admin = create_engine(url.set(database="postgres"), isolation_level="AUTOCOMMIT")
    with admin.connect() as connection:
        if not connection.execute(
            text("SELECT 1 FROM pg_database WHERE datname=:n"), {"n": DB}
        ).scalar():
            connection.execute(text(f"CREATE DATABASE {DB}"))
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
        stdout=subprocess.DEVNULL,
    )
    engine = create_engine(url)
    with engine.begin() as connection:
        names = [
            f'"{s}"."{t}"'
            for s in ("core", "mes", "erp", "fems")
            for t in inspect(connection).get_table_names(schema=s)
        ]
        connection.execute(text(f"TRUNCATE {','.join(names)} RESTART IDENTITY CASCADE"))
        create_template(connection, DAY)
    engine.dispose()


def _guest():
    """새 쿠키 저장소로 게스트를 만든다. (opener, 걸린 초)"""
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    started = time.perf_counter()
    request = Request(
        f"{BASE}/api/v1/core/guest-sessions",
        method="POST",
        headers={"Idempotency-Key": str(uuid4())},
    )
    with opener.open(request, timeout=60) as response:
        assert response.status == 201
    return opener, time.perf_counter() - started


def _get(opener, path: str) -> float:
    started = time.perf_counter()
    with opener.open(f"{BASE}{path}", timeout=60) as response:
        assert response.status == 200, path
        response.read()
    return time.perf_counter() - started


def _stats(values: list[float]) -> dict[str, float]:
    ordered = sorted(values)
    return {
        "n": len(values),
        "median": round(statistics.median(ordered), 3),
        "p95": round(ordered[max(0, round(len(ordered) * 0.95) - 1)], 3),
        "max": round(ordered[-1], 3),
    }


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    os.chdir(root)
    url = make_url(os.environ["DATABASE_URL"]).set(database=DB)
    env = {
        **os.environ,
        "DATABASE_URL": url.render_as_string(hide_password=False),
        "SESSION_SECRET": secrets.token_urlsafe(48),
        "COOKIE_SECURE": "false",
        "FS_TODAY": DAY.isoformat(),
        "GUEST_LIMIT": "40",  # 순차 10 + 동시 20. 동시 구간 직전에 20으로 되돌려 측정한다(아래)
    }
    _prepare(env)
    results: dict[str, object] = {}

    def serve(limit: str):
        return subprocess.Popen(
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
                "8010",
            ],
            env={**env, "GUEST_LIMIT": limit},
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True,
        )

    def wait_ready():
        for _ in range(200):
            try:
                urlopen(f"{BASE}/api/v1/core/sessions/current", timeout=1).close()
            except HTTPError as error:
                if error.code == 401:
                    return
            except URLError:
                pass
            time.sleep(0.1)
        raise RuntimeError("server did not start")

    def stop(server):
        os.killpg(server.pid, signal.SIGTERM)
        server.wait(timeout=15)

    # 1·2. 순차: 복사 시간과 첫 화면 API
    server = serve("40")
    try:
        wait_ready()
        copies, screens = [], {p: [] for p in FIRST_SCREEN}
        for _ in range(10):
            opener, seconds = _guest()
            copies.append(seconds)
            for path in FIRST_SCREEN:
                screens[path].append(_get(opener, path))
        results["guest_copy_seconds"] = _stats(copies)
        results["first_screen_seconds"] = {p: _stats(v) for p, v in screens.items()}
        results["first_screen_total_median"] = round(
            statistics.median(copies)
            + sum(statistics.median(v) for v in screens.values()),
            3,
        )
    finally:
        stop(server)

    # 3. 동시 20명: 제품 상한 20. 앞 구간 게스트를 지우고 새로 시작한다.
    engine = create_engine(url)
    with engine.begin() as connection:
        connection.execute(text("TRUNCATE core.workspace RESTART IDENTITY CASCADE"))
        create_template(connection, DAY)
    engine.dispose()
    server = serve("20")
    try:
        wait_ready()
        barrier = threading.Barrier(20)
        copies, pages, errors = [], [], []
        lock = threading.Lock()

        def user():
            barrier.wait()
            try:
                opener, seconds = _guest()
                times = [_get(opener, p) for p in FIRST_SCREEN[2:]]
                with lock:
                    copies.append(seconds)
                    pages.extend(times)
            except (OSError, AssertionError) as error:  # 실패도 결과로 기록한다
                with lock:
                    errors.append(repr(error)[:200])

        started = time.perf_counter()
        threads = [threading.Thread(target=user) for _ in range(20)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        results["concurrent_20"] = {
            "wall_seconds": round(time.perf_counter() - started, 3),
            "guest_copy_seconds": _stats(copies) if copies else None,
            "dashboard_seconds": _stats(pages) if pages else None,
            "errors": errors,
        }
    finally:
        stop(server)
    print(json.dumps(results, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
