"""Collect private proofs; optional signed PARTIAL reconciliation, never PASS."""

import argparse
import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from fs.common.errors import ApiError
from fs.core.backup import BackupError, create_private, private_directory, private_file
from fs.gw.acceptance_artifact import inspect_copy
from fs.gw.acceptance_collection import collect
from fs.gw.acceptance_reconciliation import sign_reconciliation
from fs.gw.acceptance_sources import sign_current
from fs.gw.operating_contract import OperatingPolicy, canonical
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError


def load(path):
    source = private_file(path)
    if source.stat().st_size > 65536:
        raise ValueError()
    return json.loads(source.read_bytes())


def main():
    parser = argparse.ArgumentParser(
        description="GW 백업·복원 인수 자료 수집 (운영 승인 아님)"
    )
    parser.add_argument("--context", help="현재 회사/정책/버전 비공개 JSON")
    parser.add_argument("--backup", help="기존 백업 도구의 서명 증거")
    parser.add_argument("--restore", help="기존 복원 도구의 서명 증거")
    parser.add_argument("--output", required=True, help="0700 폴더 안의 새 결과 파일")
    parser.add_argument("--storage-copy", help="외부 보관에서 가져온0600 암호화 사본")
    parser.add_argument(
        "--signed-reconciliation",
        action="store_true",
        help="원본 참조를 서명한 ACCEPTANCE PARTIAL 출력 (실환경 인수 아님)",
    )
    parser.add_argument(
        "--current-company-id",
        type=int,
        help="읽기 전용 DB에서 현재 회사/정책/최신 원본 선택",
    )
    parser.add_argument(
        "--admin-login",
        default="admin",
        help="읽기 전용 사전점검 조회 이름 (권한 부여 아님)",
    )
    args = parser.parse_args()
    engine = None
    try:
        if args.signed_reconciliation and args.storage_copy:
            raise ValueError("사본 검사는 별도 보고서로 실행하세요.")
        current_database = args.current_company_id is not None
        if current_database:
            if not args.signed_reconciliation or any(
                (args.context, args.backup, args.restore, args.storage_copy)
            ):
                raise ValueError()
        elif (
            not all((args.context, args.backup, args.restore))
            or args.admin_login != "admin"
        ):
            raise ValueError()
        path = Path(args.output)
        private_directory(path.parent)
        if path.exists() or path.is_symlink():
            raise ValueError()
        keys = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        if not isinstance(keys, dict) or not 1 <= len(keys) <= 20:
            raise ValueError()
        public = {k: base64.b64decode(v, validate=True) for k, v in keys.items()}
        if any(len(value) != 32 for value in public.values()):
            raise ValueError()
        signer = None
        if args.signed_reconciliation:
            signer = Ed25519PrivateKey.from_private_bytes(
                private_file(os.environ["FS_GW_RUNNER_KEY_FILE"], size=32).read_bytes()
            )
        if current_database:
            url = make_url(os.environ["FS_GW_PREFLIGHT_DATABASE_URL"])
            if (
                url.drivername not in {"postgresql", "postgresql+psycopg"}
                or not url.host
                or not url.database
                or not url.username
            ):
                raise ValueError()
            engine = create_engine(
                url.set(drivername="postgresql+psycopg"),
                connect_args={"connect_timeout": 10},
            )
            report = sign_current(
                engine,
                company_id=args.current_company_id,
                code_revision=os.environ["FS_CODE_REVISION"],
                admin_login=args.admin_login,
                public_keys=public,
                signer=signer,
                signer_id=os.environ["FS_GW_RUNNER_KEY_ID"],
            )
        else:
            context = load(args.context)
            if set(context) != {
                "workspaceId",
                "generationId",
                "policy",
                "codeRevision",
                "dbRevision",
            }:
                raise ValueError()
            for field in ("workspaceId", "generationId"):
                if type(context[field]) is not int or context[field] < 1:
                    raise ValueError()
            documents = {"BACKUP": load(args.backup), "RESTORE": load(args.restore)}
            trusted = {
                "public_keys": public,
                "workspace_id": context["workspaceId"],
                "generation_id": context["generationId"],
                "policy": OperatingPolicy.model_validate(context["policy"]),
                "code_revision": context["codeRevision"],
                "db_revision": context["dbRevision"],
                "now": datetime.now(UTC),
            }
            if args.signed_reconciliation:
                report = sign_reconciliation(
                    documents,
                    signer=signer,
                    signer_id=os.environ["FS_GW_RUNNER_KEY_ID"],
                    **trusted,
                )
            else:
                report = collect(documents, **trusted)
        if args.storage_copy:
            report["storageCopy"] = inspect_copy(
                args.storage_copy, documents["BACKUP"], **trusted
            )
            if report["storageCopy"]["state"] != "MATCH":
                report["result"] = "BLOCKED"
        with create_private(args.output) as output:
            output.write(canonical(report))
        result = (
            report["envelope"]["result"]
            if args.signed_reconciliation
            else report["result"]
        )
        print(json.dumps({"result": result, "ready": False}))
        return 0 if result == "PARTIAL" else 2
    except (
        ApiError,
        OSError,
        BackupError,
        ValueError,
        TypeError,
        KeyError,
        ValidationError,
        SQLAlchemyError,
    ):
        print(
            "인수 자료·현재 기준·공개 키·파일 권한을 확인하세요. 기존 결과는 덮어쓰지 않습니다."
        )
        return 1
    finally:
        if engine is not None:
            engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
