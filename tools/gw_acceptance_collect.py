"""Collect private proof files without DB access, credentials or PASS issuance."""

import argparse
import base64
import json
import os
from datetime import UTC, datetime

from fs.common.errors import ApiError
from fs.core.backup import BackupError, create_private, private_file
from fs.gw.acceptance_artifact import inspect_copy
from fs.gw.acceptance_collection import collect
from fs.gw.operating_contract import OperatingPolicy, canonical
from pydantic import ValidationError


def load(path):
    source = private_file(path)
    if source.stat().st_size > 65536:
        raise ValueError()
    return json.loads(source.read_bytes())


def main():
    parser = argparse.ArgumentParser(
        description="GW 백업·복원 인수 자료 수집 (운영 승인 아님)"
    )
    parser.add_argument(
        "--context", required=True, help="현재 회사/정책/버전 비공개 JSON"
    )
    parser.add_argument("--backup", required=True, help="기존 백업 도구의 서명 증거")
    parser.add_argument("--restore", required=True, help="기존 복원 도구의 서명 증거")
    parser.add_argument("--output", required=True, help="0700 폴더 안의 새 결과 파일")
    parser.add_argument("--storage-copy", help="외부 보관에서 가져온0600 암호화 사본")
    args = parser.parse_args()
    try:
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
        keys = json.loads(os.environ["FS_GW_EVIDENCE_PUBLIC_KEYS"])
        if not isinstance(keys, dict) or not 1 <= len(keys) <= 20:
            raise ValueError()
        public = {k: base64.b64decode(v, validate=True) for k, v in keys.items()}
        if any(len(value) != 32 for value in public.values()):
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
        report = collect(documents, **trusted)
        if args.storage_copy:
            report["storageCopy"] = inspect_copy(
                args.storage_copy, documents["BACKUP"], **trusted
            )
            if report["storageCopy"]["state"] != "MATCH":
                report["result"] = "BLOCKED"
        with create_private(args.output) as output:
            output.write(canonical(report))
        print(json.dumps({"result": report["result"], "ready": False}))
        return 0 if report["result"] == "PARTIAL" else 2
    except (
        ApiError,
        OSError,
        BackupError,
        ValueError,
        TypeError,
        KeyError,
        ValidationError,
    ):
        print(
            "인수 자료·현재 기준·공개 키·파일 권한을 확인하세요. 기존 결과는 덮어쓰지 않습니다."
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
