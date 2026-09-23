"""설비 단위 에너지 배분의 중복 차단 UK를 추가한다.

execution_id 를 nullable 로 바꾸면서 기존 UK가 조건부가 되었다. 그래서 execution_id 가
NULL 인 설비 단위 배분에는 중복 방어가 없다. 같은 설비·채널·기간·방식으로 배분을 두 번
넣어도 막히지 않는다. 기존 UK와 같은 구성에서 execution_id 를 equipment_id 로 바꾼
조건부 UK를 더한다.

재실행 가능하다. 실행: python3 tools/apply_alloc_uk.py → npm run db:validate
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
d = json.loads(SCHEMA.read_text())

T = 'fems.energy_allocation'
cols = {c['name'] for t in d['tables'] if t['name'] == T for c in t['columns']}
if not cols:
    raise SystemExit(f'ABORT: {T} 가 없다.')
if 'equipment_id' not in cols:
    raise SystemExit('ABORT: equipment_id 가 없다. apply_fems_alloc_fix.py 를 먼저 실행하라.')

# 기존 조건부 UK 구성을 그대로 베끼고 execution_id 자리만 equipment_id 로 바꾼다.
src = next((c for c in d['constraints']
            if c['table'] == T and c['kind'] == 'UK_PARTIAL' and 'execution_id' in c['columns']), None)
if src is None:
    raise SystemExit('ABORT: execution_id 조건부 UK를 찾지 못했다.')

target_cols = ['equipment_id' if x == 'execution_id' else x for x in src['columns']]
if any(c['table'] == T and c['columns'] == target_cols for c in d['constraints']):
    print('Already applied; nothing to do.')
    raise SystemExit(0)

d['constraints'].append(dict(
    table=T, kind='UK_PARTIAL', columns=target_cols,
    expression='UNIQUE (' + ', '.join(target_cols) + ') WHERE execution_id IS NULL',
    reason='설비 단위 배분(공정 실행 미지정)의 중복 차단. 실행 단위 배분과 키가 겹치지 않도록 조건부로 둔다'))

d['version'] = '0.5.2'
d['change_log'] = d.get('change_log', []) + [
    dict(version='0.5.2', task='FS-005e', date='2026-09-21',
         change=f'{T} 에 설비 단위 배분 중복 차단 조건부 UK 추가: {target_cols}',
         status='정적 검증 필요'),
]
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(added_uk=target_cols, next='npm run db:validate'),
                 ensure_ascii=False, indent=2))
