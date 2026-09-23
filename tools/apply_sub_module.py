"""FS-005d — 각 테이블에 sub_module 속성을 부여한다.

스키마·컬럼·제약·관계를 변경하지 않는다. 분류 축을 하나 더할 뿐이다.
매핑에 없는 테이블이 하나라도 있으면 아무것도 쓰지 않고 중단한다.
테이블 이름을 추측해서 배정하지 않기 위한 장치다.

재실행 가능하다. 이미 모두 부여되어 있으면 아무것도 바꾸지 않는다.
실행: python3 tools/apply_sub_module.py  →  npm run db:validate
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'

# 테이블 이름(스키마 제외) → 하위 모듈. FS-005d 4장 기준.
MAP = {
    'core': {
        'app_user': 'account', 'auth_session': 'account', 'role': 'account', 'user_role': 'account',
        'workspace': 'workspace', 'data_generation': 'workspace',
        'workspace_module': 'workspace', 'dashboard_layout': 'workspace',
        'site': 'factory_master', 'location': 'factory_master', 'equipment': 'factory_master',
        'item': 'item_master', 'item_unit_conversion': 'item_master',
        'meter': 'metering_master', 'meter_channel': 'metering_master',
        'energy_source': 'metering_master',
        'job_run': 'ops', 'audit_event': 'ops', 'request_receipt': 'ops',
    },
    'mes': {
        'process': 'mes_master', 'process_equipment': 'mes_master',
        'route_version': 'routing', 'route_step': 'routing',
        'production_plan': 'production_plan', 'production_plan_line': 'production_plan',
        'work_order': 'work_order', 'lot': 'work_order',
        'operation_execution': 'execution', 'operation_result': 'execution',
        'learning_binding': 'learning_link',
        'packing_unit': 'packing', 'packing_member': 'packing',
        'finished_goods_receipt': 'packing',
    },
    'erp': {
        'partner': 'erp_master',
        'sales_plan': 'sales_plan', 'sales_plan_line': 'sales_plan',
        'sales_order': 'sales_order', 'sales_order_line': 'sales_order',
        'shipment_order': 'shipping', 'shipment_order_line': 'shipping',
        'shipment': 'shipping', 'shipment_line': 'shipping',
        'sales_record': 'revenue',
    },
    'fems': {
        'energy_factor': 'fems_master', 'tariff': 'fems_master',
        'energy_reading': 'energy_reading', 'energy_allocation': 'energy_reading',
        'energy_target': 'energy_goal', 'energy_baseline': 'energy_goal',
    },
    'bems': {
        'energy_reading': 'common_metering', 'environment_reading': 'environment',
    },
    'process_map': {
        'map_version': 'process_map', 'node': 'process_map', 'edge': 'process_map',
    },
}

# learning 은 콘텐츠와 진도로 나눈다. 이름이 확정적이지 않아 키워드로 판정한다.
# 진도 키워드를 먼저 본다. step_progress 처럼 양쪽 단어가 섞인 이름이 있기 때문이다.
LEARNING_CONTENT = ('course', 'step', 'question', 'content')
LEARNING_PROGRESS = ('attempt', 'progress', 'answer', 'result', 'submission')


def learning_sub(name):
    if any(k in name for k in LEARNING_PROGRESS):
        return 'progress'
    if any(k in name for k in LEARNING_CONTENT):
        return 'course'
    return None


d = json.loads(SCHEMA.read_text())
assigned, unmapped, already = [], [], []

for t in d['tables']:
    schema, _, name = t['name'].partition('.')
    if t.get('sub_module'):
        already.append(t['name'])
        continue
    sub = learning_sub(name) if schema == 'learning' else MAP.get(schema, {}).get(name)
    if sub is None:
        unmapped.append(t['name'])
    else:
        assigned.append((t['name'], sub))

if unmapped:
    print('ABORT: 하위 모듈이 정해지지 않은 테이블이 있다. 아무것도 쓰지 않았다.')
    for n in unmapped:
        print('  -', n)
    print('\n위 목록을 그대로 알려주면 FS-005d 4장과 이 스크립트의 MAP 에 추가한다.')
    raise SystemExit(1)

if not assigned:
    print(json.dumps(dict(result='이미 모두 부여되어 있다. 변경 없음',
                          tables=len(already)), ensure_ascii=False, indent=2))
    raise SystemExit(0)

lookup = dict(assigned)
for t in d['tables']:
    if t['name'] in lookup:
        t['sub_module'] = lookup[t['name']]

# 하위 모듈별 테이블 수 요약
summary = {}
for t in d['tables']:
    key = t['name'].split('.')[0] + ' / ' + t['sub_module']
    summary[key] = summary.get(key, 0) + 1

d['task'] = 'FS-005d'
d['change_log'] = d.get('change_log', []) + [
    dict(version=d.get('version', '0.4.0'), task='FS-005d', date='2026-09-21',
         change=f'테이블 {len(assigned)}개에 sub_module 부여. 스키마·컬럼·제약·관계 변경 없음',
         status='정적 검증 재실행 필요'),
]
d['sources'] = d.get('sources', []) + ['FS-005d 모듈·하위 모듈 구조 정의']
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

print(json.dumps(dict(assigned=len(assigned), already=len(already),
                      by_sub_module=dict(sorted(summary.items())),
                      next='npm run db:validate'), ensure_ascii=False, indent=2))
