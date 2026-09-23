"""FEMS 에너지 배분의 MES 필수 의존을 끊는다 (FS-005d 3장 모듈 경계 규칙).

현재 fems.energy_allocation 은 mes.operation_execution 을 필수로 참조한다.
그래서 MES 를 끄면 에너지 배분 자체가 불가능하다. 에너지 배분은 설비 단위로도
성립해야 하며, 공정 실행은 "어느 작업에 쓰였는지"를 더해 주는 선택 정보다.

변경:
  - equipment_id 추가 (필수, core.equipment 참조 — 공유 기준정보라 필수 허용)
  - execution_id 를 nullable 로 전환
  - execution_id 가 들어간 UK 는 조건부 유니크로 전환

재실행 가능하다. 실행: python3 tools/apply_fems_alloc_fix.py
이후: python3 tools/audit_module_boundary.py → npm run db:validate → npm run db:build
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
d = json.loads(SCHEMA.read_text())
tables = {t['name']: t for t in d['tables']}

for need in ['fems.energy_allocation', 'core.equipment']:
    if need not in tables:
        raise SystemExit(f'ABORT: {need} 가 없다.')

alloc = tables['fems.energy_allocation']
acols = {c['name']: c for c in alloc['columns']}

if 'equipment_id' in acols and acols.get('execution_id', {}).get('nullable'):
    print('Already applied; nothing to do.')
    raise SystemExit(0)
if 'execution_id' not in acols:
    raise SystemExit('ABORT: fems.energy_allocation 에 execution_id 가 없다. 구조를 직접 확인하라.')

eq_type = next(c['type'] for c in tables['core.equipment']['columns'] if c['name'] == 'id')
changes = []

# 1) 설비 참조 추가 — 배분의 기본 축
if 'equipment_id' not in acols:
    alloc['columns'].append(dict(
        name='equipment_id', label='배분 대상 설비', type=eq_type, nullable=False, default=None,
        rule='배분의 기본 축. core 공유 기준정보이므로 필수 참조가 허용된다'))
    d['relations'].append(dict(
        source='fems.energy_allocation',
        columns=['workspace_id', 'generation_id', 'equipment_id'],
        target='core.equipment', target_columns=['workspace_id', 'generation_id', 'id'],
        on_delete='RESTRICT', on_update='RESTRICT', note='배분 대상 설비'))
    changes.append('equipment_id 추가 및 core.equipment 참조')

# 2) 공정 실행을 선택 참조로 전환
if not acols['execution_id']['nullable']:
    acols['execution_id']['nullable'] = True
    acols['execution_id']['rule'] = ('선택 참조. MES 가 켜져 있을 때만 지정한다. '
                                     '지정하면 어느 작업에 쓰인 에너지인지 추적이 붙는다')
    changes.append('execution_id 를 nullable 로 전환')

# 3) execution_id 가 포함된 유니크는 값이 있을 때만 적용
kept = []
for c in d['constraints']:
    if (c['table'] == 'fems.energy_allocation' and c['kind'] == 'UK'
            and 'execution_id' in c['columns']):
        kept.append(dict(c, kind='UK_PARTIAL',
                         expression='UNIQUE (' + ', '.join(c['columns']) + ') WHERE execution_id IS NOT NULL',
                         reason=c['reason'] + ' (선택 참조이므로 조건부 유니크)'))
        changes.append(f"UK {c['columns']} → 조건부 유니크")
    else:
        kept.append(c)
d['constraints'] = kept

d['constraints'] += [
    dict(table='fems.energy_allocation', kind='UK',
         columns=['workspace_id', 'generation_id', 'stat_or_reading_scope', 'equipment_id'],
         expression='', reason='설비 단위 배분 중복 차단 — 컬럼명은 실제 구조에 맞춰 확정한다')
] if False else []          # 실제 키 구성 확인 후 추가한다. 지금은 넣지 않는다.

d['constraints'].append(dict(
    table='fems.energy_allocation', kind='SERVICE/DB_POLICY', columns=['execution_id'],
    expression='MES 모듈이 비활성이면 execution_id 를 요구하지 않는다. 설비 단위로만 배분한다',
    reason='FS-005d 모듈 경계 규칙 — 타 모듈 업무 데이터는 선택 참조'))

d['version'] = '0.5.1'
d['change_log'] = d.get('change_log', []) + [
    dict(version='0.5.1', task='FS-005e', date='2026-09-21',
         change='fems.energy_allocation 독립화: ' + ', '.join(changes),
         status='모듈 경계 규칙 반영. 정적 검증 필요'),
]
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')
print(json.dumps(dict(changes=changes, next='python3 tools/audit_module_boundary.py'),
                 ensure_ascii=False, indent=2))
