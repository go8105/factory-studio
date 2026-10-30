"""Export current acceptance context with read-only company/admin diagnostics."""

import argparse
import os
from pathlib import Path

from fs.common.errors import ApiError
from fs.core.backup import BackupError, create_private, private_directory
from fs.gw.acceptance_preflight import collect
from fs.gw.acceptance_report import collect as collect_execution
from fs.gw.evidence_trust import from_environment
from fs.gw.operating_contract import canonical
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def write_outputs(context, report, *, context_output, report_output):
    paths = [Path(context_output), Path(report_output)]
    if paths[0].resolve() == paths[1].resolve():
        raise BackupError("서로 다른 새 출력 파일이 필요합니다.")
    for path in paths:
        private_directory(path.parent)
        if path.exists() or path.is_symlink():
            raise BackupError("기존 출력 파일은 덮어쓰지 않습니다.")
    opened = []
    try:
        for path in paths:
            stream = create_private(path)
            opened.append((path, stream))
        for (_, stream), value in zip(opened, [context, report], strict=True):
            stream.write(canonical(value) + b"\n")
            stream.flush()
            os.fsync(stream.fileno())
    except BaseException:
        for path, stream in opened:
            stream.close()
            path.unlink(missing_ok=True)
        raise
    finally:
        for _, stream in opened:
            stream.close()


def main():
    parser = argparse.ArgumentParser(
        description="회사10인 인수 사전점검 (읽기 전용·운영 승인 아님)"
    )
    parser.add_argument("--company-id", type=int, required=True)
    parser.add_argument(
        "--admin-login",
        default="admin",
        help="대조할 계정 이름 (권한을 부여하지 않음, 기본 admin)",
    )
    parser.add_argument(
        "--context-output", required=True, help="현재 기준을 기록할 새0600 파일"
    )
    parser.add_argument("--report", required=True, help="사전점검을 기록할 새0600 파일")
    parser.add_argument(
        "--execution-report",
        action="store_true",
        help="같은 읽기 스냅샷의 최신 원본/12조건·권한 거부 미검증 범위를 함께 보고 (서명 인수 아님)",
    )
    args = parser.parse_args()
    engine = None
    try:
        url = make_url(os.environ["FS_GW_PREFLIGHT_DATABASE_URL"])
        if (
            url.drivername not in {"postgresql", "postgresql+psycopg"}
            or not url.host
            or not url.database
            or not url.username
        ):
            raise BackupError("명시적인 PostgreSQL 읽기 연결이 필요합니다.")
        engine = create_engine(
            url.set(drivername="postgresql+psycopg"),
            connect_args={"connect_timeout": 10},
        )
        collector = collect_execution if args.execution_report else collect
        verification = (
            {"public_keys": from_environment()} if args.execution_report else {}
        )
        context, report = collector(
            engine,
            company_id=args.company_id,
            admin_login=args.admin_login,
            code_revision=os.environ["FS_CODE_REVISION"],
            **verification,
        )
        write_outputs(
            context,
            report,
            context_output=args.context_output,
            report_output=args.report,
        )
        print(
            canonical(
                {
                    "result": report["result"],
                    "ready": False,
                    **(
                        {
                            "preflightBlockedCount": sum(
                                r["state"] == "BLOCKED"
                                for r in report["preflight"]["checks"]
                            )
                        }
                        if args.execution_report
                        else {}
                    ),
                    "blockedCount": sum(
                        r["state"] == "BLOCKED" for r in report["checks"]
                    ),
                }
            ).decode()
        )
        return 0 if report["result"] == "PARTIAL" else 2
    except (
        ApiError,
        BackupError,
        OSError,
        ValueError,
        TypeError,
        KeyError,
        SQLAlchemyError,
    ):
        print(
            "사전점검을 완료하지 못했습니다. 회사·현재 기준·읽기 연결·출력 권한을 확인하세요. 기존 파일은 덮어쓰지 않습니다."
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
