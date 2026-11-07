"""Remove only this run's identified synthetic services/container and anonymous volume."""

import json
import os
import re
import signal
import subprocess
import time
from pathlib import Path

root = Path.cwd()
assert root.name == "factory-studio-gw-company"
p = (
    root / os.environ.get("GW_BROWSER_REVIEW_WORK", "work/gw-readiness-02-phase80")
).resolve()
assert p.is_relative_to((root / "work").resolve()), "private work directory required"
s = json.loads((p / "state.json").read_text())
assert s["owner"] == "gw-ready-02-phase80" and re.fullmatch(
    "gw_browser_[0-9a-f]{32}_test", s["database"]
)
assert re.fullmatch("[0-9a-f]{64}", s["container"])
i = json.loads(subprocess.check_output(["docker", "inspect", s["container"]]))[0]
assert (
    i["Id"] == s["container"]
    and i["Config"]["Labels"]["factory-studio.owner"] == s["owner"]
)
assert i["HostConfig"]["PortBindings"] == {
    "5432/tcp": [{"HostIp": "127.0.0.1", "HostPort": "55480"}]
}
volumes = [x["Name"] for x in i["Mounts"] if x["Type"] == "volume"]
for key, fragment in [
    ("apiPid", "uvicorn fs.main:app --host 127.0.0.1 --port 8380"),
    ("webPid", str(root / "frontend/node_modules/vite/bin/vite.js")),
]:
    if key not in s:
        continue
    r = subprocess.run(
        ["ps", "-p", str(s[key]), "-o", "command="],
        capture_output=True,
        text=True,
        check=False,
    )
    if r.returncode:
        continue
    assert fragment in r.stdout, "PID is no longer owned; refuse signal"
    os.kill(s[key], signal.SIGTERM)
for _ in range(30):
    if all(
        subprocess.run(
            ["ps", "-p", str(s[k])], stdout=subprocess.DEVNULL, check=False
        ).returncode
        for k in ("apiPid", "webPid")
        if k in s
    ):
        break
    time.sleep(0.1)
subprocess.run(
    ["docker", "rm", "-fv", s["container"]], check=True, stdout=subprocess.DEVNULL
)
assert (
    subprocess.run(
        ["docker", "inspect", s["container"]],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    ).returncode
    != 0
)
for v in volumes:
    assert (
        subprocess.run(
            ["docker", "volume", "inspect", v],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=False,
        ).returncode
        != 0
    )
report = {
    "ownedContainerRemoved": True,
    "ownedDatabaseRemovedWithContainer": True,
    "ownedAnonymousVolumesRemoved": len(volumes),
    "previewDatabaseAccessed": False,
    "runtimeLeftRunning": True,
}
(p / "cleanup.json").write_text(json.dumps(report))
print(json.dumps(report))
