"""W0-3 배포 스크립트 계약: 가짜 ssh·rsync·npm·curl·gh로 tools/deploy.sh를 실제로 실행한다.

서버에 접속하지 않는다. 확인하는 것: 순서(코드 → 마이그레이션 → 시드 → 재시작 → **프런트 업로드** → 확인),
서버 커밋이 다르면 중단, CI가 통과하지 않으면 서버를 건드리지 않음, 시드 버전이 같으면 템플릿 유지.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "tools/deploy.sh"

SSH_STUB = """#!/usr/bin/env bash
echo "ssh $*" >> "$FS_LOG"
case "$*" in
  *"git merge --ff-only"*) touch "$FS_STATE/merged" ;;
  *"git rev-parse HEAD"*)
    if [ -f "$FS_STATE/merged" ] && [ ! -f "$FS_STATE/stuck" ]; then cat "$FS_STATE/new_sha"; else cat "$FS_STATE/old_sha"; fi ;;
  *"git status --porcelain"*) : ;;
  *SEED_VERSION*) cat "$FS_STATE/code_seed" ;;
  *psql*) cat "$FS_STATE/db_seed" ;;
  *"is-active"*) exit 0 ;;
  *curl*) echo 200 ;;
  *verify_ddl_matches_schema*) echo '{"errors": []}' ;;
  *"grep -c"*) echo 0 ;;
  *) : ;;
esac
"""

STUBS = {
    "rsync": '#!/usr/bin/env bash\necho "rsync $*" >> "$FS_LOG"\n',
    "curl": '#!/usr/bin/env bash\necho "curl $*" >> "$FS_LOG"\necho 200\n',
    "gh": '#!/usr/bin/env bash\necho "gh $*" >> "$FS_LOG"\ncat "$FS_STATE/ci"\n',
    "npm": """#!/usr/bin/env bash
echo "npm $*" >> "$FS_LOG"
case "$*" in *"run build"*) mkdir -p frontend/dist && echo ok > frontend/dist/index.html ;; esac
""",
}


class DeployScriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fs-deploy-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, body in {"ssh": SSH_STUB, **STUBS}.items():
            path = self.bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.log = self.tmp / "log"
        self.log.write_text("", encoding="utf-8")
        # 가짜 저장소: main 브랜치 + bare origin. 실제 저장소 상태와 무관하게 돌린다.
        self.origin = self.tmp / "origin.git"
        self.repo = self.tmp / "repo"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.origin)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        (self.repo / "tools").mkdir()
        shutil.copy(DEPLOY, self.repo / "tools/deploy.sh")
        (self.repo / "frontend").mkdir()
        (self.repo / "frontend/package.json").write_text("{}\n", encoding="utf-8")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "test")
        self._git("add", "-A")
        self._git("commit", "-qm", "test")
        self._git("remote", "add", "origin", str(self.origin))
        self._git("push", "-q", "-u", "origin", "main")
        self.sha = self._git("rev-parse", "HEAD", capture=True)
        (self.state / "new_sha").write_text(self.sha + "\n", encoding="utf-8")
        (self.state / "old_sha").write_text("0" * 40 + "\n", encoding="utf-8")
        (self.state / "code_seed").write_text("sv-test-1\n", encoding="utf-8")
        (self.state / "db_seed").write_text("sv-test-1\n", encoding="utf-8")
        (self.state / "ci").write_text("completed success\n", encoding="utf-8")

    def _git(self, *args, capture=False):
        result = subprocess.run(["git", "-C", str(self.repo), *args], check=True, capture_output=True, text=True)
        return result.stdout.strip() if capture else None

    def _run(self, *args):
        env = {
            **os.environ,
            "PATH": f"{self.bin}:{os.environ['PATH']}",
            "FS_DEPLOY_NODE_BIN": str(self.bin),
            "FS_LOG": str(self.log),
            "FS_STATE": str(self.state),
            "FS_DEPLOY_HOST": "deploy@test.invalid",
            "FS_DEPLOY_SITE": "test.invalid",
        }
        return subprocess.run(
            ["bash", str(self.repo / "tools/deploy.sh"), *args],
            capture_output=True, text=True, env=env, cwd=str(self.repo),
        )

    def _commands(self):
        return self.log.read_text(encoding="utf-8")

    def test_deploy_runs_every_step_in_order(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self._commands()
        order = ["git merge --ff-only", "uv sync", "alembic", "SEED_VERSION", "systemctl restart", "rsync ", "verify_ddl_matches_schema"]
        positions = [log.find(step) for step in order]
        self.assertNotIn(-1, positions, log)
        self.assertEqual(positions, sorted(positions), log)
        self.assertIn("frontend/dist", log)  # 프런트 업로드 누락(2026-10-04) 재발 방지
        self.assertNotIn("seed.cli template", log)  # 시드 버전이 같으면 템플릿 유지
        self.assertIn("배포 완료", result.stdout)

    def test_new_seed_version_rebuilds_template(self):
        (self.state / "db_seed").write_text("sv-old-9\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("seed.cli template", self._commands())

    def test_stops_when_server_commit_differs(self):
        (self.state / "stuck").write_text("", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("서버 커밋이 다릅니다", result.stderr)
        self.assertNotIn("rsync ", self._commands())  # 프런트를 올리지 않는다

    def test_stops_before_touching_server_when_ci_is_not_green(self):
        (self.state / "ci").write_text("completed failure\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("CI가 통과하지 않았습니다", result.stderr)
        self.assertNotIn("ssh ", self._commands())

    def test_dry_run_builds_but_changes_nothing(self):
        result = self._run("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self._commands()
        self.assertIn("npm", log)
        for changing in ("git merge", "alembic", "systemctl restart", "rsync "):
            self.assertNotIn(changing, log)


if __name__ == "__main__":
    unittest.main()
