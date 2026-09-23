"""Apply FS-013 relocation as FS-014 (61 tables), never accounting/DDL.

Validate input and candidate before replacement. Preserve exact input bytes in
an exclusive SHA256-named backup. An already applied valid FS-014 is a byte-level
no-op. Invalid/partial/newer versions fail closed. --check computes without writes.
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
S = ['workspace_id', 'generation_id']
# FS-013 §3.2 row-level mapping, subtotal corrected by user: 5 / 2 / 6.
MASTERS = {
    'core.item': ['mes.item', 'erp.item'],
    'core.item_unit_conversion': ['mes.item_unit_conversion', 'erp.item_unit_conversion'],
    'core.equipment': ['mes.equipment', 'fems.equipment'],
    'core.site': ['mes.site', 'fems.site'],
    'core.location': ['mes.location', 'fems.location'],
    'core.meter': ['fems.meter'],
    'core.meter_channel': ['fems.meter_channel'],
    'core.energy_source': ['fems.energy_source'],
}
DROP = {
    'learning.course_version', 'learning.step', 'learning.question', 'learning.attempt',
    'learning.step_progress', 'learning.answer', 'process_map.map_version',
    'process_map.node', 'process_map.edge', 'mes.learning_binding',
    'bems.energy_reading', 'bems.environment_reading',
}
BEFORE = {'core': 19, 'mes': 17, 'erp': 14, 'fems': 6, 'learning': 6, 'process_map': 3, 'bems': 2}
AFTER = {'core': 11, 'mes': 21, 'erp': 16, 'fems': 13}
REMOVED_FK = {('fems.energy_allocation', 'execution_id'), ('mes.production_plan', 'sales_plan_id'),
              ('erp.shipment_line', 'packing_unit_id'), ('fems.energy_baseline', 'item_id')}
RENAMES = {'mes.production_plan': ('sales_plan_id', 'sales_plan_code', '근거 판매계획 코드'),
           'erp.shipment_line': ('packing_unit_id', 'packing_no', '참고 패킹 번호'),
           'fems.energy_baseline': ('item_id', 'item_code', '품목 코드')}


def counts(d):
    return dict(Counter(t['name'].split('.')[0] for t in d['tables']))


def need(ok, message):
    if not ok:
        raise ValueError(message)


def check(d, expected=None, isolation=True):
    errors = validate(d, expected, isolation)
    need(not errors, '\n'.join(errors))


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def transform(original):
    need(original.get('version') == '0.6.0' and original.get('task') == 'FS-005f', 'Expected v0.6.0 / FS-005f')
    need(original.get('migration_revision') is None, 'DB-applied metadata is out of scope')
    need(counts(original) == BEFORE, f'Unexpected input counts: {counts(original)}')
    check(original, isolation=False)
    names = {t['name'] for t in original['tables']}
    need(set(MASTERS) | DROP <= names, 'Missing FS-013 source tables')
    d = copy.deepcopy(original)
    def destinations(name):
        return [] if name in DROP else MASTERS.get(name, [name])
    for section, key in [('tables', 'name'), ('constraints', 'table'), ('states', 'table'), ('code_lists', 'target')]:
        result = []
        for obj in original[section]:
            for dest in destinations(obj[key]):
                clone = copy.deepcopy(obj)
                clone[key] = dest
                result.append(clone)
        d[section] = result
    d['relations'] = []
    removed = set()
    for r in original['relations']:
        if r['source'] in DROP:
            continue
        hit = next((pair for pair in REMOVED_FK if r['source'] == pair[0] and pair[1] in r['columns']), None)
        if hit:
            removed.add(hit)
            continue
        need(r['target'] not in DROP, f'Unexpected surviving FK to removed table: {r}')
        for source in destinations(r['source']):
            clone = copy.deepcopy(r)
            clone['source'] = source
            if r['target'] in MASTERS:
                local = source.split('.')[0] + '.' + r['target'].split('.')[1]
                need(local in MASTERS[r['target']], f'No authorized local master: {r}')
                clone['target'] = local
            d['relations'].append(clone)
    need(removed == REMOVED_FK, f'Expected four removed references, found {removed}')
    tables = {t['name']: t for t in d['tables']}
    for table, (old, new, label) in RENAMES.items():
        field = next(c for c in tables[table]['columns'] if c['name'] == old)
        field.update(name=new, label=label, type='varchar(40)', rule='코드 문자열만 보관. 타 솔루션 존재·상태·품목 일치를 강제하지 않는다')
    tables['fems.energy_allocation']['columns'] = [c for c in tables['fems.energy_allocation']['columns'] if c['name'] != 'execution_id']
    constraints = []
    for c in d['constraints']:
        table = c['table']
        if table == 'fems.energy_allocation' and 'execution_id' in json.dumps(c):
            if 'equipment_id' in c['columns'] and c['kind'] == 'UK_PARTIAL':
                c.update(kind='UK', expression='', reason='설비·채널·기간·산정 방법 버전별 배분 중복 차단')
            else:
                continue
        if table == 'erp.shipment_line' and c['kind'] == 'SERVICE/DB_POLICY':
            if 'packing_unit_id' in c['columns']:
                continue
            if 'received PALLET' in c['expression']:
                c.update(expression='ERP 수주 품목·단위 일치; 지시 모든 라인의 출하 합계=지시수량. MES 패킹·입고 상태는 조회하거나 강제하지 않는다', reason='FS-013 독립 출하')
        if table in RENAMES:
            old, new, _ = RENAMES[table]
            c['columns'] = [new if v == old else v for v in c['columns']]
            c['expression'] = re.sub(r'\b' + old + r'\b', new, c['expression'])
        if table == 'core.workspace_module' and c['kind'] == 'CHECK':
            if 'module_key IN' in c['expression']:
                c['expression'] = "module_key IN ('core','mes','erp','fems')"
            elif 'module_key NOT IN' in c['expression']:
                c['expression'] = "module_key <> 'core' OR enabled"
        if table == 'fems.meter' and c['kind'] == 'CHECK' and 'bems' in c['expression']:
            c['expression'] = "owner_module = 'fems'" if 'scope_kind' not in c['expression'] else "scope_kind IN ('factory','site_total')"
        constraints.append(c)
    d['constraints'] = constraints
    def constraint(table, kind, columns, expression, reason):
        d['constraints'].append(dict(table=table, kind=kind, columns=columns, expression=expression, reason=reason))
    for table, (_, new, _) in RENAMES.items():
        constraint(table, 'CHECK', [new], f'{new} IS NULL OR length(btrim({new})) > 0', '선택 코드의 빈 문자열 차단')
    constraint('erp.shipment_line', 'SERVICE/DB_POLICY', ['packing_no'], 'packing_no는 선택 참고 코드다. ERP 내부 중복 번호만 차단하며 MES 데이터와 무결성을 강제하지 않는다', 'FS-013 코드 연결')
    constraint('fems.meter_channel', 'CHECK', ['owner_module'], "owner_module = 'fems'", 'FEMS 단독 계측 소유')
    for code in d['code_lists']:
        if code['target'] == 'core.workspace_module':
            code.update(values=['core', 'mes', 'erp', 'fems'], note='QMS·WMS·BEMS 설명 카드와 도움말은 정적 파일')
        if code['target'] == 'core.role':
            code.update(values=['owner', 'guest', 'admin'], note='플랫폼 역할만 관리. 업무 권한은 솔루션 자체 소유')
    for table in d['tables']:
        if 'guest_cleanup' in table:
            table['guest_cleanup'] = table['guest_cleanup'].replace('업무/학습/FK', '업무/FK').replace('학습/설정', '설정')
    tables['mes.production_plan']['note'] = 'FS-014: ERP 판매계획은 선택 코드이며 확인 상태를 강제하지 않는다'
    tables['erp.shipment_line']['note'] = 'FS-014: ERP 품목·수량 출하. MES 패킹 번호는 선택 참고값'
    tables['fems.energy_baseline']['note'] = 'FS-014: 품목은 코드로 식별하고 생산량은 fems.production_record에서 산출'
    # New independent denominator. No item master or MES execution dependency.
    name = 'fems.production_record'
    base = {c['name']: c for c in tables['fems.energy_allocation']['columns']}
    fields = [copy.deepcopy(base[k]) for k in ['id', *S]] + [
        col('source_key', '생산량 기록 키', 'varchar(100)', rule='동일 원천 기록의 개정은 같은 키와 새 version_no'),
        col('version_no', '기록 버전', 'integer', default='1'),
        col('equipment_id', '생산 설비', 'bigint'),
        col('item_code', '생산 품목 코드', 'varchar(40)', rule='FEMS 자체 입력 코드. MES·ERP FK 없음'),
        col('period_start', '생산 구간 시작', 'timestamptz'),
        col('period_end', '생산 구간 종료', 'timestamptz', rule='반개구간 [시작, 종료)'),
        col('production_qty', '양품 생산량', 'numeric(18,3)', rule='0 허용. 원단위 분모 0은 계산 불가'),
        col('unit', '생산 수량 단위', 'varchar(10)', rule='에너지 단위와 별개. 다른 단위·품목을 무조건 합산하지 않는다'),
        col('status', '상태', 'varchar(20)', default="'draft'", rule='draft / confirmed'),
        col('confirmed_at', '확정 시각', 'timestamptz', nullable=True),
        copy.deepcopy(base['created_at']),
    ]
    d['tables'].append(dict(name=name, label='원단위 산출용 생산량', scope='generation', phase='M2', sub_module='baseline',
                            retention='세대 정리', guest_cleanup='업무 자식 우선 삭제',
                            note='독립 입력. 원천 키별 최신 확정 버전만 사용. 확정 후 불변; 수정은 새 버전', columns=fields))
    for kind, cols, reason in [('PK', ['id'], '기본키'), ('UK', S+['id'], '공간·세대 복합 참조'),
                               ('UK', S+['source_key', 'version_no'], '원천 기록 버전 중복 차단')]:
        constraint(name, kind, cols, '', reason)
    for cols, expr, reason in [(['period_start', 'period_end'], 'period_end > period_start', '양의 반개구간'),
                              (['production_qty'], 'production_qty >= 0', '생산량 음수 차단'),
                              (['version_no'], 'version_no >= 1', '버전은 1부터'),
                              (['source_key', 'item_code', 'unit'], "length(btrim(source_key)) > 0 AND length(btrim(item_code)) > 0 AND length(btrim(unit)) > 0", '빈 식별 코드·단위 차단'),
                              (['status', 'confirmed_at'], "(status = 'draft' AND confirmed_at IS NULL) OR (status = 'confirmed' AND confirmed_at IS NOT NULL)", '상태·확정시각 일치')]:
        constraint(name, 'CHECK', cols, expr, reason)
    constraint(name, 'SERVICE/DB_POLICY', ['source_key', 'version_no', 'status'], '확정 행 UPDATE/DELETE 금지(세대 정리 예외). 수정은 동일 source_key의 새 버전. 원단위 조회는 원천 키별 최대 confirmed version_no만 사용하고 draft는 제외한다', '확정 불변·버전 중복 합산 방지')
    constraint(name, 'SERVICE/DB_POLICY', ['equipment_id', 'item_code', 'unit', 'period_start', 'period_end'], '원천 키 개정 시 설비·품목·단위 고정. 최신 확정 기록끼리 같은 설비·품목·단위의 구간 중복 거부. 에너지와 동일 구간만 비교하고 부분 구간 비례 추정·공정 간 생산량 중복 합산 금지', '입력·집계 정책; DB CHECK가 아님')
    constraint(name, 'SERVICE/DB_POLICY', ['production_qty', 'unit'], '원단위 분모 0은 계산 불가. 단위가 다른 생산량은 검증된 환산 없이 합산 금지. 에너지원 합산은 PRIMARY 환산만 사용하며 EMISSION은 배출량 전용', 'FS-013 독립 원단위')
    for columns, target, target_columns in [(S, 'core.data_generation', ['workspace_id', 'id']),
                                            (S+['equipment_id'], 'fems.equipment', S+['id'])]:
        d['relations'].append(dict(source=name, columns=columns, target=target, target_columns=target_columns,
                                   on_delete='RESTRICT', on_update='RESTRICT', note='FS-014 자체 범위와 설비 참조'))
    d['states'].append(dict(table=name, column='status', values=['draft', 'confirmed'], default='draft', transition='draft→confirmed; 확정 후 불변, 수정은 새 버전'))
    # Existing v0.6.0 omissions: all calendar strings need format CHECKs.
    for table in d['tables']:
        for field in table['columns']:
            column = field['name']
            if column.endswith(('_month', '_year', '_week')) or column in {'effective_from', 'effective_to', 'period_from', 'period_to'}:
                if field['type'] not in {'varchar(4)', 'varchar(7)', 'varchar(8)'}:
                    continue
                pattern = {'varchar(4)': '^[0-9]{4}$', 'varchar(7)': '^[0-9]{4}-(0[1-9]|1[0-2])$',
                           'varchar(8)': '^[0-9]{4}-W(0[1-9]|[1-4][0-9]|5[0-3])$'}[field['type']]
                if not any(c['table'] == table['name'] and c['kind'] == 'CHECK' and re.search(r'\b'+column+r'\s*~', c['expression']) for c in d['constraints']):
                    constraint(table['name'], 'CHECK', [column], f"{column} ~ '{pattern}'", '연·월·주차 문자열 형식 강제 (FS-014 누락 보완)')
    d.update(version='0.7.0', task='FS-014', date='2026-09-22', basis='FS-013 결정 + FS-014 분리 승인; 회계 11개는 FS-014b', migration_revision=None)
    d['sources'].append('FS-014 스키마 재구성 설계서')
    d['change_log'].append(dict(version='0.7.0', task='FS-014', date='2026-09-22',
                               change='마스터 8→13 재배치, 12개 폐기, 교차 FK 제거 및 코드 대체, FEMS 생산량 신설. 61테이블; 회계 11개는 FS-014b', status='정적 검증 대상 / DB 미적용'))
    need(counts(d) == AFTER, f'Unexpected output counts: {counts(d)}')
    check(d, design_names())
    return d


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--schema', type=Path, default=ROOT/'docs/db/schema-metadata/schema.json')
    parser.add_argument('--backup-dir', type=Path)
    parser.add_argument('--check', action='store_true', help='Validate candidate without writing')
    args = parser.parse_args()
    try:
        raw = args.schema.read_bytes()
        d = json.loads(raw)
        if d.get('version') == '0.7.0' and d.get('task') == 'FS-014':
            need(counts(d) == AFTER, 'Invalid already-applied counts')
            check(d, design_names())
            print('FS-014 already applied and valid; no files changed.')
            return 0
        result = transform(d)
        payload = (json.dumps(result, ensure_ascii=False, indent=2)+'\n').encode('utf-8')
        if args.check:
            print(json.dumps({'check': 'passed', 'tables': counts(result), 'total': len(result['tables']), 'written': False}))
            return 0
        # Recheck the source before backup/replacement to catch concurrent edits.
        need(args.schema.read_bytes() == raw, 'Source changed during validation')
        backup_dir = args.backup_dir or args.schema.parent/'backups'
        backup_dir.mkdir(parents=True, exist_ok=True)
        backup = backup_dir/f'schema.before-FS-014.{hashlib.sha256(raw).hexdigest()}.json'
        if backup.exists():
            need(backup.read_bytes() == raw, 'Existing backup content mismatch')
        else:
            with backup.open('xb') as f:
                f.write(raw)
                f.flush()
                os.fsync(f.fileno())
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=args.schema.parent, prefix='.fs014-', delete=False) as f:
                temporary = Path(f.name)
                f.write(payload)
                f.flush()
                os.fsync(f.fileno())
            temporary.chmod(args.schema.stat().st_mode & 0o777)
            need(args.schema.read_bytes() == raw, 'Source changed before replacement')
            os.replace(temporary, args.schema)
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
        print(json.dumps({'applied': 'FS-014', 'tables': counts(result), 'total': len(result['tables']), 'backup': str(backup)}, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError, StopIteration) as exc:
        print(f'ABORT: {exc}')
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
