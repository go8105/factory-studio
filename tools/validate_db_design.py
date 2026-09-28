"""Static metadata validation only. Does not connect to any database."""
import argparse
import hashlib
import json
import re
from pathlib import Path
from audit_schema_isolation import audit, SCOPE

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT/'docs/db/스키마_재구성_FS-014.md'


# 작업 ID별 기준 엔티티 목록. 뒤 작업은 앞 작업의 목록을 이어받는다.
LATER_THAN_014B = {'FS-014b', 'FS-008b', 'FS-008c', 'FS-023a', 'FS-024a', 'FS-025a'}
LATER_THAN_008B = {'FS-008b', 'FS-008c', 'FS-023a', 'FS-024a', 'FS-025a'}
LATER_THAN_023A = {'FS-023a', 'FS-024a', 'FS-025a'}
LATER_THAN_024A = {'FS-024a', 'FS-025a'}
QMS_DESIGN = ROOT/'docs/modules/qms/QMS_모듈설계_FS-023.md'
WMS_DESIGN = ROOT/'docs/modules/wms/WMS_모듈설계_FS-024.md'
BEMS_DESIGN = ROOT/'docs/modules/bems/BEMS_모듈설계_FS-025.md'


def design_names(task='FS-014'):
    names = set(re.findall(r'^\| `((?:core|mes|erp|fems)\.[a-z_]+)` \|', DESIGN.read_text(encoding='utf-8'), re.M))
    if task in LATER_THAN_014B:
        document = ROOT/'docs/db/스키마_재구성_FS-014b.md'
        names |= set(re.findall(r'^\| `(erp\.[a-z_]+)` \|', document.read_text(encoding='utf-8'), re.M))
    if task in LATER_THAN_008B:
        names.discard('core.dashboard_layout')
    if task in LATER_THAN_023A:
        names |= set(re.findall(r'^\| `(qms\.[a-z_]+)` \|', QMS_DESIGN.read_text(encoding='utf-8'), re.M))
    if task in LATER_THAN_024A:
        names |= set(re.findall(r'^\| `(wms\.[a-z_]+)` \|', WMS_DESIGN.read_text(encoding='utf-8'), re.M))
    if task == 'FS-025a':
        names |= set(re.findall(r'^\| `(bems\.[a-z_]+)` \|', BEMS_DESIGN.read_text(encoding='utf-8'), re.M))
    return names


def validate(d, expected=None, isolation=True):
    errors = []
    def require(ok, message):
        if not ok:
            errors.append(message)
    tables = {t['name']: t for t in d['tables']}
    require(len(tables) == len(d['tables']), 'Duplicate table')
    if expected is not None:
        require(set(tables) == expected, f'Design inventory mismatch: missing={sorted(expected-set(tables))}, extra={sorted(set(tables)-expected)}')
    columns = {}
    for name, table in tables.items():
        cols = {c['name']: c for c in table['columns']}
        columns[name] = cols
        require(len(cols) == len(table['columns']), f'{name}: duplicate column')
        require(all(c.get('label') and c.get('type') for c in cols.values()), f'{name}: incomplete field')
        require(cols.get('id', {}).get('type') == 'bigint' and cols.get('id', {}).get('nullable') is False, f'{name}: invalid id')
        require(bool(table.get('retention')), f'{name}: missing retention')
        require(any(c['table'] == name and c['kind'] == 'PK' and c['columns'] == ['id'] for c in d['constraints']), f'{name}: missing PK')
        if table['scope'] == 'generation':
            require(all(k in cols and not cols[k]['nullable'] for k in SCOPE), f'{name}: missing scope')
            require(any(r['source'] == name and r['columns'] == SCOPE and r['target'] == 'core.data_generation' and r['target_columns'] == ['workspace_id', 'id'] for r in d['relations']), f'{name}: missing generation anchor')
    for c in d['constraints']:
        require(c['table'] in tables, f'Unknown constraint table {c["table"]}')
        require(set(c['columns']) <= set(columns.get(c['table'], {})), f'Unknown constraint columns: {c}')
        require(c['kind'] not in ['CHECK', 'SERVICE/DB_POLICY', 'UK_PARTIAL'] or bool(c['expression']), f'Empty rule {c}')
    for r in d['relations']:
        if r['source'] not in tables or r['target'] not in tables:
            errors.append(f'Unknown FK table {r}')
            continue
        a, b = columns[r['source']], columns[r['target']]
        fields_ok = set(r['columns']) <= set(a) and set(r['target_columns']) <= set(b)
        require(fields_ok, f'Unknown FK field {r}')
        require(len(r['columns']) == len(r['target_columns']), f'FK arity {r}')
        if fields_ok:
            for x, y in zip(r['columns'], r['target_columns']):
                require(a[x]['type'] == b[y]['type'], f'FK type {r["source"]}.{x} -> {r["target"]}.{y}')
        require(any(c['table'] == r['target'] and c['kind'] in ['PK', 'UK'] and c['columns'] == r['target_columns'] for c in d['constraints']), f'FK target lacks full unique key: {r}')
        if tables[r['source']]['scope'] == 'generation' and tables[r['target']]['scope'] == 'generation':
            require(r['columns'][:2] == SCOPE and r['target_columns'][:2] == SCOPE, f'Cross-generation FK risk: {r}')
        require(r['on_delete'] == 'RESTRICT', f'Unexpected cascading deletion {r}')
    for name in ['core.request_receipt', 'core.audit_event']:
        cols = columns.get(name, {})
        require(cols.get('actor_user_id', {}).get('nullable') is True, f'{name}: guest actor requires nullable user')
        require(all(k in cols and not cols[k]['nullable'] for k in ['actor_kind', 'actor_key']), f'{name}: missing actor identity')
    require(any(r['source'] == 'mes.work_order' and r['target'] == 'mes.production_plan_line' for r in d['relations']), 'Missing plan-to-order FK')
    for name in ['core.job_run', 'core.audit_event']:
        require(columns.get(name, {}).get('workspace_id', {}).get('nullable') is True, f'{name}: cleanup cannot detach')
    for st in d['states']:
        require(st['column'] in columns.get(st['table'], {}), f'Unknown state field {st}')
    for code in d.get('code_lists', []):
        if code['target'] != '공통 단위':
            require(code['column'] in columns.get(code['target'], {}), f'Unknown code-list field {code}')
    if isolation:
        errors.extend(audit(d))
        for name, cols in columns.items():
            for column, field in cols.items():
                if column.endswith(('_month', '_year', '_week')) or column in {'effective_from', 'effective_to', 'period_from', 'period_to'}:
                    require(field['type'] in {'varchar(4)', 'varchar(7)', 'varchar(8)'}, f'{name}.{column}: calendar key must be string')
                    require(any(c['table'] == name and c['kind'] == 'CHECK' and re.search(r'\b'+column+r'\s*~', c['expression']) for c in d['constraints']), f'{name}.{column}: missing calendar format CHECK')
        obsolete = {'fems.energy_allocation': 'execution_id', 'mes.production_plan': 'sales_plan_id',
                    'erp.shipment_line': 'packing_unit_id', 'fems.energy_baseline': 'item_id'}
        for name, column in obsolete.items():
            require(column not in columns.get(name, {}), f'{name}: obsolete column {column}')
            require(not any(c['table'] == name and re.search(r'\b'+column+r'\b', json.dumps(c, ensure_ascii=False)) for c in d['constraints']), f'{name}: stale rule referring to {column}')
    if d.get('task') in LATER_THAN_014B or d.get('version') in {'0.8.0', '0.9.0', '0.9.1', '0.10.0', '0.11.0', '0.12.0'}:
        errors.extend(validate_accounting(d))
    if d.get('task') in LATER_THAN_008B or d.get('version') in {'0.9.0', '0.9.1', '0.10.0', '0.11.0', '0.12.0'}:
        errors.extend(validate_screen_gaps(d))
    if d.get('task') in LATER_THAN_023A:
        errors.extend(validate_qms(d))
    if d.get('task') in LATER_THAN_024A:
        errors.extend(validate_wms(d))
    if d.get('task') == 'FS-025a':
        errors.extend(validate_bems(d))
    return errors


def validate_bems(d):
    """FS-025 설계 계약: 교차 스키마 FK 없음·관측 구간 유일(진행 멱등)·활성 경보 1건·명령 불변 이력·모듈 키."""
    errors = []
    cs, ts = d['constraints'], {t['name']: {c['name']: c for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('FS-025: ' + message)
    def unique(table, columns):
        return any(c['table'] == table and c['kind'] == 'UK' and c['columns'] == SCOPE + columns for c in cs)
    require(unique('bems.energy_reading', ['meter_id', 'period_start']), 'one energy reading per meter hour')
    require(unique('bems.environment_reading', ['sensor_id', 'period_start']), 'one environment reading per sensor hour')
    require(any(c['table'] == 'bems.alarm' and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + ['alarm_rule_id', 'sensor_id']
                and c['expression'].endswith("WHERE status <> 'cleared'") for c in cs), 'one open alarm per rule and sensor')
    require('bems.setpoint' not in ts, 'setpoints are control commands, not a separate table (FS-025 13장 3)')
    require(not any(r['source'].startswith('bems.') and r['target'].split('.')[0] not in {'bems', 'core'} for r in d['relations']), 'no FK from bems to other business schemas')
    require(any(c['table'] == 'core.workspace_module' and c['kind'] == 'CHECK' and "'bems'" in c['expression'] for c in cs), 'module key bems')
    return errors


def validate_wms(d):
    """FS-024 설계 계약: 교차 스키마 FK 없음·원천 반영 멱등 부분 유니크·스냅샷 원천·잔량 테이블 없음·모듈 키."""
    errors = []
    cs, ts = d['constraints'], {t['name']: {c['name']: c for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('FS-024: ' + message)
    def partial(table, column, predicate):
        return any(c['table'] == table and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + [column]
                   and c['expression'].endswith('WHERE ' + predicate) for c in cs)
    require(partial('wms.stock_document', 'source_key', "document_type <> 'REVERSAL'"), 'one posting per source (D14)')
    require(partial('wms.stock_document', 'reverses_document_id', 'reverses_document_id IS NOT NULL'), 'one reversal per document')
    require(partial('wms.warehouse', 'purpose', 'is_active'), 'one active warehouse per purpose')
    require(partial('wms.storage_location', 'warehouse_id', 'is_default'), 'one default location per warehouse')
    require('lot_no' in ts.get('wms.stock_move', {}) and not any(k.endswith('lot_id') for k in ts.get('wms.stock_move', {})), 'LOT is a snapshot code, not an id')
    require(not any(n.startswith('wms.') and ('balance' in n or 'stock_level' in n) for n in ts), 'no stored balance table (ledger is the source)')
    require(not any(r['source'].startswith('wms.') and r['target'].split('.')[0] not in {'wms', 'core'} for r in d['relations']), 'no FK from wms to other business schemas')
    require(any(c['table'] == 'core.workspace_module' and c['kind'] == 'CHECK' and "'wms'" in c['expression'] for c in cs), 'module key wms')
    return errors


def validate_qms(d):
    """FS-023 설계 계약: 교차 스키마 FK 없음·게시/보류 부분 유니크·스냅샷 컬럼·모듈 키."""
    errors = []
    cs, ts = d['constraints'], {t['name']: {c['name']: c for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('FS-023: ' + message)
    def partial(table, column, predicate):
        return any(c['table'] == table and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + [column]
                   and c['expression'].endswith('WHERE ' + predicate) for c in cs)
    require(partial('qms.inspection_spec', 'item_code', "status = 'published'"), 'one published spec per item')
    require(partial('qms.inspection', 'lot_no', "status = 'draft'"), 'one draft inspection per LOT')
    require(partial('qms.quality_hold', 'lot_no', "status = 'held'"), 'one active hold per LOT')
    for table in ('qms.inspection', 'qms.quality_hold'):
        require('lot_no' in ts.get(table, {}) and not any(k.endswith('lot_id') for k in ts.get(table, {})), f'{table}: LOT is a snapshot code, not an id')
    require(not any(r['source'].startswith('qms.') and r['target'].split('.')[0] not in {'qms', 'core'} for r in d['relations']), 'no FK from qms to other business schemas')
    require(any(c['table'] == 'core.workspace_module' and c['kind'] == 'CHECK' and "'qms'" in c['expression'] for c in cs), 'module key qms')
    return errors


def validate_accounting(d):
    """Check design contracts, not execution of business policies or PostgreSQL."""
    errors = []
    def require(ok, message):
        if not ok:
            errors.append('FS-014b: '+message)
    tables = {t['name']: t for t in d['tables']}
    required = {'erp.'+n for n in ['receivable','receipt','receipt_apply','payable','payment','payment_apply',
                                  'purchase_invoice','purchase_invoice_line','tax_invoice','account','posting_rule']}
    require(required <= set(tables), 'missing accounting tables')
    if not required <= set(tables):
        return errors
    cols = {n: {c['name']: c for c in t['columns']} for n,t in tables.items()}
    constraints = d['constraints']
    def unique(t, fields):
        return any(c['table']==t and c['kind']=='UK' and c['columns']==SCOPE+fields for c in constraints)
    def policy(t, reason):
        return any(c['table']==t and c['kind']=='SERVICE/DB_POLICY' and c['reason']==reason and c['expression'] for c in constraints)
    for name in required:
        for c in cols[name].values():
            require(not any(word in c['name'] for word in ['balance','remaining','written_off','fifo','cached']), name+': forbidden persisted balance/state feature')
            if c['name'].endswith('amount') or c['name']=='unit_price':
                require(c['type'].startswith('numeric('), name+': amount must be numeric')
        if any(c['name'].endswith('amount') or c['name']=='unit_price' for c in cols[name].values()):
            require('currency' in cols[name],name+': missing currency')
            require(any(c['table']==name and c['kind']=='CHECK' and c['expression']=="currency = 'KRW'" for c in constraints),name+': missing KRW CHECK')
    for ledger, cash, parent, parent_id in [('receivable','receipt','erp.sales_record','sales_record_id'),('payable','payment','erp.purchase_invoice','purchase_invoice_id')]:
        lt,ct,at='erp.'+ledger,'erp.'+cash,'erp.'+cash+'_apply'
        require('status' not in cols[lt] and 'cancelled_at' not in cols[lt],lt+': status must be derived from balance/source')
        require(not any(s['table']==lt for s in d['states']),lt+': persisted state declaration forbidden')
        require(unique(lt,[parent_id]),lt+': source must be unique')
        require(any(r['source']==lt and r['target']==parent and r['columns']==SCOPE+[parent_id,'partner_id','currency'] for r in d['relations']),lt+': source/partner/currency FK required')
        require('cancelled_at' not in cols[at] and 'status' not in cols[at],at+': apply cancellation must be physical delete')
        require(unique(at,['apply_key']),at+': missing idempotency key')
        for target,ref in [(lt,ledger+'_id'),(ct,cash+'_id')]:
            require(any(r['source']==at and r['target']==target and r['columns']==SCOPE+[ref,'partner_id','currency'] for r in d['relations']),at+': missing same-party/currency parent FK')
        for reason in ['회계 잠금 순서','소명 양쪽 합계 한도','소명 물리 삭제 및 감사','소명 재요청 중복 차단','소명 행별 비저장 미리보기']:
            require(policy(at,reason),at+': missing SERVICE policy '+reason)
        require(policy(lt,'원금 파생 및 불변') and policy(lt,'잔액·상태 조회 파생'),lt+': missing immutable/derived policy')
        require(policy(ct,'수금·지급 금액 확정과 소명 분리'),ct+': missing post-confirm apply policy')
    tax='erp.tax_invoice'
    require(unique(tax,['sales_record_id']),'tax invoice must be unique per sale')
    require('purchase_invoice_id' not in cols[tax],'tax invoice must be sales-only')
    require(any(s['table']==tax and s['values']==['pending','issued'] for s in d['states']),'tax invoice must have exactly two states')
    require(policy(tax,'세금계산서 선후 및 취소 계약'),'missing tax sequencing/cancellation policy')
    require(policy('erp.sales_record','매출 취소 계약'),'missing sale cancellation contract')
    require(policy('erp.purchase_invoice','채무 파생 생성 및 매입 취소'),'missing purchase cancellation contract')
    require(any(c['target']=='erp.account' and set(c['values'])=={'AR','PRODUCT_SALES','VAT_PAYABLE','BANK','RAW_MATERIAL','VAT_RECEIVABLE','AP'} for c in d['code_lists']),'account catalog must contain only seven supported codes')
    require(any(c['target']=='erp.posting_rule' and set(c['values'])=={'SALE','RECEIPT','PURCHASE','PAYMENT'} for c in d['code_lists']),'posting types must be exactly four')
    require(not {'condition','expression','result','journal_id'} & set(cols['erp.posting_rule']),'posting rules must not become an engine or stored journal')
    expected_rules = {('SALE','1','DEBIT','AR','TOTAL'),('SALE','2','CREDIT','PRODUCT_SALES','SUPPLY'),('SALE','3','CREDIT','VAT_PAYABLE','TAX'),
                      ('RECEIPT','1','DEBIT','BANK','APPLY'),('RECEIPT','2','CREDIT','AR','APPLY'),
                      ('PURCHASE','1','DEBIT','RAW_MATERIAL','SUPPLY'),('PURCHASE','2','DEBIT','VAT_RECEIVABLE','TAX'),('PURCHASE','3','CREDIT','AP','TOTAL'),
                      ('PAYMENT','1','DEBIT','AP','APPLY'),('PAYMENT','2','CREDIT','BANK','APPLY')}
    expressions = [c['expression'] for c in constraints if c['table']=='erp.posting_rule' and c['kind']=='CHECK']
    pattern = r"transaction_kind = '([A-Z]+)' AND line_no = ([0-9]+) AND entry_side = '([A-Z]+)' AND account_code = '([A-Z_]+)' AND amount_basis = '([A-Z]+)'"
    matches = [match for expression in expressions for match in re.findall(pattern,expression)]
    require(len(matches)==10 and set(matches)==expected_rules,'posting CHECK must encode ten exact fixed combinations')
    require(policy('erp.posting_rule','B층 고정 규칙·비저장 미리보기'),'missing non-persistent preview policy')
    for c in constraints:
        if c['table'] in required and c['kind']=='CHECK':
            require(not re.search(r'\b(SUM|SELECT)\s*[( ]',c['expression'],re.I),'cross-row aggregate masquerading as CHECK')
    return errors


def validate_screen_gaps(d):
    """FS-008b shape contracts; SERVICE execution remains outside static checks."""
    errors=[]
    def require(ok,message):
        if not ok: errors.append('FS-008b: '+message)
    ts={t['name']:{c['name']:c for c in t['columns']} for t in d['tables']}
    cs=d['constraints']
    require('core.dashboard_layout' not in ts,'dashboard layout must be removed')
    for t in ['fems.meter','fems.meter_channel','fems.energy_reading']:
        require('owner_module' not in ts.get(t,{}),'obsolete owner '+t)
    require(not any('owner_module' in json.dumps(x) for key in ['tables','relations','constraints','states','code_lists'] for x in d[key]),'stale active owner reference')
    a=ts.get('fems.energy_allocation',{})
    require('kwh' not in a and a.get('quantity',{}).get('type')=='numeric(20,6)','allocation quantity')
    require(a.get('unit',{}).get('type')=='varchar(10)' and a.get('unit',{}).get('nullable') is False,'allocation unit')
    require(any(c['table']=='fems.energy_allocation' and c['kind']=='CHECK' and c['expression']=='quantity >= 0' for c in cs),'nonnegative quantity CHECK')
    for t in ['fems.energy_reading','fems.energy_allocation']:
        require(any(r['source']==t and r['target']=='fems.meter_channel' and r['columns']==SCOPE+['meter_channel_id','unit'] and r['target_columns']==SCOPE+['id','unit'] for r in d['relations']),'unit-preserving FK '+t)
    for t,c in [('erp.partner','payment_term_days'),('erp.receivable','due_date'),('erp.payable','due_date'),('erp.purchase_invoice','due_date')]:
        require(ts.get(t,{}).get(c,{}).get('nullable') is True,'nullable terms/due '+t)
    require(any(c['table']=='erp.partner' and c['kind']=='CHECK' and c['expression']=='payment_term_days >= 0' for c in cs),'nonnegative nullable payment terms')
    require(any(c['table']=='erp.item' and c['kind']=='CHECK' and c['expression']=="tax_category IN ('TAXABLE','ZERO','EXEMPT')" for c in cs),'tax categories')
    policies={c['reason']:c for c in cs if c['kind']=='SERVICE/DB_POLICY'}
    for name in ['FS-008b 채권 만기 스냅샷','FS-008b 채무 만기 스냅샷','FS-008b 매입 만기 우선순위','FS-008b 설비 동시 점유 방지','TX-10 양품 초과 패킹 거부','고정 세율 출처','다중 에너지원 배분 단위']:
        require(name in policies,'missing SERVICE policy '+name)
    require(ts.get('mes.work_order',{}).get('bom_version_id',{}).get('nullable') is True,'optional BOM')
    require(any(c['table']=='mes.lot' and c['kind']=='UK' and c['columns']==SCOPE+['work_order_id'] for c in cs),'one LOT per work order')
    require('core.workspace_module' in ts,'keep app toggle')
    require(not any(c in ts.get('erp.quotation',{}) for c in ['is_latest','is_current']),'derived quotation revision')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--report', type=Path, default=ROOT/'docs/db/validation-report.json')
    args = parser.parse_args()
    raw = args.schema.read_bytes()
    d = json.loads(raw)
    errors = validate(d, design_names(d.get('task')))
    by_schema = {}
    for t in d['tables']:
        schema = t['name'].split('.')[0]
        by_schema[schema] = by_schema.get(schema, 0) + 1
    report = dict(task=d['task'], validation='정적 메타데이터 검증 + FS-013 R1~R6', database_applied=False,
                  tables=len(d['tables']), tables_by_schema=dict(sorted(by_schema.items())),
                  columns=sum(len(t['columns']) for t in d['tables']), foreign_keys=len(d['relations']),
                  constraints_and_policies=len(d['constraints']), source_sha256=hashlib.sha256(raw).hexdigest(), errors=errors,
                  not_tested=['실제 DDL 적용', 'PostgreSQL CHECK 구문·트리거 동작', '동시성·성능·권한·마이그레이션', 'Excel 네이티브 앱 동작', 'SERVICE 정책 실행·소명 동시성·금액 계산', '법정 세무·회계 기준 적합성'])
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
