"""FS-005f — MES 에 BOM 2개와 자재 투입 1개를 추가한다.

목적: LOT 역추적을 성립시킨다. 지금은 공정→완제품(정방향)만 되고
완제품→투입 자재(역방향)가 되지 않는다.

  mes.bom_version   품목별 BOM 버전. 게시 후 불변
  mes.bom_line      자재 구성과 단위 소요량
  mes.material_issue 공정 실행별 자재 투입 기록

재고는 차감하지 않는다. 투입 기록만 남기고 재고 원장은 WMS 소유다.
WMS 가 없어도 투입 기록은 성립해야 한다 (FS-005d 3장 모듈 경계 규칙).

재실행 가능하다. 실행: python3 tools/apply_fs005f.py
이후: npm run db:validate → npm run db:build → python3 tools/build_erd.py
      → python3 tools/audit_module_boundary.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
d = json.loads(SCHEMA.read_text())
tables = {t['name']: t for t in d['tables']}

if 'mes.bom_version' in tables:
    print('FS-005f already applied; nothing to do.')
    raise SystemExit(0)
for need in ['mes.work_order', 'mes.lot', 'mes.operation_execution', 'core.item']:
    if need not in tables:
        raise SystemExit(f'ABORT: {need} 가 없다. 메타데이터 버전을 확인하라.')

base = tables['mes.work_order']
bc = {c['name']: c for c in base['columns']}
for need in ['id', 'workspace_id', 'generation_id', 'created_at']:
    if need not in bc:
        raise SystemExit(f'ABORT: mes.work_order 에 {need} 가 없다.')

ID_COL, CREATED = dict(bc['id']), dict(bc['created_at'])
SCOPE = [dict(bc['workspace_id']), dict(bc['generation_id'])]
BIGINT = ID_COL['type']
anchor = [r for r in d['relations']
          if r['source'] == 'mes.work_order' and set(r['columns']) == {'workspace_id', 'generation_id'}]
if not anchor:
    raise SystemExit('ABORT: mes.work_order 의 범위 앵커 FK를 찾지 못했다.')

new_tables, new_constraints, new_relations = [], [], []


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def add(name, label, sub, note, body):
    new_tables.append(dict(name=name, label=label, scope='generation', phase='M2',
                           retention='세대 교체', note=note, sub_module=sub,
                           columns=[dict(ID_COL)] + [dict(c) for c in SCOPE] + body + [dict(CREATED)]))
    new_constraints.append(dict(table=name, kind='PK', columns=['id'], expression='', reason='기본키'))
    new_constraints.append(dict(table=name, kind='UK', columns=['workspace_id', 'generation_id', 'id'],
                               expression='', reason='공간·세대 복합 참조 대상'))
    for r in anchor:
        new_relations.append(dict(r, source=name))


def uk(t, c, reason):
    new_constraints.append(dict(table=t, kind='UK', columns=c, expression='', reason=reason))


def chk(t, c, e, reason):
    new_constraints.append(dict(table=t, kind='CHECK', columns=c, expression=e, reason=reason))


def pol(t, c, e, reason):
    new_constraints.append(dict(table=t, kind='SERVICE/DB_POLICY', columns=c, expression=e, reason=reason))


def fk(s, c, t, tc, note):
    new_relations.append(dict(source=s, columns=['workspace_id', 'generation_id'] + c,
                              target=t, target_columns=['workspace_id', 'generation_id'] + tc,
                              on_delete='RESTRICT', on_update='RESTRICT', note=note))


QTY = 'numeric(18,3)'

# ───────────────────────────── BOM ─────────────────────────────
add('mes.bom_version', 'BOM 버전', 'bom',
    'FS-005f 5.1. 경로 버전과 같은 규칙 — 게시 후 불변, 지시 발행 시 고정', [
        col('bom_code', 'BOM 코드', 'varchar(40)'),
        col('item_id', '대상 품목', BIGINT, rule='이 BOM이 만들어내는 품목'),
        col('version_no', '버전 번호', 'integer', default='1'),
        col('status', '상태', 'varchar(20)', default="'draft'",
            rule='draft / published / retired'),
        col('published_at', '게시 시각', 'timestamptz', nullable=True),
    ])
uk('mes.bom_version', ['workspace_id', 'generation_id', 'bom_code'], '세대 내 코드 유일')
uk('mes.bom_version', ['workspace_id', 'generation_id', 'item_id', 'version_no'], '품목별 버전 유일')
chk('mes.bom_version', ['version_no'], 'version_no >= 1', '버전은 1부터')
pol('mes.bom_version', ['status'],
    'published 이후 구성 라인 변경 거부. 변경이 필요하면 새 버전을 만든다', '게시 BOM 불변')
pol('mes.bom_version', ['status'],
    'draft 상태 BOM 은 작업지시에 적용할 수 없다', '미게시 BOM 사용 차단')
fk('mes.bom_version', ['item_id'], 'core.item', ['id'], '대상 품목')

add('mes.bom_line', 'BOM 구성', 'bom', 'FS-005f 5.1. 1단계 전개만 구현한다', [
    col('bom_version_id', 'BOM 버전', BIGINT),
    col('line_no', '행 번호', 'integer'),
    col('material_item_id', '자재 품목', BIGINT),
    col('qty_per_unit', '단위 소요량', QTY, rule='완제품 1개당 필요한 자재 수량'),
    col('unit', '단위', 'varchar(10)'),
    col('loss_rate', '로스율', 'numeric(5,2)', default='0', rule='예상 손실률 %'),
])
uk('mes.bom_line', ['workspace_id', 'generation_id', 'bom_version_id', 'line_no'], 'BOM 내 행 유일')
uk('mes.bom_line', ['workspace_id', 'generation_id', 'bom_version_id', 'material_item_id'],
   'BOM 내 자재 품목 1회')
chk('mes.bom_line', ['qty_per_unit'], 'qty_per_unit > 0', '0 소요량 차단')
chk('mes.bom_line', ['loss_rate'], 'loss_rate >= 0 AND loss_rate < 100', '로스율 범위')
pol('mes.bom_line', ['material_item_id'],
    '대상 품목과 자재 품목이 같을 수 없다. 자기 참조 구성을 거부한다', '순환 구성 차단')
fk('mes.bom_line', ['bom_version_id'], 'mes.bom_version', ['id'], 'BOM 소속')
fk('mes.bom_line', ['material_item_id'], 'core.item', ['id'], '자재 품목')

# ─────────────────────────── 자재 투입 ───────────────────────────
add('mes.material_issue', '자재 투입', 'execution',
    'FS-005f 5.1. LOT 역추적의 근거. 재고를 차감하지 않고 투입 기록만 남긴다', [
        col('execution_id', '공정 실행', BIGINT),
        col('material_item_id', '자재 품목', BIGINT),
        col('material_lot_id', '자재 LOT', BIGINT, nullable=True,
            rule='LOT 관리 자재만 지정한다. 없으면 품목 단위 투입으로 기록한다'),
        col('bom_version_id', '적용 BOM 버전', BIGINT, nullable=True,
            rule='이론 소요량과 비교할 근거. BOM 없이 투입한 경우 NULL'),
        col('issued_qty', '투입 수량', QTY),
        col('unit', '단위', 'varchar(10)'),
        col('issued_at', '투입 시각', 'timestamptz'),
    ])
uk('mes.material_issue',
   ['workspace_id', 'generation_id', 'execution_id', 'material_item_id', 'material_lot_id'],
   '실행·자재·LOT별 1건')
chk('mes.material_issue', ['issued_qty'], 'issued_qty > 0', '0 투입 차단')
pol('mes.material_issue', ['material_lot_id'],
    'material_lot_id 가 NULL 인 행은 UNIQUE 로 중복이 막히지 않는다. '
    '같은 실행·자재에 LOT 미지정 투입을 두 번 넣지 않도록 서비스에서 검사한다',
    'NULL 중복 허용 보완')
pol('mes.material_issue', ['issued_qty'],
    '재고를 차감하지 않는다. 재고 원장은 WMS 소유이며 WMS 가 없어도 투입 기록은 성립한다',
    'FS-005d 모듈 경계 규칙')
pol('mes.material_issue', ['execution_id'],
    '확정된 공정 실적이 있는 실행에는 자재 투입을 추가하거나 변경할 수 없다', '확정 후 불변')
fk('mes.material_issue', ['execution_id'], 'mes.operation_execution', ['id'], '대상 공정 실행')
fk('mes.material_issue', ['material_item_id'], 'core.item', ['id'], '자재 품목')
fk('mes.material_issue', ['material_lot_id'], 'mes.lot', ['id'], '자재 LOT — 역추적의 연결점')
fk('mes.material_issue', ['bom_version_id'], 'mes.bom_version', ['id'], '적용 BOM 버전')

# ─────────────────── 작업지시에 BOM 버전 고정 ───────────────────
base['columns'] += [col('bom_version_id', '적용 BOM 버전', BIGINT, nullable=True,
                        rule='발행 시 고정한다. BOM 이 없는 품목은 NULL')]
new_relations.append(dict(source='mes.work_order',
                          columns=['workspace_id', 'generation_id', 'bom_version_id'],
                          target='mes.bom_version',
                          target_columns=['workspace_id', 'generation_id', 'id'],
                          on_delete='RESTRICT', on_update='RESTRICT', note='발행 시 고정한 BOM 버전'))
new_constraints.append(dict(
    table='mes.work_order', kind='SERVICE/DB_POLICY', columns=['bom_version_id'],
    expression='발행 시점의 게시 BOM 버전을 고정한다. 이후 BOM 이 개정돼도 진행 중 지시는 영향받지 않는다',
    reason='경로 버전 고정과 동일한 규칙'))

# ───────────────────────────── 병합 ─────────────────────────────
d['tables'] += new_tables
d['constraints'] += new_constraints
d['relations'] += new_relations
d['version'] = '0.6.0'
d['task'] = 'FS-005f'
d['states'] = d.get('states', []) + [
    dict(table='mes.bom_version', column='status',
         values=['draft', 'published', 'retired'], default='draft',
         transition='draft→published→retired; 게시 내용 불변'),
]
d['change_log'] = d.get('change_log', []) + [
    dict(version='0.6.0', task='FS-005f', date='2026-09-21',
         change='MES 보강: bom_version, bom_line, material_issue 추가. work_order 에 bom_version_id 고정 컬럼',
         status='정적 검증 필요'),
    dict(version='0.6.0', task='FS-005f', date='2026-09-21',
         change='LOT 역추적 성립: 완제품 LOT → 공정 실행 → 자재 투입 → 자재 LOT',
         status='조회 경로는 구현 단계에서 검증'),
]
d['sources'] = d.get('sources', []) + ['FS-005f MES 모듈 공통 설계서']
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

print(json.dumps(dict(
    applied='FS-005f', added_tables=len(new_tables),
    added_constraints=len(new_constraints), added_relations=len(new_relations),
    traceability='완제품 LOT → 공정 실행 → 자재 투입 → 자재 LOT (역추적 성립)',
    total_tables=len(d['tables']),
    total_columns=sum(len(t['columns']) for t in d['tables']),
    total_relations=len(d['relations']),
    next='npm run db:validate',
), ensure_ascii=False, indent=2))
