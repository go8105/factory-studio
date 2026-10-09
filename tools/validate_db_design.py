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
# 병합 순서(2026-09-30): FS-028a(SPC) 다음 FS-026a(WMS 확장). 마지막 작업 ID가 FS-026a여도 SPC를 포함한다.
# FS-040(런처 평가, core.app_review)은 FS-026a 뒤다. FS-030a(GW) 다음 FS-029a(CMMS).
LATER_THAN_014B = {'FS-014b', 'FS-008b', 'FS-008c', 'FS-023a', 'FS-024a', 'FS-025a', 'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
LATER_THAN_008B = {'FS-008b', 'FS-008c', 'FS-023a', 'FS-024a', 'FS-025a', 'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
LATER_THAN_023A = {'FS-023a', 'FS-024a', 'FS-025a', 'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
LATER_THAN_024A = {'FS-024a', 'FS-025a', 'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
LATER_THAN_025A = {'FS-025a', 'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
LATER_THAN_028A = {'FS-028a', 'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}
QMS_DESIGN = ROOT/'docs/modules/qms/QMS_모듈설계_FS-023.md'
WMS_DESIGN = ROOT/'docs/modules/wms/WMS_모듈설계_FS-024.md'
BEMS_DESIGN = ROOT/'docs/modules/bems/BEMS_모듈설계_FS-025.md'
SPC_DESIGN = ROOT/'docs/modules/spc/SPC_모듈설계_FS-028.md'
CMMS_DESIGN = ROOT/'docs/modules/cmms/CMMS_모듈설계_FS-029.md'
REVIEW_DESIGN = ROOT/'docs/plan/런처평가_한줄평_FS-040.md'


def at_least(task, gate):
    """일괄 개발(W…) 단계는 그 앞의 모든 검사를 켠다. 새 작업 ID를 집합마다 더하지 않는다."""
    return task.startswith(('W', 'GW-')) or task in gate


def gate_task(d):
    """목표 설계(DSN)는 base_task(지금 schema.json의 작업 ID)로 기존 검사를 모두 켠다."""
    return d.get('base_task') or d.get('task')


def target_names():
    """목표 설계에서 새로 생긴 테이블은 `docs/modules/*/*_DSN-*.md` 표의 첫 칸에 적는다."""
    names = set()
    for doc in sorted(ROOT.glob('docs/modules/*/*_DSN-*.md')):
        names |= set(re.findall(r'^\| `([a-z]+\.[a-z_]+)` \|', doc.read_text(encoding='utf-8'), re.M))
    return names


def validate_target(d):
    """schema-target.json 계약: 실제 DB 기록(migration_revision)이 없고, 기준 작업이 지금 schema.json과 같다."""
    errors = []
    current = json.loads((ROOT/'docs/db/schema-metadata/schema.json').read_text(encoding='utf-8'))
    if d.get('migration_revision') is not None:
        errors.append('target: migration_revision must be null (설계 전용)')
    if d.get('base_task') != current.get('task'):
        errors.append(f"target: base_task {d.get('base_task')} != schema.json task {current.get('task')} — 실제 DB가 바뀌면 목표 파일 기준도 옮긴다")
    return errors


def design_names(task='FS-014'):
    names = set(re.findall(r'^\| `((?:core|mes|erp|fems)\.[a-z_]+)` \|', DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, LATER_THAN_014B):
        document = ROOT/'docs/db/스키마_재구성_FS-014b.md'
        names |= set(re.findall(r'^\| `(erp\.[a-z_]+)` \|', document.read_text(encoding='utf-8'), re.M))
    if at_least(task, LATER_THAN_008B):
        names.discard('core.dashboard_layout')
    if at_least(task, LATER_THAN_023A):
        names |= set(re.findall(r'^\| `(qms\.[a-z_]+)` \|', QMS_DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, LATER_THAN_024A):
        names |= set(re.findall(r'^\| `(wms\.[a-z_]+)` \|', WMS_DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, LATER_THAN_025A):
        names |= set(re.findall(r'^\| `(bems\.[a-z_]+)` \|', BEMS_DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, LATER_THAN_028A):
        names |= set(re.findall(r'^\| `(spc\.[a-z_]+)` \|', SPC_DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, {'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}):
        names |= set(re.findall(r'^\| `(core\.[a-z_]+)` \|', REVIEW_DESIGN.read_text(encoding='utf-8'), re.M))
    if at_least(task, {'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}):
        doc = ROOT/'docs/modules/wms/WMS_모듈설계_FS-026.md'
        names |= set(re.findall(r'^### 3\.[1-5] (wms\.[a-z_]+)', doc.read_text(encoding='utf-8'), re.M))
    if at_least(task, {'FS-030a', 'FS-029a', 'W0-1'}):
        doc = ROOT/'docs/modules/gw/GW_모듈설계_FS-030.md'
        names |= set(re.findall(r'^\| `(gw\.[a-z_]+)` \|', doc.read_text(encoding='utf-8'), re.M))
    if at_least(task, {'FS-029a', 'W0-1'}):
        names |= set(re.findall(r'^\| `(cmms\.[a-z_]+)` \|', CMMS_DESIGN.read_text(encoding='utf-8'), re.M))
    return names


def expected_names(d):
    """이 설계 파일이 가질 수 있는 표 이름. 일괄 개발(W…)·목표 설계는 DSN 설계 문서의 표도 포함한다."""
    task = gate_task(d)
    return design_names(task) | (target_names() if d.get('target') or task.startswith(('W', 'GW-')) else set())


def validate(d, expected=None, isolation=True):
    errors = []
    task = gate_task(d)
    def require(ok, message):
        if not ok:
            errors.append(message)
    tables = {t['name']: t for t in d['tables']}
    require(len(tables) == len(d['tables']), 'Duplicate table')
    if expected is not None:
        if task.startswith(('W', 'GW-')) and not d.get('target'):
            # 일괄 개발: 제품 DB는 단계마다 자란다. 설계에 없는 표만 막는다.
            require(set(tables) <= expected, f'Design inventory mismatch: extra={sorted(set(tables)-expected)}')
        else:
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
    if task in LATER_THAN_014B or d.get('version') in {'0.8.0', '0.9.0', '0.9.1', '0.10.0', '0.11.0', '0.12.0', '0.13.0', '0.14.0', '0.15.0', '0.15.0-gw', '0.16.0', '0.17.0', '0.18.0'}:
        errors.extend(validate_accounting(d))
    if task in LATER_THAN_008B or d.get('version') in {'0.9.0', '0.9.1', '0.10.0', '0.11.0', '0.12.0', '0.13.0', '0.14.0', '0.15.0', '0.15.0-gw', '0.16.0', '0.17.0', '0.18.0'}:
        errors.extend(validate_screen_gaps(d))
    if at_least(task, LATER_THAN_023A):
        errors.extend(validate_qms(d))
    if at_least(task, LATER_THAN_024A):
        errors.extend(validate_wms(d))
    if at_least(task, LATER_THAN_025A):
        errors.extend(validate_bems(d))
    if at_least(task, LATER_THAN_028A):
        errors.extend(validate_spc(d))
    if at_least(task, {'FS-026a', 'FS-040', 'FS-030a', 'FS-029a', 'W0-1'}):
        from validate_fs026a import validate_extension
        errors.extend(validate_extension(d))
    if at_least(task, {'FS-030a', 'FS-029a', 'W0-1'}):
        from validate_fs030a import validate_gw
        errors.extend(validate_gw(d))
    if at_least(task, {'FS-029a', 'W0-1'}):
        errors.extend(validate_cmms(d))
    if 'erp.journal_entry' in {t['name'] for t in d['tables']}:
        errors.extend(validate_erp_dsn11(d))
    if 'mes.pop_import' in {t['name'] for t in d['tables']}:
        errors.extend(validate_mes_dsn12(d))
    if 'wms.pop_import' in {t['name'] for t in d['tables']}:
        errors.extend(validate_wms_dsn13(d))
    if 'qms.ncr' in {t['name'] for t in d['tables']}:
        errors.extend(validate_qms_dsn14(d))
    if 'fems.alarm' in {t['name'] for t in d['tables']}:
        errors.extend(validate_fems_dsn15(d))
    if 'bems.demand_plan' in {t['name'] for t in d['tables']}:
        errors.extend(validate_bems_dsn16(d))
    if 'spc.spec_violation' in {t['name'] for t in d['tables']}:
        errors.extend(validate_spc_dsn17(d))
    if 'cmms.technician' in {t['name'] for t in d['tables']}:
        errors.extend(validate_cmms_dsn21(d))
    if 'pop.entry' in {t['name'] for t in d['tables']}:
        errors.extend(validate_pop_dsn22(d))
    if 'tms.dispatch' in {t['name'] for t in d['tables']}:
        errors.extend(validate_tms_dsn23(d))
    if 'plm.eco' in {t['name'] for t in d['tables']}:
        errors.extend(validate_plm_dsn24(d))
    if 'crm.opportunity' in {t['name'] for t in d['tables']}:
        errors.extend(validate_crm_dsn25(d))
    if 'scm.forecast_run' in {t['name'] for t in d['tables']}:
        errors.extend(validate_scm_dsn26(d))
    if 'elb.request' in {t['name'] for t in d['tables']}:
        errors.extend(validate_elb_dsn27(d))
    if 'eip.kpi' in {t['name'] for t in d['tables']}:
        errors.extend(validate_eip_dsn28(d))
    if 'rws.request' in {t['name'] for t in d['tables']}:
        errors.extend(validate_rws_dsn29(d))
    if 'hr.employee' in {t['name'] for t in d['tables']}:
        errors.extend(validate_hr_dsn30(d))
    if d.get('target'):
        errors.extend(validate_integration_dsn90(d))
    if 'gw.authority_rule' in {t['name'] for t in d['tables']}:
        errors.extend(validate_gw_dsn31(d))
    return errors


def validate_erp_dsn11(d):
    """DSN-11 ERP 보강 계약: 재고 원장 없음(Q1)·자동 전표 원천 1건(Q3)·역분개 1건·확정 1건(원가·부가세·예산)·잔액 비저장·달력 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-11: ' + message)
    def partial(t, cols, words):
        return any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + cols and all(w in c['expression'] for w in words) for c in cs)
    def policy(t, reason):
        return any(c['table'] == t and c['kind'] == 'SERVICE/DB_POLICY' and c['reason'] == reason for c in cs)
    require(not any(n.startswith('erp.') and any(w in n for w in ('stock', 'inventory_ledger', 'warehouse')) for n in ts), 'ERP must not own stock ledgers (Q1, FS-024 D13)')
    require(not any(n.startswith('erp.') and n.split('.')[1] in ('payroll', 'payslip', 'attendance', 'hr_employee') for n in ts), 'payroll/attendance belong to HR (D79)')
    require(partial('erp.journal_entry', ['source_kind', 'source_id'], ["status <> 'reversed'"]), 'one live auto journal per source (Q3)')
    require(partial('erp.journal_entry', ['reversal_of_id'], ['reversal_of_id IS NOT NULL']), 'one reversal per entry')
    require(policy('erp.journal_entry', '전표 확정·불변(F45)') and policy('erp.journal_entry', '자동 전표 즉시 + 일괄(Q3)'), 'journal confirm/immutability and posting policies')
    require(any(c['table'] == 'erp.journal_line' and c['kind'] == 'CHECK' and 'amount > 0' in c['expression'] for c in cs), 'journal lines are positive amounts with side')
    for t, col in [('erp.cost_run', 'cost_month'), ('erp.vat_return', 'vat_period'), ('erp.budget', 'budget_year')]:
        require(partial(t, [col], ["status = 'confirmed'"]), f'{t}: one confirmed version per period')
    for t in ('erp.receivable_adjust', 'erp.payable_adjust'):
        require(any(c['table'] == t and c['kind'] == 'UK' and c['columns'] == SCOPE + ['apply_key'] for c in cs), t + ': idempotency key')
    for t in ('erp.receivable', 'erp.payable', 'erp.purchase_order', 'erp.receivable_adjust', 'erp.payable_adjust'):
        require(not any(w in col for col in ts.get(t, ()) for w in ('balance', 'remaining', 'received_qty', 'open_qty')), t + ': balances/progress are derived, not stored')
    require(policy('erp.purchase_order', '발주 진행 파생'), 'PO receipt progress derived from WMS')
    require(policy('erp.purchase_invoice', '매입 경로 둘 다 허용(Q4)'), 'purchase paths PO_RECEIPT + DIRECT (Q4)')
    require(policy('erp.cost_run', '원가 확정·재계산(Q5)'), 'cost run policy (Q5)')
    require(any(s['table'] == 'erp.tax_invoice' and 'transmitted' in s['values'] for s in d['states']), 'tax invoice simulated transmission states (Q6)')
    require(not any(c['table'] == 'erp.account' and c['kind'] == 'CHECK' and "account_code = 'AR'" in c['expression'] for c in cs), 'fixed 7-account CHECK removed')
    require(all(r['target'].split('.')[0] in ('erp', 'core') for r in rs if r['source'].startswith('erp.')), 'ERP FKs stay inside erp/core anchors')
    return errors


def validate_mes_dsn12(d):
    """DSN-12 MES 보강 계약: 스캔 원장은 POP(Q1)·재고는 WMS(Q2)·자재 LOT 스냅샷(Q4)·유효 라벨 1건·금형 타수 파생·POP 가져오기 멱등."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-12: ' + message)
    def partial(t, cols, word):
        return any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + cols and word in c['expression'] for c in cs)
    require(not any(n.startswith('mes.') and ('scan' in n or 'stock' in n) for n in ts), 'scan logs belong to POP (Q1), stock to WMS (Q2)')
    require(any(c['table'] == 'mes.pop_import' and c['kind'] == 'UK' and c['columns'] == SCOPE + ['pop_entry_ref'] for c in cs), 'POP import is idempotent per entry')
    require(any(c['table'] == 'mes.pop_import' and c['kind'] == 'SERVICE/DB_POLICY' and c['reason'] == 'POP 가져오기 재검증(Q1)' for c in cs), 'POP entries re-validated by MES rules')
    require('material_lot_no' in ts.get('mes.material_issue', ()), 'material issue takes WMS LOT number snapshot (Q4)')
    require(partial('mes.label_print', ['label_kind', 'barcode_value'], "status = 'VALID'"), 'one valid label per target')
    require(not any(w in col for col in ts.get('mes.mold', ()) for w in ('shot_count', 'current_shots', 'accumulated')), 'mold shots are derived from usage')
    require(partial('mes.downtime', ['equipment_id'], 'ended_at IS NULL'), 'one open downtime per equipment')
    require(any(c['table'] == 'mes.material_adjustment' and c['reason'] == '비계획 입출고 경계(Q2)' for c in cs), 'unplanned moves recorded by MES, applied by WMS')
    require(all(r['target'].split('.')[0] in ('mes', 'core') for r in d['relations'] if r['source'].startswith('mes.')), 'MES FKs stay inside mes/core anchors')
    return errors


def validate_wms_dsn13(d):
    """DSN-13 WMS 보강 계약: 잔량 비저장·LOT 품목별(Q3)·LOT 활성 보류 1건·예약당 피킹 1건·월 마감(Q6)·POP 가져오기 멱등(Q1)."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-13: ' + message)
    def has(t, kind, cols, word=''):
        return any(c['table'] == t and c['kind'] == kind and c['columns'] == SCOPE + cols and word in c['expression'] for c in cs)
    require(not any(c['table'] == 'wms.item' and "lot_tracked = (item_class = 'FG')" in c['expression'] for c in cs), 'LOT tracking is per item (Q3)')
    require(has('wms.lot', 'UK', ['item_id', 'lot_no']), 'LOT master unique per item')
    require(not any(w in col for col in ts.get('wms.lot', ()) for w in ('qty', 'quantity', 'balance')), 'LOT quantity comes from the ledger')
    require(has('wms.lot_hold', 'UK_PARTIAL', ['lot_id'], 'released_at IS NULL'), 'one active hold per LOT')
    require(has('wms.pick_order', 'UK', ['reservation_id']), 'one pick per reservation')
    require(has('wms.stock_period', 'UK', ['period_month']) and any(c['table'] == 'wms.stock_period' and c['reason'] == '재고 월 마감(Q6)' for c in cs), 'monthly stock close (Q6)')
    require(has('wms.pop_import', 'UK', ['pop_entry_ref']), 'POP import idempotent (Q1)')
    require(not any(n.startswith('wms.') and 'scan' in n for n in ts), 'scan logs belong to POP (Q1)')
    return errors


def validate_qms_dsn14(d):
    """DSN-14 QMS 보강 계약: 수입·출하 기준 분리·AQL Ac/Re·수입 판정은 WMS가 읽음(Q1)·NCR→CAPA·클레임 QMS 소유(Q4)·공정 검사는 MES(MES Q5)."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-14: ' + message)
    require('inspection_kind' in ts.get('qms.inspection_spec', ()) and 'inspection_kind' in ts.get('qms.inspection', ()), 'inspection kinds (incoming/outgoing)')
    require(any(c['table'] == 'qms.inspection' and c['kind'] == 'CHECK' and 'reject_number = accept_number + 1' in c['expression'] for c in cs), 'AQL Ac/Re shape (Q2)')
    require(not any(n.startswith('qms.') and ('aql' in n or 'sampling_table' in n) for n in ts), 'AQL table is code, not DB')
    require(any(c['table'] == 'qms.inspection' and c['reason'] == '수입 검사 → WMS(Q1)' for c in cs), 'incoming result read by WMS (Q1)')
    require(any(r['source'] == 'qms.capa' and r['target'] == 'qms.ncr' for r in d['relations']), 'CAPA belongs to NCR (Q3)')
    require('qms.claim' in ts, 'claims owned by QMS (Q4)')
    require(not any(n.startswith('qms.') and 'process_inspection' in n for n in ts), 'process inspection belongs to MES (MES Q5)')
    require(not any(w in col for col in ts.get('qms.gauge', ()) for w in ('next_due', 'last_calibrated')), 'calibration due is derived from history')
    return errors


def validate_fems_dsn15(d):
    """DSN-15 FEMS 보강 계약: TOU 계약전력·확정 1건(검토·명세서·비용 배분)·진행 경보 1건·환산/배출 계수 분리·1시간 계측 유지(Q2)."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-15: ' + message)
    def partial(t, cols, word):
        return any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + cols and word in c['expression'] for c in cs)
    require(any(c['table'] == 'fems.tariff' and 'contract_kw > 0' in c['expression'] for c in cs), 'TOU tariff needs contract power (Q1)')
    for t, col in [('fems.energy_review', 'review_month'), ('fems.ghg_inventory', 'inventory_year'), ('fems.cost_run', 'cost_month')]:
        require(partial(t, [col], "status = 'confirmed'"), f'{t}: one confirmed version per period')
    require(partial('fems.alarm', ['alarm_rule_id'], "status <> 'CLEARED'"), 'one open alarm per rule')
    require(any(c['table'] == 'fems.energy_review' and c['reason'] == '환산·배출 계수 분리' for c in cs), 'PRIMARY and EMISSION factors stay separate')
    require(not any(n.startswith('fems.') and ('15m' in n or 'quarter_hour' in n or 'demand_15' in n) for n in ts), '1-hour metering kept (Q2)')
    require(not any(w in col for col in ts.get('fems.saving_project', ()) for w in ('period_from', 'period_to')), 'saving comparison uses dates, not calendar keys')
    return errors


def validate_bems_dsn16(d):
    """DSN-16 BEMS 보강 계약: 휴일은 core 공통·업무 FK 없음(Q1)·피크 감축은 승인 후 제어(Q2)·스케줄 대상 하나·확정 1건(배분·보고서)."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name'] for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-16: ' + message)
    require('core.holiday' in ts and not any(n != 'core.holiday' and n.endswith('.holiday') for n in ts), 'one shared holiday calendar in core (Q1)')
    require(not any(r['target'] == 'core.holiday' for r in rs), 'business schemas read holidays by date, no FK (FS-013 §6)')
    require(any(c['table'] == 'bems.demand_plan' and c['reason'] == '피크 감축 승인(Q2)' for c in cs), 'peak curtailment needs approval (Q2)')
    require(any(c['table'] == 'bems.demand_plan' and c['kind'] == 'UK_PARTIAL' and 'fems_alarm_ref' in c['columns'] for c in cs), 'one plan per FEMS alarm')
    require(any(c['table'] == 'bems.schedule_slot' and '(hvac_unit_id IS NULL) <> (lighting_circuit_id IS NULL)' in c['expression'] for c in cs), 'schedule targets exactly one device')
    for t, col in [('bems.cost_run', 'cost_month'), ('bems.energy_review', 'review_month')]:
        require(any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + [col] and "status = 'confirmed'" in c['expression'] for c in cs), f'{t}: one confirmed version per month')
    require(not any(n.startswith('bems.') and ('complaint' in n or 'request' in n) for n in ts), 'occupant complaints excluded (Q5)')
    return errors


def validate_spc_dsn17(d):
    """DSN-17 SPC 보강 계약: 관리도 종류·n 범위(Q1·Q2)·계량/계수 부분군 하나·규칙 1~8(Q3)·규격 이탈은 측정값당 1건(Q4)·계수 표·능력 지표 비저장(보고서 스냅샷만)."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-17: ' + message)
    require('chart_type' in ts.get('spc.characteristic', ()), 'chart type per characteristic (Q1·Q2)')
    require(any(c['table'] == 'spc.subgroup' and 'inspected_qty > 0' in c['expression'] and 'xbar IS NOT NULL' in c['expression'] for c in cs), 'subgroup is variable or attribute, not both')
    require(any(c['table'] == 'spc.signal' and c['expression'] == 'rule BETWEEN 1 AND 8' for c in cs), 'Nelson rules 1-8 (Q3)')
    require(any(c['table'] == 'spc.spec_violation' and c['kind'] == 'UK' and c['columns'] == SCOPE + ['subgroup_id', 'seq'] for c in cs), 'one spec violation per measurement (Q4)')
    require(not any(n.startswith('spc.') and ('constant' in n or 'coefficient' in n) for n in ts), 'chart constants are code, not DB')
    require(not any(w in col for col in ts.get('spc.characteristic', ()) for w in ('cpk', 'ppk')), 'capability is computed or snapshotted in reports only')
    return errors


def validate_cmms_dsn21(d):
    """DSN-21 CMMS 보강 계약: 금형 출처(Q1)·기준별 PM 주기(Q2)·점검표 완료 조건(Q3)·신호 출처 확장 없음(Q4)·비용 비저장(Q5)·재고는 WMS(Q6)."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-21: ' + message)
    require(any(c['table'] == 'cmms.asset' and c['expression'] == "(source = 'MES_MOLD') = (asset_type = 'MOLD')" for c in cs), 'molds come from MES (Q1)')
    require(any(c['table'] == 'cmms.pm_plan' and "(trigger_kind = 'CALENDAR') = (interval_days IS NOT NULL)" in c['expression'] for c in cs), 'PM interval matches trigger (Q2)')
    require(any(c['table'] == 'cmms.checklist_result' and c['reason'] == '점검표 완료 조건(Q3)' for c in cs), 'checklist must be complete before PM completion (Q3)')
    require(any(c['table'] == 'cmms.work_order' and c['expression'].startswith("source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN'") and 'FEMS' not in c['expression'] for c in cs), 'signal sources unchanged (DSN-29 adds RWS_REQUEST only) — FEMS/BEMS equipment alarms excluded (Q4)')
    require(not any(w in col for t in ('cmms.work_order', 'cmms.asset') for col in ts.get(t, ()) for w in ('total_cost', 'labor_cost', 'parts_cost')), 'maintenance cost is derived (Q5)')
    require(not any(w in col for col in ts.get('cmms.spare_part', ()) for w in ('on_hand', 'stock_qty', 'quantity')), 'spare part stock is read from WMS (Q6)')
    return errors


def validate_pop_dsn22(d):
    """DSN-22 POP 계약: 다른 업무 스키마에 FK·쓰기 없음·확정 입력 번호 유일(가져오기 멱등 키)·반영 솔루션별 종류·MES/WMS 가져오기 종류 일치·취소 1건·모듈 키(Q1·Q2)."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name'] for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-22: ' + message)
    def expr(t, word):
        return next((c['expression'] for c in cs if c['table'] == t and c['kind'] == 'CHECK' and word in c['expression']), '')
    require(all(r['target'].split('.')[0] in ('pop', 'core') for r in rs if r['source'].startswith('pop.')), 'POP FKs stay inside pop/core anchors')
    require(any(c['table'] == 'pop.entry' and c['kind'] == 'UK' and c['columns'] == SCOPE + ['entry_no'] for c in cs), 'entry_no unique (pop_entry_ref idempotency key)')
    pop_kinds = expr('pop.entry', "target_solution = 'MES'")
    for target in ('mes', 'wms'):
        imp = expr(f'{target}.pop_import', 'entry_kind IN')
        kinds = set(re.findall(r"'([A-Z]+)'", imp.split(' AND result')[0]))
        side = pop_kinds.split("target_solution = 'WMS'")[0 if target == 'mes' else 1]
        require(kinds and kinds == set(re.findall(r"'([A-Z]+)'", side)) - {'MES', 'WMS'}, f'{target}.pop_import kinds match POP {target.upper()} entry kinds')
    require(any(c['table'] == 'pop.entry' and c['kind'] == 'UK_PARTIAL' and 'cancels_entry_id' in c['columns'] for c in cs), 'one cancel per entry')
    require(any(c['table'] == 'pop.entry' and c['reason'] == '확정·지연 가져오기(Q1)' for c in cs), 'lazy pull by MES/WMS (Q1)')
    require('pop.operator' in ts, 'POP owns its operators (Q2)')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'pop'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key pop')
    return errors


def validate_tms_dsn23(d):
    """DSN-23 TMS 계약: ERP·WMS 경계(FK 없음·번호 스냅샷, Q1·Q6)·출하지시당 살아 있는 배송 1건·용차는 운송사·운송사 월 확정 정산 1건(Q5)·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    def require(ok, message):
        if not ok:
            errors.append('DSN-23: ' + message)
    def partial(t, cols, word):
        return any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + cols and word in c['expression'] for c in cs)
    require(all(r['target'].split('.')[0] in ('tms', 'core') for r in rs if r['source'].startswith('tms.')), 'TMS FKs stay inside tms/core anchors')
    require(any(c['table'] == 'tms.dispatch' and c['reason'] == 'ERP·WMS 경계(Q1·Q6)' for c in cs), 'TMS does not change ERP/WMS (Q1·Q6)')
    require(partial('tms.dispatch_stop', ['shipment_order_no'], "NOT IN ('FAILED', 'CANCELLED')"), 'one live delivery per shipment order')
    require(any(c['table'] == 'tms.vehicle' and "(ownership = 'HIRED') = (carrier_id IS NOT NULL)" in c['expression'] for c in cs), 'hired vehicle needs carrier (Q2)')
    require(partial('tms.settlement', ['carrier_id', 'settle_month'], "status = 'confirmed'"), 'one confirmed settlement per carrier month (Q5)')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'tms'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key tms')
    return errors


def validate_plm_dsn24(d):
    """DSN-24 PLM 계약: 배포는 ECO로만·현재 배포 리비전 1개·리비전은 ECO 1건에만·다른 업무 스키마 FK 없음·파일 저장 없음(Q2)·M-BOM은 MES(Q4)·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-24: ' + message)
    for t, parent in [('plm.part_revision', 'part_id'), ('plm.document_revision', 'document_id')]:
        require(any(c['table'] == t and 'eco_id IS NOT NULL' in c['expression'] for c in cs), f'{t}: release only through ECO')
        require(any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + [parent] and "status = 'RELEASED'" in c['expression'] for c in cs), f'{t}: one current released revision')
    require(any(c['table'] == 'plm.eco_item' and c['kind'] == 'UK_PARTIAL' and 'part_revision_id' in c['columns'] for c in cs), 'a revision belongs to one ECO')
    require(all(r['target'].split('.')[0] in ('plm', 'core') for r in rs if r['source'].startswith('plm.')), 'PLM FKs stay inside plm/core anchors')
    require(not any(w in col for cols in (v for n, v in ts.items() if n.startswith('plm.')) for col in cols for w in ('file_path', 'file_url', 'blob', 'content_bytes')), 'no file storage (Q2)')
    require(not any(n.startswith('plm.') and ('mbom' in n or 'process' in n or 'routing' in n) for n in ts), 'M-BOM and routing belong to MES (Q4)')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'plm'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key plm')
    return errors


def validate_crm_dsn25(d):
    """DSN-25 CRM 계약: 견적·수주는 ERP·클레임은 QMS(테이블 금지)·다른 스키마 FK 없음·ERP 처리 상태 비저장(Q2)·수주는 ERP 수주 번호 필수·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-25: ' + message)
    require(not any(n.startswith('crm.') and any(w in n for w in ('quotation', 'sales_order', 'claim', 'invoice')) for n in ts), 'quotations/orders belong to ERP, claims to QMS')
    require(all(r['target'].split('.')[0] in ('crm', 'core') for r in rs if r['source'].startswith('crm.')), 'CRM FKs stay inside crm/core anchors')
    require(not any(w in col for col in ts.get('crm.quote_request', ()) for w in ('imported', 'erp_quotation', 'erp_status')), 'ERP import state is read, not stored (Q2)')
    require(any(c['table'] == 'crm.opportunity' and "stage <> 'WON' OR (probability = 100 AND erp_order_no IS NOT NULL)" in c['expression'] for c in cs), 'won needs ERP order (Q2)')
    require(any(c['table'] == 'crm.inquiry' and c['expression'] == "status <> 'TRANSFERRED' OR kind = 'QUALITY'" for c in cs), 'only quality inquiries go to QMS (Q4)')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'crm'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key crm')
    return errors


def validate_scm_dsn26(d):
    """DSN-26 SCM 계약: 계획·분석만 — 판매계획·생산계획·발주·재고 원장 테이블 금지(Q1)·확정 1건(예측·S&OP)·재고 정책 품목당 제안 1건·FK 없음·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name'] for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-26: ' + message)
    def partial(t, cols, word):
        return any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + cols and word in c['expression'] for c in cs)
    require(not any(n.startswith('scm.') and any(w in n for w in ('purchase', 'sales_plan', 'production_plan', 'work_order', 'stock_move', 'reservation')) for n in ts), 'SCM plans and analyses only — execution stays in ERP/MES/WMS (Q1)')
    require(partial('scm.forecast_run', ['base_month'], "status = 'confirmed'") and partial('scm.sop_plan', ['sop_month'], "status = 'confirmed'"), 'one confirmed forecast and S&OP per month')
    require(partial('scm.inventory_policy', ['item_code'], "status = 'proposed'"), 'one proposed policy per item (Q5)')
    require(any(c['table'] == 'scm.forecast_line' and 'adjust_reason' in c['expression'] for c in cs), 'adjustments need a reason')
    require(all(r['target'].split('.')[0] in ('scm', 'core') for r in rs if r['source'].startswith('scm.')), 'SCM FKs stay inside scm/core anchors')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'scm'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key scm')
    return errors


def validate_elb_dsn27(d):
    """DSN-27 ELB 계약: 자체 발주·매입·재고 테이블 금지(Q1)·긴급 구매는 카드 내역 1건(Q6)·재고 품목은 WMS 코드·단계당 승인 1건·FK 없음·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name'] for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-27: ' + message)
    require(not any(n.startswith('elb.') and any(w in n for w in ('purchase_order', 'invoice', 'stock', 'payable')) for n in ts), 'no POs, invoices or stock in ELB — ERP/WMS own them (Q1)')
    require(any(c['table'] == 'elb.request' and c['expression'] == "(kind = 'EMERGENCY') = (card_txn_ref IS NOT NULL)" for c in cs), 'emergency purchase needs card transaction (Q6)')
    require(any(c['table'] == 'elb.request' and c['kind'] == 'UK_PARTIAL' and 'card_txn_ref' in c['columns'] for c in cs), 'one request per card transaction')
    require(any(c['table'] == 'elb.catalog_item' and '(is_stock = (wms_item_code IS NOT NULL))' in c['expression'] for c in cs), 'stock items link WMS item code')
    require(any(c['table'] == 'elb.approval' and c['kind'] == 'UK' and c['columns'] == SCOPE + ['request_id', 'step'] for c in cs), 'one decision per request step (Q2)')
    require(all(r['target'].split('.')[0] in ('elb', 'core') for r in rs if r['source'].startswith('elb.')), 'ELB FKs stay inside elb/core anchors')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'elb'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key elb')
    return errors


def validate_eip_dsn28(d):
    """DSN-28 EIP 계약: 공지는 GW(Q1 — eip 공지 테이블 금지)·KPI 실적 비저장(Q2)·사람 연결은 HR 사원 코드(Q3-1)·위젯 배치는 eip에만(core 금지, FS-008b)·확정 보고서 1건·FK 없음·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-28: ' + message)
    require(not any(n.startswith('eip.') and any(w in n for w in ('notice', 'board', 'banner')) for n in ts), 'notices belong to GW (Q1)')
    require(not any(w in col for col in ts.get('eip.kpi', ()) for w in ('actual', 'value')), 'KPI actuals are read, not stored (Q2)')
    require(all('hr_employee_code' in ts.get(t, ()) for t in ('gw.person', 'crm.sales_rep', 'eip.person_link', 'elb.approver')), 'people link through HR employee code (Q3-1)')
    require('core.dashboard_layout' not in ts and 'eip.widget_layout' in ts, 'widget layout lives in eip, not core (Q5, FS-008b)')
    require(any(c['table'] == 'eip.management_report' and c['kind'] == 'UK_PARTIAL' and "status = 'confirmed'" in c['expression'] for c in cs), 'one confirmed management report per month (Q4)')
    require(all(r['target'].split('.')[0] in ('eip', 'core') for r in rs if r['source'].startswith('eip.')), 'EIP FKs stay inside eip/core anchors')
    require(not any(c['table'] in ('core.workspace_module', 'core.app_review') and "'eip'" in c.get('expression', '') for c in cs), 'EIP is the portal home, not a toggleable module (DSN-28 Q8): no module key eip')
    return errors


def validate_rws_dsn29(d):
    """DSN-29 RWS 계약: 영상·사진·POP 호출 없음(Q1·Q2)·현장 출동은 CMMS가 가져감(Q3 — RWS→CMMS FK·쓰기 없음)·고객 현장은 고객사 필수(Q4)·게시 가이드 1건(Q5)·주 담당 1명·완료 1건·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-29: ' + message)
    require(not any(n.startswith('rws.') and any(w in n for w in ('video', 'media', 'attachment', 'photo', 'call')) for n in ts), 'no video/photo/POP-call tables (Q1·Q2)')
    require(any(c['table'] == 'rws.request' and "source_kind IN ('DIRECT', 'CMMS_WO', 'QMS_NCR')" in c['expression'] for c in cs), 'request sources are direct/CMMS/QMS only (Q2)')
    require(any(c['table'] == 'cmms.work_order' and 'RWS_REQUEST' in c['expression'] and c['kind'] == 'UK_PARTIAL' for c in cs), 'CMMS imports one work order per RWS field visit (Q3)')
    require(any(c['table'] == 'rws.request' and "(site_kind = 'CUSTOMER') = (customer_code IS NOT NULL)" in c['expression'] for c in cs), 'customer site requires customer code (Q4)')
    require(any(c['table'] == 'rws.guide' and c['kind'] == 'UK_PARTIAL' and "status = 'published'" in c['expression'] for c in cs), 'one published guide per code (Q5)')
    require(any(c['table'] == 'rws.assignment' and c['kind'] == 'UK_PARTIAL' and "role = 'PRIMARY'" in c['expression'] for c in cs), 'one active primary expert per request')
    require(any(c['table'] == 'rws.resolution' and c['kind'] == 'UK' and c['columns'][-1] == 'request_id' for c in cs), 'one resolution per request')
    require('hr_employee_code' in ts.get('rws.expert', ()), 'internal experts link by HR employee code')
    require(all(r['target'].split('.')[0] in ('rws', 'core') for r in rs if r['source'].startswith('rws.')), 'RWS FKs stay inside rws/core anchors')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'rws'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key rws')
    return errors


def validate_hr_dsn30(d):
    """DSN-30 HR 계약: 민감 정보 칸 없음(D79)·신고 테이블 없음·사원 코드 유일(사람 원천 Q1)·확정 근태 마감·급여 월 1건(Q4)·근태 1일 1건(Q2)·HR FK는 hr/core만·모듈 키."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-30: ' + message)
    sensitive = ('resident', 'rrn', 'ssn', 'bank', 'account_no', 'address', 'family', 'phone')
    require(not any(n.startswith('hr.') and any(w in col for col in cols for w in sensitive) for n, cols in ts.items()), 'no sensitive personal data columns (D79)')
    require(not any(n.startswith('hr.') and any(w in n for w in ('insurance_report', 'tax_report', 'year_end')) for n in ts), 'no insurance/tax filing tables (D79)')
    require(any(c['table'] == 'hr.employee' and c['kind'] == 'UK' and c['columns'][-1] == 'employee_code' for c in cs), 'employee code is unique — HR is the people source (Q1)')
    require(any(c['table'] == 'hr.attendance' and c['kind'] == 'UK' and c['columns'][-2:] == ['employee_id', 'work_date'] for c in cs), 'one attendance row per employee-day (Q2)')
    for t, label in (('hr.attendance_close', 'attendance close'), ('hr.payroll_run', 'payroll run')):
        require(any(c['table'] == t and c['kind'] == 'UK_PARTIAL' and "status = 'confirmed'" in c['expression'] for c in cs), f'one confirmed {label} per month (Q4)')
    require(any(c['table'] == 'hr.payslip' and 'net_pay = gross_pay - deduction_total' in c['expression'] for c in cs), 'net pay equals gross minus deductions')
    require(all(r['target'].split('.')[0] in ('hr', 'core') for r in rs if r['source'].startswith('hr.')), 'HR FKs stay inside hr/core anchors')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'hr'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key hr')
    return errors


# DSN-90 통합 흐름이 기대는 받는 쪽 칸 — (흐름, 표, 칸). docs/plan/통합검증_DSN-90.md 4장
DSN90_FLOW_COLUMNS = [
    ('S1', 'crm.account', 'erp_partner_code'), ('S1', 'erp.partner', 'crm_account_code'), ('S1', 'erp.quotation', 'crm_quote_request_no'),
    ('S1', 'erp.sales_plan', 'scm_forecast_ref'), ('S1', 'mes.production_plan', 'sales_plan_code'), ('S1', 'mes.pop_import', 'pop_entry_ref'),
    ('S1', 'wms.pop_import', 'pop_entry_ref'), ('S1', 'tms.dispatch_stop', 'shipment_order_no'),
    ('S2', 'erp.purchase_request', 'source_ref'), ('S2', 'tms.dispatch_stop', 'po_no'), ('S2', 'tms.dispatch_stop', 'inbound_notice_no'),
    ('S2', 'wms.lot_hold', 'source_ref'), ('S2', 'erp.purchase_invoice', 'source_ref'),
    ('S3', 'cmms.asset', 'source_code'), ('S3', 'cmms.work_order', 'source_ref'), ('S3', 'rws.request', 'source_ref'),
    ('S4', 'qms.ncr', 'source_ref'), ('S4', 'qms.claim', 'crm_inquiry_no'), ('S4', 'qms.change_notice', 'plm_eco_no'),
    ('S5', 'elb.request', 'card_txn_ref'),
    ('S6', 'erp.journal_entry', 'source_ref'), ('S6', 'eip.person_link', 'hr_employee_code'),
    ('S7', 'fems.production_record', 'source_key'), ('S7', 'bems.demand_plan', 'fems_alarm_ref'),
    ('S9', 'gw.approval_document', 'source_digest'), ('S9', 'erp.approval_evidence', 'approval_digest'), ('S9', 'gw.organization_unit', 'code'),
    ('S8', 'erp.item', 'plm_part_no'), ('S8', 'mes.item', 'plm_part_no'), ('S8', 'wms.item', 'plm_part_no'), ('S8', 'mes.bom_version', 'plm_bom_ref'),
] + [('S6', t, c) for t, c in (('mes.worker', 'hr_employee_code'), ('pop.operator', 'hr_employee_code'), ('cmms.technician', 'hr_employee_code'),
     ('gw.person', 'hr_employee_code'), ('crm.sales_rep', 'hr_employee_code'), ('erp.employee', 'hr_employee_code'), ('rws.expert', 'hr_employee_code'),
     ('elb.approver', 'hr_employee_code'), ('elb.request', 'requester_hr_code'), ('qms.capa', 'owner_hr_code'))]
# 같은 원천을 두 번 가져오지 않게 하는 유일 키(멱등)
DSN90_IDEMPOTENT = [('mes.pop_import', 'pop_entry_ref'), ('wms.pop_import', 'pop_entry_ref'), ('erp.partner', 'crm_account_code'),
    ('erp.quotation', 'crm_quote_request_no'), ('qms.claim', 'crm_inquiry_no'), ('qms.change_notice', 'plm_eco_no'), ('qms.ncr', 'source_ref'),
    ('erp.purchase_request', 'source_ref'), ('erp.purchase_invoice', 'source_ref'), ('cmms.work_order', 'source_ref'), ('cmms.asset', 'source_code'),
    ('rws.request', 'source_ref'), ('erp.journal_entry', 'source_ref'), ('wms.stock_document', 'source_key'), ('bems.demand_plan', 'fems_alarm_ref'),
    ('elb.request', 'card_txn_ref'), ('fems.production_record', 'source_key'),
    ('gw.approval_document', 'source_no'), ('erp.approval_evidence', 'gw_document_no'), ('gw.notification', 'event_key'), ('gw.chat_message', 'client_key')]
# 원천 종류 값 — (표, CHECK에 있어야 할 값)
DSN90_CODES = [('erp.purchase_request', "'MES'"), ('erp.purchase_request', "'CMMS'"), ('erp.purchase_request', "'ELB'"),
    ('gw.approval_document', "'ERP_PO'"), ('gw.approval_document', "'PLM_ECO'"),
    ('erp.purchase_invoice', "'FREIGHT'"), ('erp.purchase_invoice', "'INDIRECT'"), ('wms.stock_document', "'CMMS_ISSUE'"),
    ('erp.journal_entry', "'PAYROLL'"), ('erp.journal_entry', "'CARD'"), ('cmms.work_order', "'RWS_REQUEST'"), ('qms.inspection', "'WMS'")]


def validate_integration_dsn90(d):
    """DSN-90 통합 계약: 흐름 S1~S8의 받는 쪽 칸 존재·가져오기 멱등 UK·원천 종류 값. 교차 FK 0은 audit_schema_isolation이 본다."""
    errors = []
    cs = d['constraints']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    for flow, t, col in DSN90_FLOW_COLUMNS:
        if col not in ts.get(t, ()):
            errors.append(f'DSN-90 {flow}: {t}.{col} missing (cross-solution flow needs the source code snapshot)')
    for t, col in DSN90_IDEMPOTENT:
        if not any(c['table'] == t and c['kind'] in ('UK', 'UK_PARTIAL') and col in c['columns'] for c in cs):
            errors.append(f'DSN-90: {t}.{col} needs a unique key so the same source is imported once')
    for t, value in DSN90_CODES:
        if not any(c['table'] == t and c['kind'] == 'CHECK' and value in c['expression'] for c in cs):
            errors.append(f'DSN-90: {t} source kind {value} missing')
    return errors


def validate_gw_dsn31(d):
    """DSN-31 GW 계약: 사람·조직 원천 HR(D81 — GW 인사·근태·소속 이력 표 금지, 조직은 HR 스냅샷)·첨부/외부 메일/서명 표 없음·결재 대상 확장·병렬(단계 순번 유일 키 없음)·알림/메시지 중복 0·TEAM 공간 core·ERP 확정 통제·GW→core 사용자 FK 없음."""
    errors = []
    cs, rs = d['constraints'], d['relations']
    ts = {t['name']: {c['name'] for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('DSN-31: ' + message)
    def uk(t, cols, kind='UK'):
        return any(c['table'] == t and c['kind'] == kind and c['columns'][-len(cols):] == cols for c in cs)
    gw = [n for n in ts if n.startswith('gw.')]
    require(not any(w in n for n in gw for w in ('attendance', 'leave', 'payroll', 'person_assignment', 'employee')), 'people, org history, attendance and leave belong to HR (D81)')
    require('gw.organization_unit' in ts and 'organization_unit_id' in ts.get('gw.person', ()), 'GW org is an HR department snapshot (D81)')
    require(not any(w in n for n in gw for w in ('attachment', 'mail', 'signature', 'export_job')), 'no attachment, mail or e-signature tables (excluded / real-adoption track)')
    require(any(c['table'] == 'gw.approval_document' and c['kind'] == 'CHECK' and "'PLM_ECO'" in c['expression'] and "'ERP_PO'" in c['expression'] for c in cs), 'approval kinds include ERP PO/expense and PLM ECO (Q2)')
    require(not uk('gw.approval_step', ['document_id', 'seq']) and uk('gw.approval_step', ['document_id', 'person_id']), 'parallel approval: several people per stage, one row per person (Q3)')
    require(uk('gw.notification', ['recipient_id', 'event_key']) and uk('gw.chat_message', ['channel_id', 'seq']), 'notification and message idempotency (Q5)')
    if d.get('target') or 'core.workspace_membership' in ts:
        require(any(c['table'] == 'core.workspace' and c['kind'] == 'CHECK' and "'TEAM'" in c['expression'] for c in cs) and uk('core.workspace_membership', ['workspace_id', 'user_id']), 'TEAM space and membership live in core (Q1)')
    require(not any(r['source'].startswith('gw.') and r['target'] == 'core.app_user' for r in rs), 'GW keeps account subjects as strings, no FK to core.app_user')
    if d.get('target') or 'erp.approval_policy' in ts:
        require(any(c['table'] == 'erp.approval_policy' and c['kind'] == 'CHECK' and "'REQUIRED'" in c['expression'] for c in cs) and 'gw_document_no' in ts.get('erp.approval_evidence', ()), 'ERP owns the confirm control and evidence (Q6)')
    return errors


def validate_cmms(d):
    """FS-029 설계 계약: 교차 스키마 FK 없음·설비 원천 1건·신호 1건당 작업지시 1건·PM 계획·예정일 1건·재고 원장 없음·모듈 키."""
    errors = []
    cs, ts = d['constraints'], {t['name'] for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('FS-029: ' + message)
    def partial(table, columns, where):
        return any(c['table'] == table and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + columns and where in c['expression'] for c in cs)
    require(partial('cmms.asset', ['source', 'source_code'], "source <> 'CMMS'"), 'one asset per imported source code (D46)')
    require(partial('cmms.work_order', ['source', 'source_ref'], "status <> 'CANCELLED'"), 'one live work order per signal (D48)')
    require(partial('cmms.work_order', ['pm_plan_id', 'due_on'], "kind = 'PM'"), 'one live PM work order per plan and due date')
    require(not any(n.startswith('cmms.') and ('stock' in n or 'inventory' in n) for n in ts), 'no stock ledger in CMMS (D50, WMS owns stock)')
    require(not any(r['source'].startswith('cmms.') and r['target'].split('.')[0] not in {'cmms', 'core'} for r in d['relations']), 'no FK from cmms to other business schemas')
    require(all(any(c['table'] == t and c['kind'] == 'CHECK' and "'cmms'" in c['expression'] for c in cs) for t in ('core.workspace_module', 'core.app_review')), 'module key cmms')
    return errors


def validate_spc(d):
    """FS-028 설계 계약: 교차 스키마 FK 없음·측정값은 SPC 소유(MES 측정 테이블 없음)·부분군 크기 5·기록 멱등·이상 1건·모듈 키."""
    errors = []
    cs, ts = d['constraints'], {t['name']: {c['name']: c for c in t['columns']} for t in d['tables']}
    def require(ok, message):
        if not ok:
            errors.append('FS-028: ' + message)
    def unique(table, columns):
        return any(c['table'] == table and c['kind'] == 'UK' and c['columns'] == SCOPE + columns for c in cs)
    require(unique('spc.subgroup', ['characteristic_id', 'lot_no', 'measured_at']), 'one subgroup per characteristic, lot and time')
    require(unique('spc.measurement', ['subgroup_id', 'seq']), 'one value per subgroup position')
    require(unique('spc.signal', ['subgroup_id', 'chart', 'rule']), 'one signal per subgroup, chart and rule')
    require(unique('spc.control_limit', ['characteristic_id', 'version']), 'one limit per characteristic version')
    # DSN-17 Q1(목표 설계): n=1(I-MR)·2~10(X̄-R).
    require(any(c['table'] == 'spc.characteristic' and c['kind'] == 'CHECK' and c['expression'] in ('subgroup_size = 5', 'subgroup_size BETWEEN 1 AND 10') for c in cs), 'subgroup size fixed to 5 (13장 1)')
    require(not any(n.startswith('mes.') and 'measure' in n for n in ts), 'measurements are owned by SPC, not MES (D38)')
    require(not any(r['source'].startswith('spc.') and r['target'].split('.')[0] not in {'spc', 'core'} for r in d['relations']), 'no FK from spc to other business schemas')
    require(any(c['table'] == 'core.workspace_module' and c['kind'] == 'CHECK' and "'spc'" in c['expression'] for c in cs), 'module key spc')
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
    # DSN-13 Q2(목표 설계): 다창고 — 용도당 '기본' 창고 1개로 좁힌다.
    require(partial('wms.warehouse', 'purpose', 'is_active') or partial('wms.warehouse', 'purpose', 'is_default AND is_active'), 'one active warehouse per purpose')
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
    # DSN-14(목표 설계): 수입·출하 기준을 따로 — 품목·검사 종류당 게시 1개.
    require(partial('qms.inspection_spec', 'item_code', "status = 'published'") or any(c['table'] == 'qms.inspection_spec' and c['kind'] == 'UK_PARTIAL' and c['columns'] == SCOPE + ['item_code', 'inspection_kind'] and c['expression'].endswith("WHERE status = 'published'") for c in cs), 'one published spec per item')
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
    # DSN-11(목표 설계)은 B층 고정 규칙(계정 7·분개 10·세금계산서 2상태)을 실제 전표로 대체한다 — validate_erp_dsn11이 새 계약을 검사.
    dsn11 = 'erp.journal_entry' in tables
    require(dsn11 or any(s['table']==tax and s['values']==['pending','issued'] for s in d['states']),'tax invoice must have exactly two states')
    require(policy(tax,'세금계산서 선후 및 취소 계약'),'missing tax sequencing/cancellation policy')
    require(policy('erp.sales_record','매출 취소 계약'),'missing sale cancellation contract')
    require(policy('erp.purchase_invoice','채무 파생 생성 및 매입 취소'),'missing purchase cancellation contract')
    require(any(c['target']=='erp.account' and set(c['values'])=={'AR','PRODUCT_SALES','VAT_PAYABLE','BANK','RAW_MATERIAL','VAT_RECEIVABLE','AP'} for c in d['code_lists']),'account catalog must contain only seven supported codes')
    require(dsn11 or any(c['target']=='erp.posting_rule' and set(c['values'])=={'SALE','RECEIPT','PURCHASE','PAYMENT'} for c in d['code_lists']),'posting types must be exactly four')
    require(not {'condition','expression','result','journal_id'} & set(cols['erp.posting_rule']),'posting rules must not become an engine or stored journal')
    expected_rules = {('SALE','1','DEBIT','AR','TOTAL'),('SALE','2','CREDIT','PRODUCT_SALES','SUPPLY'),('SALE','3','CREDIT','VAT_PAYABLE','TAX'),
                      ('RECEIPT','1','DEBIT','BANK','APPLY'),('RECEIPT','2','CREDIT','AR','APPLY'),
                      ('PURCHASE','1','DEBIT','RAW_MATERIAL','SUPPLY'),('PURCHASE','2','DEBIT','VAT_RECEIVABLE','TAX'),('PURCHASE','3','CREDIT','AP','TOTAL'),
                      ('PAYMENT','1','DEBIT','AP','APPLY'),('PAYMENT','2','CREDIT','BANK','APPLY')}
    expressions = [c['expression'] for c in constraints if c['table']=='erp.posting_rule' and c['kind']=='CHECK']
    pattern = r"transaction_kind = '([A-Z]+)' AND line_no = ([0-9]+) AND entry_side = '([A-Z]+)' AND account_code = '([A-Z_]+)' AND amount_basis = '([A-Z]+)'"
    matches = [match for expression in expressions for match in re.findall(pattern,expression)]
    require(dsn11 or (len(matches)==10 and set(matches)==expected_rules),'posting CHECK must encode ten exact fixed combinations')
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
    # DSN-12(목표 설계): LOT 분할(F37)로 "원 LOT 1개"를 조건부 유니크로 바꾼다.
    require(any(c['table']=='mes.lot' and c['columns']==SCOPE+['work_order_id'] and (c['kind']=='UK' or (c['kind']=='UK_PARTIAL' and 'origin_lot_id IS NULL' in c['expression'])) for c in cs),'one LOT per work order')
    require('core.workspace_module' in ts,'keep app toggle')
    require(not any(c in ts.get('erp.quotation',{}) for c in ['is_latest','is_current']),'derived quotation revision')
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--report', type=Path)
    args = parser.parse_args()
    raw = args.schema.read_bytes()
    d = json.loads(raw)
    target = bool(d.get('target'))
    report_path = args.report or ROOT/('docs/db/validation-report-target.json' if target else 'docs/db/validation-report.json')
    # 일괄 개발(W…)에서는 DSN 설계 문서의 표도 제품에 들어올 수 있다.
    expected = expected_names(d)
    errors = validate(d, expected) + (validate_target(d) if target else [])
    by_schema = {}
    for t in d['tables']:
        schema = t['name'].split('.')[0]
        by_schema[schema] = by_schema.get(schema, 0) + 1
    report = dict(task=d['task'], validation='정적 메타데이터 검증 + FS-013 R1~R6', database_applied=False,
                  tables=len(d['tables']), tables_by_schema=dict(sorted(by_schema.items())),
                  columns=sum(len(t['columns']) for t in d['tables']), foreign_keys=len(d['relations']),
                  constraints_and_policies=len(d['constraints']), source_sha256=hashlib.sha256(raw).hexdigest(), errors=errors,
                  not_tested=['실제 DDL 적용', 'PostgreSQL CHECK 구문·트리거 동작', '동시성·성능·권한·마이그레이션', 'Excel 네이티브 앱 동작', 'SERVICE 정책 실행·소명 동시성·금액 계산', '법정 세무·회계 기준 적합성'])
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
