"""IntelliJ/터미널 공통 로컬 기동. 기존 DB/볼륨/계정은 보존한다."""

import fcntl
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args, quiet=False):
    return subprocess.run(args, cwd=ROOT, check=True, capture_output=quiet)


def prepare_db():
    (ROOT / "work").mkdir(exist_ok=True)
    with (ROOT / "work/local-db-start.lock").open("w") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        ready = (
            subprocess.run(
                ["docker", "info"], capture_output=True, cwd=ROOT, check=False
            ).returncode
            == 0
        )
        if not ready:
            context = (
                run("docker", "context", "show", quiet=True).stdout.decode().strip()
            )
            if context != "colima-factory-studio" or not shutil.which("colima"):
                raise RuntimeError(
                    "Docker를 먼저 실행하세요. 현재 Docker 환경은 자동 기동 대상이 아닙니다."
                )
            run("colima", "start", "--profile", "factory-studio")
        compose = ["docker", "compose"]
        if subprocess.run(
            [*compose, "version"], capture_output=True, check=False
        ).returncode:
            compose = ["docker-compose"]
        run(*compose, "up", "-d", "--wait", "db")
        from fs.common.db import get_engine
        from sqlalchemy import text
        from sqlalchemy.exc import SQLAlchemyError

        try:
            with get_engine().connect() as connection:
                connection.execute(text("SELECT 1"))
        except SQLAlchemyError, RuntimeError:
            raise RuntimeError(
                "DB 접속 확인 실패: .env의 DATABASE_URL과 DB 기동 상태를 확인하세요."
            ) from None
        print("로컬 DB 준비 완료", flush=True)


def main():
    target = sys.argv[1] if len(sys.argv) == 2 else ""
    if target not in {"db", "backend", "frontend"}:
        raise RuntimeError("사용법: start_local.py db|backend|frontend")
    os.chdir(ROOT)
    prepare_db()
    if target == "backend":
        print("백엔드: http://localhost:8000", flush=True)
        os.execvp(
            "uv",
            [
                "uv",
                "run",
                "--project",
                "backend",
                "--env-file",
                ".env",
                "uvicorn",
                "fs.main:app",
                "--host",
                "localhost",
                "--port",
                "8000",
                "--reload",
                "--reload-dir",
                "backend/src",
            ],
        )
    elif target == "frontend":
        node24 = Path("/opt/homebrew/opt/node@24/bin")
        if node24.exists():
            os.environ["PATH"] = str(node24) + os.pathsep + os.environ.get("PATH", "")
        print("프런트: http://localhost:5173", flush=True)
        os.execvp(
            "npm",
            [
                "npm",
                "--prefix",
                "frontend",
                "run",
                "dev",
                "--",
                "--host",
                "localhost",
                "--port",
                "5173",
            ],
        )


if __name__ == "__main__":
    try:
        main()
    except (RuntimeError, subprocess.CalledProcessError, FileNotFoundError) as error:
        print(f"로컬 기동 실패: {error}", file=sys.stderr)
        sys.exit(1)
