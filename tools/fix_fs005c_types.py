"""FS-005c 반영 후 남은 FK 타입 불일치를 바로잡는다.

원인: core.meter_channel.owner_module 의 타입을 varchar(20) 으로 직접 지정했으나,
관측 테이블의 owner_module 타입과 문자열이 달라 복합 FK 타입 검사에 걸렸다.
추측하지 않고 참조하는 쪽의 타입을 그대로 복사한다.

재실행 가능하다. 이미 일치하면 아무것도 바꾸지 않는다.
실행: python3 tools/fix_fs005c_types.py  →  npm run db:validate
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
d = json.loads(SCHEMA.read_text())
tables = {t['name']: t for t in d['tables']}

if 'core.meter_channel' not in tables:
    raise SystemExit('ABORT: core.meter_channel 이 없다. apply_fs005c.py 를 먼저 실행하라.')

chan = {c['name']: c for c in tables['core.meter_channel']['columns']}
fixed = []

# 관측 테이블 3종이 채널을 복합 FK로 참조한다. 참조하는 쪽 컬럼 타입을 기준으로 맞춘다.
for r in d['relations']:
    if r['target'] != 'core.meter_channel':
        continue
    src = {c['name']: c for c in tables[r['source']]['columns']}
    for scol, tcol in zip(r['columns'], r['target_columns']):
        if tcol not in chan or scol not in src:
            continue
        if chan[tcol]['type'] != src[scol]['type']:
            fixed.append(dict(column=tcol, was=chan[tcol]['type'],
                              now=src[scol]['type'], driven_by=f"{r['source']}.{scol}"))
            chan[tcol]['type'] = src[scol]['type']

if not fixed:
    print(json.dumps(dict(result='이미 일치. 변경 없음'), ensure_ascii=False, indent=2))
    raise SystemExit(0)

d['change_log'] = d.get('change_log', []) + [
    dict(version=d.get('version', '0.4.0'), task='FS-005d', date='2026-09-21',
         change='core.meter_channel 의 복합 FK 참여 컬럼 타입을 관측 테이블 기준으로 정정: '
                + ', '.join(f"{f['column']} {f['was']}→{f['now']}" for f in fixed),
         status='정적 검증 재실행 필요'),
]
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(fixed=fixed, next='npm run db:validate'), ensure_ascii=False, indent=2))
