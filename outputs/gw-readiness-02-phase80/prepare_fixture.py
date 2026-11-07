"""Disposable phase80 reproduction fixture; no production or preview DB access."""

import base64
import json
import os
import secrets
import socket
import subprocess
import sys
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import URL, create_engine, text

root = Path.cwd()
assert root.name == "factory-studio-gw-company" and (root / "AGENTS.md").exists()
assert sys.argv[1:] == ["--prepare-owned-synthetic"]
p = (
    root / os.environ.get("GW_BROWSER_REVIEW_WORK", "work/gw-readiness-02-phase80")
).resolve()
assert p.is_relative_to((root / "work").resolve()), "private work directory required"
p.mkdir(mode=0o700, exist_ok=True)
p.chmod(0o700)
assert not (p / "state.json").exists(), (
    "existing run must be cleaned and archived first"
)
for port in (55480, 8380, 5380):
    check = socket.socket()
    check.bind(("127.0.0.1", port))
    check.close()
owner = "gw-ready-02-phase80"
name = "fs-gw-phase80-" + uuid4().hex[:8]
db = "gw_browser_" + uuid4().hex + "_test"
env = {
    k: v
    for (k, v) in os.environ.items()
    if not k.startswith(("FS_GW_", "FS_SECURITY_"))
    and k not in {"DATABASE_URL", "TEST_DATABASE_URL"}
}
password = secrets.token_urlsafe(36)
runenv = dict(env, POSTGRES_PASSWORD=password)
cid = (
    subprocess.check_output(
        [
            "docker",
            "run",
            "-d",
            "--name",
            name,
            "--label",
            "factory-studio.owner=" + owner,
            "-e",
            "POSTGRES_PASSWORD",
            "-p",
            "127.0.0.1:55480:5432",
            "postgres:18",
        ],
        env=runenv,
    )
    .decode()
    .strip()
)
state = {
    "container": cid,
    "name": name,
    "owner": owner,
    "database": db,
    "port": 55480,
    "apiPort": 8380,
    "webPort": 5380,
}
(p / "state.json").write_text(json.dumps(state))
(p / "state.json").chmod(0o600)


def owned():
    i = json.loads(subprocess.check_output(["docker", "inspect", cid]))[0]
    assert (
        i["Id"] == cid
        and i["State"]["Running"]
        and (i["Config"]["Labels"]["factory-studio.owner"] == owner)
    )
    assert i["NetworkSettings"]["Ports"]["5432/tcp"] == [
        {"HostIp": "127.0.0.1", "HostPort": "55480"}
    ]


owned()
for _ in range(60):
    if (
        subprocess.run(
            ["docker", "exec", cid, "pg_isready", "-h", "127.0.0.1", "-U", "postgres"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        == 0
    ):
        break
    time.sleep(0.5)
url = URL.create(
    "postgresql+psycopg",
    username="postgres",
    password=password,
    host="127.0.0.1",
    port=55480,
    database="postgres",
)
a = create_engine(url, isolation_level="AUTOCOMMIT")
from tools.gw_integration_check import clock_preflight

with a.connect() as c:
    clock = clock_preflight(c)
    assert clock["stableSample"], "clock guard blocked"
    c.exec_driver_sql('CREATE DATABASE "' + db + '"')
a.dispose()
(p / "clock.json").write_text(json.dumps(clock))
env.update(
    DATABASE_URL=url.set(database=db).render_as_string(hide_password=False),
    TEST_DATABASE_URL=url.set(database=db).render_as_string(hide_password=False),
    SESSION_SECRET=secrets.token_urlsafe(48),
    COOKIE_SECURE="false",
    FS_SECURITY_MODE="TEAM_TEST",
    FS_SECURITY_KEY_ID="browser80",
    FS_SECURITY_KEYS=json.dumps(
        {"browser80": base64.urlsafe_b64encode(secrets.token_bytes(32)).decode()}
    ),
    FS_PUBLIC_ORIGIN="http://localhost:5380",
    FS_SMOKE_API_PORT="8380",
    FS_SMOKE_WEB_PORT="5380",
)
(p / "env.json").write_text(
    json.dumps(
        {
            k: v
            for (k, v) in env.items()
            if k
            in {
                "DATABASE_URL",
                "TEST_DATABASE_URL",
                "SESSION_SECRET",
                "COOKIE_SECURE",
                "FS_SECURITY_MODE",
                "FS_SECURITY_KEY_ID",
                "FS_SECURITY_KEYS",
                "FS_PUBLIC_ORIGIN",
                "FS_SMOKE_API_PORT",
                "FS_SMOKE_WEB_PORT",
            }
        }
    )
)
(p / "env.json").chmod(0o600)
with (p / "migration.log").open("w") as f:
    assert (
        subprocess.run(
            [
                str(root / "backend/.venv/bin/python"),
                "-m",
                "alembic",
                "-c",
                "backend/alembic.ini",
                "upgrade",
                "head",
            ],
            env=env,
            stdout=f,
            stderr=subprocess.STDOUT,
            check=False,
        ).returncode
        == 0
    ), "migration failed; private log"
os.environ.update(env)
from datetime import date

import pyotp
from fastapi.testclient import TestClient
from fs.core.security.config import security_settings
from fs.hr.work_setup import create_company
from fs.main import create_app
from seed.generate import create_template

engine = create_engine(env["DATABASE_URL"])
pw = secrets.token_urlsafe(30)
with engine.begin() as c:
    create_template(c, date(2026, 11, 7))
    co = create_company(
        c,
        {
            "companyName": "합성 GW 격리 브라우저 검증",
            "loginId": "admin",
            "name": "합성 관리자",
            "password": pw,
            "employeeCode": "SYN-001",
            "workStart": "09:00",
            "dailyMinutes": 480,
            "breakMinutes": 60,
            "annualDays": 15,
        },
    )
c = TestClient(create_app())
r = c.post(
    "/api/v1/core/sessions",
    json={"loginId": "admin", "password": pw},
    headers={"Idempotency-Key": str(uuid4())},
)
assert r.status_code == 201
csrf = r.json()["data"]["csrfToken"]


def api(path, body=None, method="POST"):
    r = c.request(
        method,
        "/api/v1/gw/" + path,
        params={"companyId": co["companyId"]},
        json=body,
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
    )
    assert r.status_code == 200, (path, r.status_code, r.text[:400])
    return r.json()["data"]


person = api(
    "company-setup", {"employeeCode": "SYN-001", "reason": "합성 격리 시험 준비"}
)["personId"]
r = c.post(
    "/api/v1/hr/work/users",
    params={"companyId": co["companyId"]},
    json={
        "loginId": "synthetic-staff",
        "password": pw,
        "name": "합성 직원",
        "employeeCode": "SYN-002",
        "annualDays": 15,
        "role": "STAFF",
    },
    headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
)
assert r.status_code == 200, r.text[:400]
preview = api("company-hr-preview", method="GET")
api(
    "company-hr-import",
    {
        "previewDigest": preview["digest"],
        "employeeCodes": ["SYN-002"],
        "reason": "합성 직원 가져오기",
    },
)
with engine.begin() as conn:
    uid = conn.scalar(
        text("SELECT id FROM core.app_user WHERE login_id='synthetic-staff'")
    )
    pid = conn.scalar(
        text(
            "SELECT id FROM gw.person WHERE workspace_id=:w AND hr_employee_code='SYN-002'"
        ),
        {"w": co["companyId"]},
    )
    conn.execute(
        text(
            "UPDATE core.auth_session SET assurance='MFA',verified_at=clock_timestamp() WHERE user_id=:u"
        ),
        {"u": co["userId"]},
    )
b = api(
    "identity-bindings",
    {"personId": str(pid), "userId": str(uid), "reason": "합성 본인 연결 요청"},
)
s = TestClient(create_app())
r = s.post(
    "/api/v1/core/sessions",
    json={"loginId": "synthetic-staff", "password": pw},
    headers={"Idempotency-Key": str(uuid4())},
)
assert r.status_code == 201
r = s.post(
    "/api/v1/gw/me/binding/accept",
    params={"companyId": co["companyId"]},
    json={"bindingId": b["id"], "expectedVersion": b["version"]},
    headers={
        "X-CSRF-Token": r.json()["data"]["csrfToken"],
        "Idempotency-Key": str(uuid4()),
    },
)
assert r.status_code == 200, r.text[:400]
api(
    "operating-policies",
    {
        "expectedVersion": 0,
        "policy": {"responsiblePersonId": str(person), "reason": "합성 운영 준비 기준"},
    },
)
credentials = {
    "companyId": co["companyId"],
    "bindingId": b["id"],
    "admin": {"login": "admin", "password": pw},
    "staff": {"login": "synthetic-staff", "password": pw},
}
with engine.begin() as conn:
    for key, user in [("admin", co["userId"]), ("staff", uid)]:
        secret = pyotp.random_base32()
        (kid, encrypted) = security_settings().box.seal(
            secret, purpose="totp", owner=str(user)
        )
        credentials[key]["setupKey"] = secret
        conn.execute(
            text(
                "INSERT INTO core.mfa_factor(user_id,kind,state,secret_ciphertext,encryption_key_id,version,confirmed_at,created_at) VALUES(:u,'TOTP','ACTIVE',:s,:k,1,clock_timestamp(),clock_timestamp())"
            ),
            {"u": user, "s": encrypted, "k": kid},
        )
    conn.execute(
        text(
            "UPDATE core.auth_session SET revoked_at=clock_timestamp() WHERE revoked_at IS NULL"
        )
    )
c.close()
s.close()
engine.dispose()
(p / "credentials.json").write_text(json.dumps(credentials))
(p / "credentials.json").chmod(0o600)
for label, cmd, cwd in [
    (
        "api",
        [
            str(root / "backend/.venv/bin/python"),
            "-m",
            "uvicorn",
            "fs.main:app",
            "--host",
            "127.0.0.1",
            "--port",
            "8380",
        ],
        root,
    ),
    (
        "web",
        [
            "/opt/homebrew/opt/node@24/bin/node",
            str(root / "frontend/node_modules/vite/bin/vite.js"),
            "--host",
            "localhost",
            "--port",
            "5380",
        ],
        root / "frontend",
    ),
]:
    f = (p / (label + ".log")).open("w")
    proc = subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=f,
        stderr=subprocess.STDOUT,
        start_new_session=True,
    )
    state[label + "Pid"] = proc.pid
(p / "state.json").write_text(json.dumps(state))
print(
    json.dumps(
        {
            "prepared": True,
            "synthetic": True,
            "companyId": co["companyId"],
            "connected": 2,
            "planned": 10,
            "realApi": True,
            "mode": "TEAM_TEST",
            "mfaEnrollment": "SYNTHETIC_FIXTURE",
            "ready": False,
            "credentialsPrinted": False,
        }
    )
)
