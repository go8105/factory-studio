"""Actual API control of this new disposable synthetic fixture only."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import httpx
import pyotp

root = Path.cwd()
assert root.name == "factory-studio-gw-company"
p = (
    root / os.environ.get("GW_BROWSER_REVIEW_WORK", "work/gw-readiness-02-phase80")
).resolve()
assert p.is_relative_to((root / "work").resolve()), "private work directory required"
s = json.loads((p / "state.json").read_text())
v = json.loads((p / "credentials.json").read_text())
assert (
    s["owner"] == "gw-ready-02-phase80"
    and s["database"].startswith("gw_browser_")
    and s["database"].endswith("_test")
)
i = json.loads(subprocess.check_output(["docker", "inspect", s["container"]]))[0]
assert (
    i["Id"] == s["container"]
    and i["State"]["Running"]
    and (i["Config"]["Labels"]["factory-studio.owner"] == s["owner"])
)
assert i["NetworkSettings"]["Ports"]["5432/tcp"] == [
    {"HostIp": "127.0.0.1", "HostPort": "55480"}
]
command = subprocess.check_output(
    ["ps", "-p", str(s["apiPid"]), "-o", "command="]
).decode()
assert "uvicorn fs.main:app --host 127.0.0.1 --port 8380" in command
c = httpx.Client(base_url="http://127.0.0.1:8380")
cp = p / "control-cookies.json"
if cp.exists():
    a = json.loads(cp.read_text())
    c.cookies.update(a["cookies"])
    csrf = a["csrf"]
else:
    r = c.post(
        "/api/v1/core/sessions",
        json={"loginId": v["admin"]["login"], "password": v["admin"]["password"]},
        headers={"Idempotency-Key": str(uuid4())},
    )
    assert r.status_code == 202
    r = c.post(
        "/api/v1/core/security/login/verify",
        json={"code": pyotp.TOTP(v["admin"]["setupKey"]).now()},
        headers={"X-CSRF-Token": r.json()["data"]["challengeCsrfToken"]},
    )
    assert r.status_code == 201, (r.status_code, "MFA control failed")
    csrf = r.json()["data"]["csrfToken"]
    cp.write_text(json.dumps({"cookies": dict(c.cookies), "csrf": csrf}))
    cp.chmod(0o600)


def api(path, body=None, method="POST"):
    r = c.request(
        method,
        "/api/v1/gw/" + path,
        params={"companyId": v["companyId"]},
        json=body,
        headers={"X-CSRF-Token": csrf, "Idempotency-Key": str(uuid4())},
    )
    assert r.status_code in (200, 201), (path, r.status_code, r.text[:300])
    return r.json()["data"]


mode = sys.argv[1]
if mode == "audit":
    ops = api("operations", method="GET")
    rows = api("identity-bindings", method="GET")["items"]
    binding = next(x for x in rows if str(x["id"]) == str(v["bindingId"]))
    doc = api("documents/" + str(v["documentId"]), method="GET")
    report = {
        "ready": ops["ready"],
        "unverifiedCount": ops["launchGate"]["unverifiedCount"],
        "connectedPeople": ops["connectedPeople"],
        "adminOriginalRead": doc["body"] == "합성 비공개 대조 원문",
        "staffBindingState": binding["state"],
        "synthetic": True,
        "signedEvidence": False,
    }
    (p / "actual-api-audit.json").write_text(json.dumps(report))
    print(json.dumps(report))
elif mode == "document":
    assert "documentId" not in v, "document fixture already prepared"
    staff = next(
        x for x in api("people-options", method="GET") if x["name"] == "합성 직원"
    )
    route = api(
        "routes",
        {
            "code": "SYN-BROWSER-STAFF",
            "name": "합성 초안 대조",
            "steps": [
                {"personId": staff["id"], "seq": 1, "participantRole": "APPROVER"}
            ],
        },
    )
    doc = api(
        "documents",
        {
            "kind": "GENERAL",
            "routeId": route["id"],
            "title": "합성 관리자 전용 대조",
            "body": "합성 비공개 대조 원문",
        },
    )
    v["documentId"] = doc["id"]
    (p / "credentials.json").write_text(json.dumps(v))
    print(json.dumps({"createdSyntheticDocument": True, "documentId": doc["id"]}))
elif mode in ("suspend", "resume"):
    result = api("identity-bindings", method="GET")
    rows = result["items"] if isinstance(result, dict) and "items" in result else result
    b = next(x for x in rows if str(x["id"]) == str(v["bindingId"]))
    r = api(
        "identity-bindings/" + str(b["id"]) + "/" + mode,
        {
            "expectedVersion": b["version"],
            "reason": "별도 소유 브라우저 합성 연결 검증",
        },
    )
    print(
        json.dumps(
            {
                "operation": mode,
                "state": r["state"],
                "version": r["version"],
                "synthetic": True,
            }
        )
    )
else:
    raise ValueError("unknown control")
c.close()
