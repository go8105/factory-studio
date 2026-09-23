"""FS-005e — ERP 모듈 보강. 견적 3개 + 거래처별 단가 1개 추가, 출하 구조 독립화.

1) 신규 테이블 4개
   erp.quotation / erp.quotation_line / erp.quotation_status_history / erp.partner_item_price
2) erp.sales_order 에 quotation_id(nullable) 추가 — 견적에서 수주로 전환
3) **출하 독립화**: erp.shipment_line 에 item_id(필수) + shipped_uom 추가,
   packing_unit_id 를 nullable 로 바꾸고 이중 출하 차단을 조건부 유니크로 전환.
   MES 를 꺼도 품목·수량으로 출하와 매출이 성립해야 한다 (FS-005d 3장 모듈 경계 규칙).

재실행 가능하다. 실행: python3 tools/apply_fs005e.py
이후: python3 tools/audit_module_boundary.py → npm run db:validate → npm run db:build
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
d = json.loads(SCHEMA.read_text())
tables = {t['name']: t for t in d['tables']}

if 'erp.quotation' in tables:
    print('FS-005e already applied; nothing to do.')
    raise SystemExit(0)
for need in ['erp.partner', 'erp.sales_order', 'erp.shipment_line', 'core.item']:
    if need not in tables:
        raise SystemExit(f'ABORT: {need} 가 없다. 메타데이터 버전을 확인하라.')

base = tables['erp.sales_order']
bcols = {c['name']: c for c in base['columns']}
for need in ['id', 'workspace_id', 'generation_id', 'created_at']:
    if need not in bcols:
        raise SystemExit(f'ABORT: erp.sales_order 에 {need} 가 없다.')

ID_COL, CREATED = dict(bcols['id']), dict(bcols['created_at'])
SCOPE = [dict(bcols['workspace_id']), dict(bcols['generation_id'])]
anchor = [r for r in d['relations']
          if r['source'] == 'erp.sales_order' and set(r['columns']) == {'workspace_id', 'generation_id'}]
if not anchor:
    raise SystemExit('ABORT: erp.sales_order 의 범위 앵커 FK를 찾지 못했다.')

new_tables, new_constraints, new_relations = [], [], []


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def add(name, label, sub, note, body):
    new_tables.append(dict(name=name, label=label, scope='generation', phase='M3',
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


QTY, MONEY, PRICE = 'numeric(18,3)', 'numeric(18,2)', 'numeric(18,4)'

# ───────────────────────────── 견적 ─────────────────────────────
add('erp.quotation', '견적서', 'quotation', 'FS-005e 5.1. 확정본은 수정하지 않고 새 개정본으로 복제', [
    col('quote_no', '견적번호', 'varchar(40)'),
    col('revision_no', '개정 번호', 'integer', default='1'),
    col('partner_id', '거래처', 'bigint'),
    col('quoted_on', '견적일', 'date'),
    col('valid_until', '유효기한', 'date', nullable=True),
    col('status', '상태', 'varchar(20)', default="'draft'",
        rule='draft / confirmed / sent / accepted / rejected / cancelled'),
    col('remark', '비고', 'text', nullable=True),
])
uk('erp.quotation', ['workspace_id', 'generation_id', 'quote_no', 'revision_no'], '견적번호·개정별 1건')
chk('erp.quotation', ['revision_no'], 'revision_no >= 1', '개정 번호는 1부터')
chk('erp.quotation', ['quoted_on', 'valid_until'],
    'valid_until IS NULL OR valid_until >= quoted_on', '유효기한이 견적일보다 빠를 수 없음')
pol('erp.quotation', ['status'],
    'confirmed 이후 라인 변경 거부. 변경이 필요하면 revision_no 를 올린 새 행으로 복제한다', '확정 견적 보호')
fk('erp.quotation', ['partner_id'], 'erp.partner', ['id'], '견적 거래처')

add('erp.quotation_line', '견적 명세', 'quotation', 'FS-005e 5.1', [
    col('quotation_id', '견적서', 'bigint'),
    col('line_no', '행 번호', 'integer'),
    col('item_id', '품목', 'bigint'),
    col('quote_qty', '견적수량', QTY),
    col('unit', '단위', 'varchar(10)'),
    col('unit_price', '단가', PRICE, rule='단가 마스터에서 복사한 값. 이후 마스터 변경에 영향받지 않는다'),
    col('discount_rate', '할인율', 'numeric(5,2)', default='0'),
])
uk('erp.quotation_line', ['workspace_id', 'generation_id', 'quotation_id', 'line_no'], '견적 내 행 유일')
chk('erp.quotation_line', ['quote_qty'], 'quote_qty > 0', '0 견적 차단')
chk('erp.quotation_line', ['discount_rate'], 'discount_rate >= 0 AND discount_rate <= 100', '할인율 범위')
fk('erp.quotation_line', ['quotation_id'], 'erp.quotation', ['id'], '견적 소속')
fk('erp.quotation_line', ['item_id'], 'core.item', ['id'], '견적 품목')

add('erp.quotation_status_history', '견적 상태 이력', 'quotation',
    'FS-005e 5.1. 불변 이력. UPDATE/DELETE 금지', [
        col('quotation_id', '견적서', 'bigint'),
        col('status', '상태', 'varchar(20)'),
        col('changed_at', '변경 시각', 'timestamptz'),
        col('reason', '사유', 'varchar(200)', nullable=True),
    ])
pol('erp.quotation_status_history', ['status'],
    'APPEND ONLY. 상태 전이마다 행을 추가하고 기존 행을 수정하지 않는다', '업무 상태 추적')
fk('erp.quotation_status_history', ['quotation_id'], 'erp.quotation', ['id'], '대상 견적')

# ───────────────────────── 거래처별 단가 ─────────────────────────
add('erp.partner_item_price', '거래처별 품목 단가', 'erp_master',
    'FS-005e 5.1. 전표는 이 값을 복사해 보관한다. 마스터만 참조하지 않는다', [
        col('partner_id', '거래처', 'bigint'),
        col('item_id', '품목', 'bigint'),
        col('price_kind', '단가 구분', 'varchar(20)', default="'SALE'", rule='SALE. 구매는 ERP-2'),
        col('unit_price', '단가', PRICE),
        col('currency', '통화', 'varchar(3)', default="'KRW'"),
        col('effective_from', '적용 시작 연월', 'varchar(7)', rule="'YYYY-MM'"),
        col('effective_to', '적용 종료 연월', 'varchar(7)', nullable=True,
            rule="'YYYY-MM'. NULL이면 현재 적용 중"),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ])
uk('erp.partner_item_price',
   ['workspace_id', 'generation_id', 'partner_id', 'item_id', 'price_kind', 'effective_from'],
   '거래처·품목·구분·적용시작별 1건')
chk('erp.partner_item_price', ['unit_price'], 'unit_price >= 0', '음수 단가 차단')
chk('erp.partner_item_price', ['effective_from'],
    "effective_from ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", '연월 형식 강제')
pol('erp.partner_item_price', ['unit_price'],
    '견적·수주 생성 시 이 단가를 명세 행에 복사한다. 이후 마스터 변경이 과거 전표에 소급되지 않는다',
    '단가 스냅샷')
fk('erp.partner_item_price', ['partner_id'], 'erp.partner', ['id'], '대상 거래처')
fk('erp.partner_item_price', ['item_id'], 'core.item', ['id'], '대상 품목')

# ─────────────────── 수주: 견적 전환 연결 (선택) ───────────────────
base['columns'] += [col('quotation_id', '근거 견적서', 'bigint', nullable=True,
                        rule='견적에서 전환된 수주만 값을 갖는다')]
new_relations.append(dict(source='erp.sales_order',
                          columns=['workspace_id', 'generation_id', 'quotation_id'],
                          target='erp.quotation',
                          target_columns=['workspace_id', 'generation_id', 'id'],
                          on_delete='RESTRICT', on_update='RESTRICT', note='견적에서 전환'))

# ─────────────────── 출하 독립화 (모듈 경계 규칙) ───────────────────
sl = tables['erp.shipment_line']
slc = {c['name']: c for c in sl['columns']}
if 'packing_unit_id' not in slc:
    raise SystemExit('ABORT: erp.shipment_line 에 packing_unit_id 가 없다.')

item_type = next(c['type'] for c in tables['core.item']['columns'] if c['name'] == 'id')
sl['columns'] += [
    col('item_id', '품목', item_type, rule='ERP 단독 출하의 기준. MES 없이도 출하가 성립한다'),
    col('shipped_uom', '출하 단위', 'varchar(10)'),
]
slc['packing_unit_id']['nullable'] = True
slc['packing_unit_id']['rule'] = ('선택 참조. MES 가 켜져 있을 때만 지정한다. '
                                  '지정하면 LOT 추적이 붙고, 없으면 품목·수량 기준 출하로 처리한다')

kept = []
for c in d['constraints']:
    if c['table'] == 'erp.shipment_line' and c['kind'] == 'UK' and 'packing_unit_id' in c['columns']:
        # 이중 출하 차단은 값이 있을 때만 적용한다.
        kept.append(dict(c, kind='UK_PARTIAL',
                         expression='UNIQUE (' + ', '.join(c['columns']) + ') WHERE packing_unit_id IS NOT NULL',
                         reason=c['reason'] + ' (FS-005e: 선택 참조이므로 조건부 유니크)'))
    else:
        kept.append(c)
d['constraints'] = kept

new_constraints += [
    dict(table='erp.shipment_line', kind='SERVICE/DB_POLICY', columns=['item_id', 'packing_unit_id'],
         expression='packing_unit_id 가 있으면 그 패킹 단위의 품목과 item_id 가 일치해야 한다',
         reason='품목 불일치 출하 차단'),
    dict(table='erp.shipment_line', kind='SERVICE/DB_POLICY', columns=['packing_unit_id'],
         expression='MES 모듈이 비활성이면 packing_unit_id 입력을 요구하지 않는다. 품목·수량만으로 출하 확정한다',
         reason='FS-005d 모듈 경계 규칙 — 타 모듈 업무 데이터는 선택 참조'),
]
new_relations.append(dict(source='erp.shipment_line',
                          columns=['workspace_id', 'generation_id', 'item_id'],
                          target='core.item', target_columns=['workspace_id', 'generation_id', 'id'],
                          on_delete='RESTRICT', on_update='RESTRICT', note='출하 품목'))

# ───────────────────────────── 병합 ─────────────────────────────
d['tables'] += new_tables
d['constraints'] += new_constraints
d['relations'] += new_relations
d['version'] = '0.5.0'
d['task'] = 'FS-005e'
d['states'] = d.get('states', []) + [
    dict(table='erp.quotation', column='status',
         values=['draft', 'confirmed', 'sent', 'accepted', 'rejected', 'cancelled'], default='draft',
         transition='draft→confirmed→sent→accepted 또는 rejected; 어느 단계에서든 cancelled. '
                    'confirmed 이후 내용 변경은 새 개정본으로만'),
]
d['code_lists'] = d.get('code_lists', []) + [
    dict(target='erp.partner_item_price', column='price_kind', values=['SALE'], default='SALE',
         note='구매 단가(PURCHASE)는 ERP-2에서 추가한다'),
]
d['change_log'] = d.get('change_log', []) + [
    dict(version='0.5.0', task='FS-005e', date='2026-09-21',
         change='ERP 보강: 견적 3개(quotation, quotation_line, quotation_status_history)와 '
                '거래처별 단가 1개 추가. sales_order 에 quotation_id 선택 참조 추가',
         status='정적 검증 필요'),
    dict(version='0.5.0', task='FS-005e', date='2026-09-21',
         change='출하 독립화: shipment_line 에 item_id·shipped_uom 추가, packing_unit_id 를 nullable 로 전환, '
                '이중 출하 차단을 조건부 유니크로 변경. MES 없이도 ERP 출하·매출이 성립한다',
         status='모듈 경계 규칙(FS-005d 3장) 반영'),
]
d['sources'] = d.get('sources', []) + ['FS-005e ERP 모듈 공통 설계서']
SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n')

print(json.dumps(dict(
    applied='FS-005e', added_tables=len(new_tables),
    added_constraints=len(new_constraints), added_relations=len(new_relations),
    shipment_line='item_id 추가 · packing_unit_id nullable · 이중출하 차단 조건부 유니크',
    total_tables=len(d['tables']),
    total_columns=sum(len(t['columns']) for t in d['tables']),
    total_relations=len(d['relations']),
    next='python3 tools/audit_module_boundary.py',
), ensure_ascii=False, indent=2))
