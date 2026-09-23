"""FS-008c: remove exactly two stale fems.meter CHECKs (v0.9.1).

Metadata only. Source/candidate validation, SHA256 backup, same-directory fsync
and atomic replace. --check and a valid repeated application do not write files.
No generic CHECK-expression parser; no meter_channel changes.
"""
import argparse
import copy
import hashlib
import json
import os
import re
import tempfile
from collections import Counter
from pathlib import Path
from validate_db_design import validate, design_names

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {'core': 10, 'mes': 21, 'erp': 27, 'fems': 13}
DA = "(measurement_kind IN ('cumulative_energy','interval_energy') AND unit = 'kWh') OR (measurement_kind = 'instant_power' AND unit = 'kW')"
DB_OLD = "scope_kind IN ('factory','common','site_total')"
DB_KEEP = "scope_kind IN ('factory','site_total')"


def need(ok, message):
    if not ok:
        raise ValueError(message)


def checks(d):
    return [c for c in d['constraints'] if c['table']=='fems.meter' and c['kind']=='CHECK']


def check(d, applied=False):
    need(d.get('migration_revision') is None, 'DB-applied metadata is out of scope')
    expected_version, task = ('0.9.1','FS-008c') if applied else ('0.9.0','FS-008b')
    need((d.get('version'),d.get('task')) == (expected_version,task), f'Expected {expected_version} / {task}')
    need(dict(Counter(t['name'].split('.')[0] for t in d['tables'])) == COUNTS, 'Unexpected table counts')
    need(sum(len(t['columns']) for t in d['tables']) == 712, 'Unexpected column count')
    need(len(d['relations']) == 161, 'Unexpected FK count')
    need(len(d['constraints']) == (526 if applied else 528), 'Unexpected constraint/policy count')
    errors = validate(d, design_names(task))
    need(not errors, '\n'.join(errors))
    expressions = [c['expression'] for c in checks(d)]
    need(expressions.count(DB_KEEP)==1, 'Expected one retained scope CHECK')
    if applied:
        need(not any(re.search(r'\b(measurement_kind|unit)\b', c['expression']) or {'measurement_kind','unit'} & set(c['columns']) for c in checks(d)), 'D-A remains')
        need(sum(bool(re.search(r'\bscope_kind\b',e)) for e in expressions)==1, 'D-B remains')
        need(sum(c.get('task')=='FS-008c' for c in d['change_log'])==1, 'Expected one FS-008c change log')
    else:
        need(expressions.count(DA)==1 and expressions.count(DB_OLD)==1, 'Expected exactly one D-A and D-B obsolete CHECK')
        need(sum(bool(re.search(r'\bscope_kind\b',e)) for e in expressions)==2, 'Unexpected scope CHECKs')
        need(not any(c.get('task')=='FS-008c' for c in d['change_log']), 'Partial FS-008c application')


def transform(original):
    if (original.get('version'),original.get('task'))==('0.9.1','FS-008c'):
        check(original, applied=True)
        return copy.deepcopy(original)
    check(original)
    d=copy.deepcopy(original)
    d['constraints']=[c for c in d['constraints'] if not (c['table']=='fems.meter' and c['kind']=='CHECK' and c['expression'] in {DA,DB_OLD})]
    d.update(version='0.9.1',task='FS-008c',date='2026-09-23')
    d['change_log'].append(dict(version='0.9.1',task='FS-008c',date='2026-09-23',
        change='fems.meter의 삭제된 measurement_kind/unit 참조 CHECK 삭제(D-A), scope_kind 중복 CHECK 통합(D-B). 채널 변경 없음. 71테이블·712컬럼·161 FK·제약/정책 526개',
        status='정적 메타데이터 검증 대상 / DB 미적용'))
    check(d, applied=True)
    return d


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema',type=Path,default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--backup-dir',type=Path)
    parser.add_argument('--check',action='store_true')
    args=parser.parse_args()
    try:
        raw=args.schema.read_bytes();original=json.loads(raw)
        if (original.get('version'),original.get('task'))==('0.9.1','FS-008c'):
            check(original,applied=True)
            print('FS-008c already applied and valid; no files changed.');return 0
        result=transform(original)
        payload=(json.dumps(result,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
        if args.check:
            print(json.dumps(dict(check='passed',tables=71,columns=712,foreign_keys=161,constraints_and_policies=526,written=False)));return 0
        need(args.schema.read_bytes()==raw,'Source changed during validation')
        backup_dir=args.backup_dir or args.schema.parent/'backups';backup_dir.mkdir(parents=True,exist_ok=True)
        backup=backup_dir/f'schema.before-FS-008c.{hashlib.sha256(raw).hexdigest()}.json'
        if backup.exists():need(backup.read_bytes()==raw,'Existing backup content mismatch')
        else:
            with backup.open('xb') as f:f.write(raw);f.flush();os.fsync(f.fileno())
        temporary=None
        try:
            with tempfile.NamedTemporaryFile(dir=args.schema.parent,prefix='.fs008c-',delete=False) as f:
                temporary=Path(f.name);f.write(payload);f.flush();os.fsync(f.fileno())
            temporary.chmod(args.schema.stat().st_mode & 0o777)
            need(args.schema.read_bytes()==raw,'Source changed before replacement')
            os.replace(temporary,args.schema)
        finally:
            if temporary and temporary.exists():temporary.unlink()
        print(json.dumps(dict(applied='FS-008c',tables=71,columns=712,foreign_keys=161,constraints_and_policies=526,
                              backup=str(backup),sha256=hashlib.sha256(payload).hexdigest()),ensure_ascii=False,indent=2))
        return 0
    except (OSError,ValueError,KeyError,TypeError,StopIteration) as exc:
        print(f'ABORT: {exc}');return 1


if __name__=='__main__':
    raise SystemExit(main())
