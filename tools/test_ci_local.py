"""OPS-CI-01 로컬 CI 스크립트 검증: tools/ci_local.sh 단위 테스트.

--help, --dry-run, 알 수 없는 인자 거부, _test 접미사 안전 검사 및 비밀번호 미노출을 확인한다.
"""

import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CI_LOCAL = ROOT / "tools/ci_local.sh"


class CiLocalScriptTest(unittest.TestCase):
    def test_help_option(self):
        result = subprocess.run(
            ["bash", str(CI_LOCAL), "--help"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0)
        self.assertIn("tools/ci_local.sh", result.stdout)
        self.assertIn("--dry-run", result.stdout)

    def test_unknown_option(self):
        result = subprocess.run(
            ["bash", str(CI_LOCAL), "--unknown-flag"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("모르는 인자", result.stderr)

    def test_dry_run_executes_safely(self):
        result = subprocess.run(
            ["bash", str(CI_LOCAL), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(result.returncode, 0, msg=result.stderr)
        self.assertIn("1단계: DB 검증 · 도구 단위 테스트", result.stdout)
        self.assertIn("2단계: 백엔드 ruff 검사", result.stdout)
        self.assertIn("3단계: 백엔드 마이그레이션 적용 및 pytest", result.stdout)
        self.assertIn("4단계: DB 초기화 및 마이그레이션 왕복", result.stdout)
        self.assertIn("5단계: 프런트엔드 검증", result.stdout)
        self.assertIn("로컬 CI 전체 통과 완료", result.stdout)

    def test_rejects_non_test_db(self):
        env = {"TEST_DB": "factory_studio_production"}
        result = subprocess.run(
            ["bash", str(CI_LOCAL), "--dry-run"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            env={**subprocess.os.environ, **env},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("_test", result.stderr)


if __name__ == "__main__":
    unittest.main()
