"""맥북 배포 스크립트 계약(HYUDO-04): 가짜 docker·uv·npm·curl·gh·launchctl로 tools/deploy.sh를 실제로 실행한다.

운영 DB·API·Nginx는 건드리지 않는다. 확인하는 것: 순서(백업 → 전환 → 빌드 → 마이그레이션 → 시드 → 재시작 → 확인),
CI가 통과하지 않거나 운영 폴더가 더러우면 아무것도 바꾸지 않음, 비공개 자산 누락 시 마이그레이션 전에 멈춤,
시드 버전이 같으면 템플릿 유지.
"""

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEPLOY = ROOT / "tools/deploy.sh"
PRIVATE = "soap-poc.html research-notebook.html soap-poc/assembly-v3.json soap-poc/research-history.json soap-poc/soap-poc-03.zip soap-poc/drawer-v3.stl"

STUBS = {
    "docker": """#!/usr/bin/env bash
echo "docker $*" >> "$FS_LOG"
case "$*" in
  *pg_dump*) echo dump ;;
  *seed_version*) cat "$FS_STATE/db_seed" ;;
  *psql*) echo 1 ;;
esac
""",
    "uv": """#!/usr/bin/env bash
echo "uv $*" >> "$FS_LOG"
case "$*" in
  *SEED_VERSION*) cat "$FS_STATE/code_seed" ;;
  *verify_ddl_matches_schema*) echo '{"errors": []}' ;;
esac
""",
    "npm": f"""#!/usr/bin/env bash
echo "npm $*" >> "$FS_LOG"
case "$*" in *"run build"*)
  mkdir -p "$2/dist" && echo ok > "$2/dist/index.html"
  if [ "$2" = frontend ] && [ ! -f "$FS_STATE/private_missing" ]; then
    for asset in {PRIVATE}; do mkdir -p "backend/private-assets/soap-poc/$(dirname "$asset")"; echo p > "backend/private-assets/soap-poc/$asset"; done
  fi ;;
esac
""",
    "curl": """#!/usr/bin/env bash
echo "curl $*" >> "$FS_LOG"
case "$*" in *127.0.0.1*) echo -n 401 ;; *) echo -n 200 ;; esac
""",
    "gh": '#!/usr/bin/env bash\necho "gh $*" >> "$FS_LOG"\ncat "$FS_STATE/ci"\n',
    "launchctl": '#!/usr/bin/env bash\necho "launchctl $*" >> "$FS_LOG"\n',
}


class DeployScriptTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="fs-deploy-test-"))
        self.addCleanup(shutil.rmtree, self.tmp, ignore_errors=True)
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        for name, body in STUBS.items():
            path = self.bin / name
            path.write_text(body, encoding="utf-8")
            path.chmod(0o755)
        self.state = self.tmp / "state"
        self.state.mkdir()
        self.log = self.tmp / "log"
        self.log.write_text("", encoding="utf-8")
        self.api_log = self.tmp / "api.log"
        self.api_log.write_text('old "GET / HTTP/1.1" 500\n', encoding="utf-8")  # 재시작 전 5xx는 세지 않는다
        # 가짜 저장소: main + bare origin + 운영 worktree. 실제 저장소·운영과 무관하게 돌린다.
        self.origin = self.tmp / "origin.git"
        self.repo = self.tmp / "repo"
        self.prod = self.tmp / "prod"
        subprocess.run(["git", "init", "--bare", "-b", "main", str(self.origin)], check=True, capture_output=True)
        subprocess.run(["git", "init", "-b", "main", str(self.repo)], check=True, capture_output=True)
        (self.repo / "tools").mkdir()
        shutil.copy(DEPLOY, self.repo / "tools/deploy.sh")
        (self.repo / ".gitignore").write_text(".env\n*/dist/\nbackend/private-assets/\n", encoding="utf-8")
        self._git("config", "user.email", "test@example.com")
        self._git("config", "user.name", "test")
        self._git("add", "-A")
        self._git("commit", "-qm", "old")
        self._git("worktree", "add", "-q", "--detach", str(self.prod))
        (self.prod / ".env").write_text("X=1\n", encoding="utf-8")
        (self.repo / "frontend").mkdir()
        (self.repo / "frontend/package.json").write_text("{}\n", encoding="utf-8")
        self._git("add", "-A")
        self._git("commit", "-qm", "new")
        self._git("remote", "add", "origin", str(self.origin))
        self._git("push", "-q", "-u", "origin", "main")
        self.sha = self._git("rev-parse", "HEAD", capture=True)
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
            "FS_DEPLOY_PROD_DIR": str(self.prod),
            "FS_DEPLOY_BACKUP_DIR": str(self.tmp / "backups"),
            "FS_DEPLOY_API_LOG": str(self.api_log),
            "FS_DEPLOY_SITE": "eip.test.invalid",
            "FS_DEPLOY_CARD_SITE": "www.test.invalid",
        }
        return subprocess.run(
            ["bash", str(self.repo / "tools/deploy.sh"), *args],
            capture_output=True, text=True, env=env, cwd=str(self.repo), check=False,
        )

    def _commands(self):
        return self.log.read_text(encoding="utf-8")

    def _prod_head(self):
        return subprocess.run(["git", "-C", str(self.prod), "rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()

    def test_deploy_runs_every_step_in_order(self):
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self._commands()
        order = ["pg_dump", "npm --prefix frontend run build", "npm --prefix card run build", "uv sync", "alembic", "SEED_VERSION", "launchctl kickstart -k", "https://eip.test.invalid/", "https://www.test.invalid/", "verify_ddl_matches_schema"]
        positions = [log.find(step) for step in order]
        self.assertNotIn(-1, positions, log)
        self.assertEqual(positions, sorted(positions), log)
        self.assertEqual(self._prod_head(), self.sha)
        self.assertNotIn("seed.cli template", log)  # 시드 버전이 같으면 템플릿 유지
        self.assertEqual(len(list((self.tmp / "backups").iterdir())), 1)
        self.assertIn("5xx 0건", result.stdout)
        self.assertIn("배포 완료", result.stdout)

    def test_missing_private_assets_stop_before_migration(self):
        (self.state / "private_missing").touch()
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("관리자 비누 자산이 없습니다", result.stderr)
        self.assertNotIn("alembic", self._commands())
        self.assertNotIn("launchctl", self._commands())

    def test_new_seed_version_rebuilds_template(self):
        (self.state / "db_seed").write_text("sv-old-9\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("seed.cli template", self._commands())

    def test_dirty_prod_folder_changes_nothing(self):
        (self.prod / ".gitignore").write_text("changed\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("운영 폴더에 고친 파일", result.stderr)
        self.assertNotIn("pg_dump", self._commands())
        self.assertNotEqual(self._prod_head(), self.sha)

    def test_stops_before_touching_prod_when_ci_is_not_green(self):
        (self.state / "ci").write_text("completed failure\n", encoding="utf-8")
        result = self._run()
        self.assertEqual(result.returncode, 1)
        self.assertIn("CI가 통과하지 않았습니다", result.stderr)
        self.assertNotIn("docker", self._commands())
        self.assertNotEqual(self._prod_head(), self.sha)

    def test_dry_run_changes_nothing(self):
        result = self._run("--dry-run")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        log = self._commands()
        for changing in ("pg_dump", "npm", "alembic", "launchctl"):
            self.assertNotIn(changing, log)
        self.assertNotEqual(self._prod_head(), self.sha)


if __name__ == "__main__":
    unittest.main()
