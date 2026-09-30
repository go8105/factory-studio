"""FS-028a: SPC 5테이블과 core.workspace_module 'spc'를 schema.json에 반영한다(멱등).

근거: docs/modules/spc/SPC_모듈설계_FS-028.md 4장, docs/plan/SPC도입_관리도_결정_FS-028.md(D37~D44).
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""
import json
from pathlib import Path

from apply_fs023a import S, c, col, r
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
OLD_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms','wms','bems')"
NEW_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms','wms','bems','spc')"
MODULE_KEYS = ['core', 'mes', 'erp', 'fems', 'qms', 'wms', 'bems', 'spc']
CODE_FORMAT = "code ~ '^[A-Z][A-Z0-9-]{1,19}$'"
CAUSES = ('MACHINE', 'MATERIAL', 'MAN', 'METHOD', 'MEASUREMENT', 'ENVIRONMENT')


def quoted(values):
    return ', '.join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), 'phase': 'S1'}


def limit(name, label):
    return col(name, label, 'numeric(14,6)')


TABLES = [
    table('spc.characteristic', '관리 특성', 'spc_master', 'FS-028 4.1·D38. 품목·공정·특성·규격. 품목·공정은 MES 코드 스냅샷(FK 없음)', [
        col('code', '특성 코드', 'varchar(20)'),
        col('item_code', '품목 코드', 'varchar(40)', rule='MES 품목 코드 스냅샷'),
        col('item_name', '품목명', 'varchar(100)', rule='스냅샷'),
        col('process_code', '공정 코드', 'varchar(20)', rule='MES 공정 코드 스냅샷'),
        col('name', '특성명', 'varchar(100)'),
        col('unit', '단위', 'varchar(10)'),
        col('lsl', '규격 하한', 'numeric(12,4)', nullable=True),
        col('usl', '규격 상한', 'numeric(12,4)', nullable=True),
        col('target', '목표값', 'numeric(12,4)', nullable=True),
        col('subgroup_size', '부분군 크기', 'smallint', default='5', rule='5 고정(D39)'),
        col('decimals', '표시 소수 자릿수', 'smallint', default='3', rule='0~4'),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ]),
    table('spc.control_limit', '관리 한계', 'spc_master', 'FS-028 4.1·D40. X̄-R 관리 한계 버전. 게시 후 불변, 재산정은 새 버전', [
        col('characteristic_id', '관리 특성', 'bigint'),
        col('version', '버전', 'integer'),
        col('effective_at', '적용 시작', 'timestamptz', rule='게시 때 이 특성의 마지막 유효 부분군 측정 시각. 이보다 늦게 측정한 부분군부터 이 버전으로 판정한다(벽시계와 무관)'),
        col('basis_from', '기준 구간 시작', 'timestamptz'),
        col('basis_to', '기준 구간 종료', 'timestamptz'),
        col('basis_count', '기준 부분군 수', 'integer', rule='유효 부분군 20개 이상'),
        limit('xbar_cl', 'X̄ 중심선'), limit('xbar_ucl', 'X̄ 관리 상한'), limit('xbar_lcl', 'X̄ 관리 하한'),
        limit('r_cl', 'R 중심선'), limit('r_ucl', 'R 관리 상한'), limit('r_lcl', 'R 관리 하한'),
        col('reason', '게시 사유', 'varchar(200)'),
    ]),
    table('spc.subgroup', '부분군', 'measure', 'FS-028 4.2·D39. 공정 실행 1건 안의 한 시각 측정 n=5. LOT·공정·설비는 MES 스냅샷', [
        col('characteristic_id', '관리 특성', 'bigint'),
        col('lot_no', 'LOT 번호', 'varchar(50)', rule='MES 스냅샷'),
        col('item_code', '품목 코드', 'varchar(40)', rule='스냅샷'),
        col('process_code', '공정 코드', 'varchar(20)', rule='스냅샷'),
        col('equipment_code', '설비 코드', 'varchar(40)', rule='스냅샷'),
        col('run_started_at', '공정 실행 시작', 'timestamptz', rule='스냅샷'),
        col('run_ended_at', '공정 실행 종료', 'timestamptz', nullable=True, rule='스냅샷. 진행 중이면 비움'),
        col('measured_at', '측정 시각', 'timestamptz'),
        col('xbar', '평균 X̄', 'numeric(14,6)', rule='측정값 5개 평균(기록 때 계산)'),
        col('r', '범위 R', 'numeric(14,6)', rule='최대 − 최소'),
        col('status', '상태', 'varchar(10)', default="'valid'", rule='valid / void'),
        col('void_reason', '무효 사유', 'varchar(200)', nullable=True),
        col('voided_at', '무효 시각', 'timestamptz', nullable=True),
        col('source', '출처', 'varchar(10)', rule='SEED / MANUAL'),
        col('note', '메모', 'varchar(300)', nullable=True),
    ]),
    table('spc.measurement', '측정값', 'measure', 'FS-028 4.2. 부분군당 5개. 불변', [
        col('subgroup_id', '부분군', 'bigint'),
        col('seq', '순서', 'smallint', rule='1~5'),
        col('value', '측정값', 'numeric(12,4)'),
    ]),
    table('spc.signal', '이상 기록', 'signal', 'FS-028 4.3·D41·D42. 규칙 판정 결과. 발생 → 조치 완료, 부분군 무효 시 무효', [
        col('subgroup_id', '부분군', 'bigint'),
        col('characteristic_id', '관리 특성', 'bigint', rule='부분군의 특성과 같다'),
        col('control_limit_id', '판정 한계', 'bigint', rule='측정 시각에 유효한 버전'),
        col('lot_no', 'LOT 번호', 'varchar(50)', rule='부분군 스냅샷. QMS 배지 조회용'),
        col('chart', '관리도', 'varchar(4)', rule='XBAR / R'),
        col('rule', '판정 규칙', 'smallint', rule='1 한계 밖 · 2 한쪽 연속 9점 · 3 연속 6점 증가·감소'),
        col('value', '판정 값', 'numeric(14,6)'),
        col('detected_at', '발생 시각', 'timestamptz', rule='부분군 측정 시각'),
        col('status', '상태', 'varchar(10)', default="'open'", rule='open / resolved / void'),
        col('cause_category', '원인 분류', 'varchar(12)', nullable=True, rule=' / '.join(CAUSES)),
        col('action', '조치 내용', 'varchar(500)', nullable=True),
        col('resolved_at', '조치 시각', 'timestamptz', nullable=True),
        col('voided_at', '무효 시각', 'timestamptz', nullable=True),
    ]),
]
CH, CL, SG, MS, SI = (t['name'] for t in TABLES)

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [c(t['name'], 'PK', ['id'], reason='기본키'),
                    c(t['name'], 'UK', S + ['id'], reason='공간·세대 복합 참조 대상')]
CONSTRAINTS += [
    c(CH, 'UK', S + ['code'], reason='세대 내 특성 코드 유일'),
    c(CH, 'UK', S + ['item_code', 'process_code', 'name'], reason='품목·공정·특성명 조합 유일'),
    c(CH, 'CHECK', ['code'], CODE_FORMAT, '코드 형식'),
    c(CH, 'CHECK', ['lsl', 'usl'], '(lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl)', '규격 하나 이상, 하한 < 상한'),
    c(CH, 'CHECK', ['target', 'lsl', 'usl'], 'target IS NULL OR ((lsl IS NULL OR target >= lsl) AND (usl IS NULL OR target <= usl))', '목표값은 규격 안'),
    c(CH, 'CHECK', ['subgroup_size'], 'subgroup_size = 5', '부분군 크기 5 고정(13장 1)'),
    c(CH, 'CHECK', ['decimals'], 'decimals BETWEEN 0 AND 4', '표시 자릿수 범위'),
    c(CH, 'SERVICE/DB_POLICY', ['lsl'], '부분군이 있는 특성의 규격·품목·공정은 바꾸지 않는다(409 CHARACTERISTIC_IN_USE). 사용 안 함은 가능', '판정 근거 보존'),
    c(CL, 'UK', S + ['characteristic_id', 'version'], reason='특성별 버전 유일'),
    c(CL, 'UK', S + ['characteristic_id', 'effective_at'], reason='특성별 적용 시작 유일'),
    c(CL, 'CHECK', ['version'], 'version >= 1', '버전은 1부터'),
    c(CL, 'CHECK', ['basis_count'], 'basis_count >= 20', '기준 부분군 20개 이상(D40)'),
    c(CL, 'CHECK', ['basis_from', 'basis_to'], 'basis_from <= basis_to', '기준 구간 순서'),
    c(CL, 'CHECK', ['xbar_lcl', 'xbar_cl', 'xbar_ucl'], 'xbar_lcl < xbar_cl AND xbar_cl < xbar_ucl', 'X̄ 한계 순서'),
    c(CL, 'CHECK', ['r_lcl', 'r_cl', 'r_ucl'], 'r_lcl >= 0 AND r_lcl < r_cl AND r_cl < r_ucl', 'R 한계 순서'),
    c(CL, 'SERVICE/DB_POLICY', ['version'],
      '게시(TX-S2)만 만든다. 기준 구간의 유효 부분군으로 X̿·R̄을 계산(n=5: A2 0.577, D3 0, D4 2.114)하고, 적용 시작 = 게시 때 마지막 유효 부분군의 측정 시각(직전 버전 뒤 새 부분군이 없으면 거부). 게시 시각은 created_at. 게시 후 수정·삭제하지 않는다(세대 정리 제외)', '한계 불변·재산정은 새 버전'),
    c(SG, 'UK', S + ['characteristic_id', 'lot_no', 'measured_at'], reason='같은 실행·시각 중복 방지(기록 멱등)'),
    c(SG, 'CHECK', ['r'], 'r >= 0', '범위 음수 금지'),
    c(SG, 'CHECK', ['status'], "status IN ('valid', 'void')", '상태 값'),
    c(SG, 'CHECK', ['status', 'void_reason', 'voided_at'],
      "(status = 'valid' AND void_reason IS NULL AND voided_at IS NULL) OR (status = 'void' AND void_reason IS NOT NULL AND voided_at IS NOT NULL)", '무효는 사유·시각 필수'),
    c(SG, 'CHECK', ['source'], "source IN ('SEED', 'MANUAL')", '출처 값'),
    c(SG, 'CHECK', ['run_started_at', 'run_ended_at', 'measured_at'],
      'measured_at >= run_started_at AND (run_ended_at IS NULL OR (run_started_at <= run_ended_at AND measured_at <= run_ended_at))', '측정 시각은 공정 실행 기간 안'),
    c(SG, 'SERVICE/DB_POLICY', ['measured_at'],
      '측정 시각은 그 특성의 마지막 유효 부분군보다 늦어야 한다(13장 2). 품목·공정은 특성과 같아야 한다. X̄·R은 측정값에서 계산한 값이다. 값은 불변, 상태만 valid→void(TX-S4)', '순서 강제·값 불변'),
    c(MS, 'UK', S + ['subgroup_id', 'seq'], reason='부분군 내 순서 유일'),
    c(MS, 'CHECK', ['seq'], 'seq BETWEEN 1 AND 5', '순서 범위'),
    c(MS, 'SERVICE/DB_POLICY', ['subgroup_id'], '부분군과 같은 트랜잭션에서 5개를 만든다(TX-S1). 수정·삭제하지 않는다(세대 정리 제외)', '측정값 불변'),
    c(SI, 'UK', S + ['subgroup_id', 'chart', 'rule'], reason='부분군·관리도·규칙당 1건'),
    c(SI, 'CHECK', ['chart'], "chart IN ('XBAR', 'R')", '관리도 값'),
    c(SI, 'CHECK', ['rule'], 'rule BETWEEN 1 AND 3', '규칙 값'),
    c(SI, 'CHECK', ['chart', 'rule'], "rule = 1 OR chart = 'XBAR'", '규칙 2·3은 X̄만'),
    c(SI, 'CHECK', ['status'], "status IN ('open', 'resolved', 'void')", '상태 값'),
    c(SI, 'CHECK', ['cause_category'], f'cause_category IS NULL OR cause_category IN ({quoted(CAUSES)})', '원인 분류 값'),
    c(SI, 'CHECK', ['action'], 'action IS NULL OR char_length(btrim(action)) >= 2', '조치 내용 2자 이상'),
    c(SI, 'CHECK', ['status', 'cause_category', 'action', 'resolved_at', 'voided_at'],
      "(status = 'open' AND cause_category IS NULL AND action IS NULL AND resolved_at IS NULL AND voided_at IS NULL) OR "
      "(status = 'resolved' AND cause_category IS NOT NULL AND action IS NOT NULL AND resolved_at IS NOT NULL AND voided_at IS NULL) OR "
      "(status = 'void' AND voided_at IS NOT NULL)", '상태와 조치·시각 일치'),
    c(SI, 'SERVICE/DB_POLICY', ['status'],
      '발생은 부분군 기록(TX-S1)의 규칙 판정으로만, 조치 완료는 사람만(TX-S3), 무효는 부분군 무효(TX-S4)로만. 조치 완료·무효 후 불변', '이상 수명(D42)'),
    c(SI, 'SERVICE/DB_POLICY', ['control_limit_id'],
      '측정 시각에 유효한 한계 버전(적용 시작 < 측정 시각인 최신). 연속 규칙은 같은 버전 안의 유효 부분군만 센다(13장 3)', '판정 버전'),
    c(SG, 'INDEX', S + ['characteristic_id', 'measured_at'], reason='관리도·순서 검사'),
    c(SI, 'INDEX', S + ['characteristic_id'], reason='FK 조회'),
    c(SI, 'INDEX', S + ['control_limit_id'], reason='FK 조회'),
    c(SI, 'INDEX', S + ['status', 'lot_no'], reason='QMS 배지 조회(미조치 LOT)'),
]

RELATIONS = [dict(source=t['name'], columns=S, target='core.data_generation', target_columns=['workspace_id', 'id'],
                  on_delete='RESTRICT', on_update='RESTRICT', note='같은 참조 범위 유지') for t in TABLES]
RELATIONS += [
    r(CL, ['characteristic_id'], CH, '한계의 특성'),
    r(SG, ['characteristic_id'], CH, '부분군의 특성'),
    r(MS, ['subgroup_id'], SG, '측정값의 부분군'),
    r(SI, ['subgroup_id'], SG, '이상의 부분군'),
    r(SI, ['characteristic_id'], CH, '이상의 특성'),
    r(SI, ['control_limit_id'], CL, '이상을 판정한 한계'),
]

STATES = [
    dict(table=SG, column='status', values=['valid', 'void'], default='valid', transition='valid→void(사유 필수); 무효 후 불변'),
    dict(table=SI, column='status', values=['open', 'resolved', 'void'], default='open',
         transition='open→resolved(원인·조치 필수), open→void, resolved→void(부분군 무효); 그 밖에는 불변'),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if CH in {t['name'] for t in d['tables']}:
        return False
    d['tables'].extend(TABLES)
    d['constraints'].extend(CONSTRAINTS)
    d['relations'].extend(RELATIONS)
    d['states'].extend(STATES)
    for cst in d['constraints']:
        if cst['table'] == 'core.workspace_module' and cst['expression'] == OLD_MODULE_CHECK:
            cst['expression'] = NEW_MODULE_CHECK
    for code in d['code_lists']:
        if code['target'] == 'core.workspace_module' and code['column'] == 'module_key':
            code['values'] = MODULE_KEYS
            code['note'] = 'QMS(FS-023)·WMS(FS-024)·BEMS(FS-025)·SPC(FS-028)는 구현 솔루션. SCM 설명 카드와 도움말은 정적 파일'
    d['code_lists'].extend([
        dict(target=SG, column='source', values=['SEED', 'MANUAL'], default=None, note='시드 / 화면 입력'),
        dict(target=SI, column='chart', values=['XBAR', 'R'], default=None, note='X̄ 관리도 / R 관리도'),
        dict(target=SI, column='cause_category', values=list(CAUSES), default=None, note='설비·자재·작업자·방법·측정·환경(4M1E+측정)'),
    ])
    d.update(version='0.13.0', task='FS-028a', date='2026-09-30', migration_revision='fs028a_spc')
    d['change_log'].append(dict(version='0.13.0', task='FS-028a', date='2026-09-30',
                                change='spc 스키마 5테이블(관리 특성·관리 한계·부분군·측정값·이상 기록), core.workspace_module module_key에 spc 추가. 스키마 간 FK 0건',
                                status='마이그레이션 fs028a_spc 적용 대상'))
    return True


def main():
    d = json.loads(SCHEMA.read_text(encoding='utf-8'))
    changed = apply(d)
    if changed:
        SCHEMA.write_text(json.dumps(d, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps(dict(changed=changed, tables=len(d['tables']), constraints=len(d['constraints']),
                          relations=len(d['relations'])), ensure_ascii=False))


if __name__ == '__main__':
    main()
