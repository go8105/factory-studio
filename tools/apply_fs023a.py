"""FS-023a: QMS 6테이블과 core.workspace_module 'qms'를 schema.json에 반영한다(멱등).

근거: docs/modules/qms/QMS_모듈설계_FS-023.md 4장, docs/plan/QMS도입_교차조회_결정_FS-023.md.
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
S = ['workspace_id', 'generation_id']
OLD_MODULE_CHECK = "module_key IN ('core','mes','erp','fems')"
NEW_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms')"


def col(name, label, type_, nullable=False, default=None, rule=''):
    return dict(name=name, label=label, type=type_, nullable=nullable, default=default, rule=rule)


def base(*columns):
    return [col('id', '내부 식별자', 'bigint', default='GENERATED ALWAYS AS IDENTITY'),
            col('workspace_id', '개인 체험 공간', 'bigint'),
            col('generation_id', '데이터 세대', 'bigint'),
            *columns,
            col('created_at', '등록 시각', 'timestamptz', default='now()')]


def table(name, label, sub, note, columns):
    return dict(name=name, label=label, scope='generation', phase='Q1', retention='세대 정리',
                note=note, sub_module=sub, columns=base(*columns))


TABLES = [
    table('qms.defect_type', '불량 유형', 'qms_master', 'FS-023 4.1. 쓰인 유형은 삭제 대신 사용 안 함', [
        col('code', '불량 유형 코드', 'varchar(30)', rule='대문자로 시작; MES 불량 사유 코드와 같게 심되 FK 없음'),
        col('name', '불량 유형명', 'varchar(100)'),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ]),
    table('qms.inspection_spec', '검사 기준 버전', 'spec', 'FS-023 4.2. 게시 후 불변, 품목당 게시 1건, 검사 생성 시 고정', [
        col('item_code', '품목 코드', 'varchar(40)', rule='MES 조회 또는 직접 입력한 코드 스냅샷(D11)'),
        col('item_name', '품목명', 'varchar(100)', rule='스냅샷'),
        col('version_no', '버전 번호', 'integer', default='1'),
        col('status', '상태', 'varchar(20)', default="'draft'", rule='draft / published / retired'),
        col('published_at', '게시 시각', 'timestamptz', nullable=True),
        col('note', '메모', 'varchar(300)', nullable=True),
    ]),
    table('qms.inspection_spec_item', '검사 항목', 'spec', 'FS-023 4.3. RANGE는 하한·상한 중 1개 이상, PASS_FAIL은 한계·단위 없음', [
        col('spec_id', '검사 기준 버전', 'bigint'),
        col('seq', '순서', 'integer'),
        col('name', '항목명', 'varchar(100)'),
        col('method', '판정 방식', 'varchar(12)', rule='RANGE / PASS_FAIL'),
        col('lower_limit', '하한', 'numeric(15,4)', nullable=True),
        col('upper_limit', '상한', 'numeric(15,4)', nullable=True),
        col('unit', '단위', 'varchar(10)', nullable=True, rule='RANGE이면 필수'),
        col('is_required', '필수 여부', 'boolean', default='true'),
    ]),
    table('qms.inspection', '검사', 'inspection', 'FS-023 4.4. LOT 단위 출하 전 최종검사. 확정 후 불변, 정정은 재검사', [
        col('inspection_no', '검사 번호', 'varchar(40)', rule='서버 발번 QI-YYYYMMDD-NNN'),
        col('source', '출처', 'varchar(10)', rule='MES(조회) / MANUAL(직접 입력)'),
        col('lot_no', 'LOT 번호', 'varchar(50)', rule='스냅샷(D11). MES FK 없음'),
        col('item_code', '품목 코드', 'varchar(40)', rule='스냅샷'),
        col('item_name', '품목명', 'varchar(100)', rule='스냅샷'),
        col('lot_qty', 'LOT 수량', 'numeric(15,3)', rule='검사 대상 수량 스냅샷'),
        col('unit', '단위', 'varchar(10)'),
        col('sample_qty', '표본 수량', 'numeric(15,3)'),
        col('spec_id', '적용 검사 기준', 'bigint', rule='만들 때의 게시 버전 고정'),
        col('reinspection_of_id', '원 검사', 'bigint', nullable=True, rule='재검사면 원 검사'),
        col('status', '상태', 'varchar(20)', default="'draft'", rule='draft / confirmed'),
        col('result', '판정', 'varchar(10)', nullable=True, rule='PASS / FAIL. 확정 시 서버 계산'),
        col('inspected_on', '검사일', 'date'),
        col('inspection_month', '검사 월', 'varchar(7)', rule="'YYYY-MM'. inspected_on에서 파생"),
        col('confirmed_at', '확정 시각', 'timestamptz', nullable=True),
        col('note', '메모', 'varchar(300)', nullable=True),
    ]),
    table('qms.inspection_value', '검사 측정값', 'inspection', 'FS-023 4.5. 항목 판정은 서버 계산. 확정 검사의 값은 불변', [
        col('inspection_id', '검사', 'bigint'),
        col('spec_item_id', '검사 항목', 'bigint'),
        col('measured_value', '측정값', 'numeric(15,4)', nullable=True, rule='RANGE 항목'),
        col('pass_value', '합·부 입력', 'boolean', nullable=True, rule='PASS_FAIL 항목'),
        col('judgement', '항목 판정', 'varchar(4)', nullable=True, rule='PASS / FAIL. 값이 없으면 NULL'),
        col('defect_type_id', '불량 유형', 'bigint', nullable=True, rule='불합격 항목이면 확정 시 필수'),
    ]),
    table('qms.quality_hold', '품질 보류', 'hold', 'FS-023 4.6. 불합격 확정 시 자동 생성, LOT당 활성 1건. MES 패킹을 막지 않는다(D10)', [
        col('hold_no', '보류 번호', 'varchar(40)', rule='서버 발번 QH-YYYYMMDD-NNN'),
        col('lot_no', 'LOT 번호', 'varchar(50)', rule='스냅샷'),
        col('item_code', '품목 코드', 'varchar(40)', rule='스냅샷'),
        col('inspection_id', '원인 검사', 'bigint'),
        col('status', '상태', 'varchar(20)', default="'held'", rule='held / released'),
        col('held_at', '보류 시각', 'timestamptz'),
        col('disposition', '처분', 'varchar(12)', nullable=True, rule='REINSPECTED / CONCESSION / SCRAP'),
        col('release_inspection_id', '해제 재검사', 'bigint', nullable=True),
        col('release_reason', '해제 사유', 'varchar(300)', nullable=True),
        col('released_at', '해제 시각', 'timestamptz', nullable=True),
    ]),
]


def c(table_, kind, columns, expression='', reason=''):
    return dict(table=table_, kind=kind, columns=columns, expression=expression, reason=reason)


def uk_partial(table_, columns, predicate, reason):
    cols = S + columns
    return c(table_, 'UK_PARTIAL', cols, f"UNIQUE ({', '.join(cols)}) WHERE {predicate}", reason)


CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [c(t['name'], 'PK', ['id'], reason='기본키'),
                    c(t['name'], 'UK', S + ['id'], reason='공간·세대 복합 참조 대상')]
DT, SP, SI, IN, IV, QH = (t['name'] for t in TABLES)
CONSTRAINTS += [
    c(DT, 'UK', S + ['code'], reason='세대 내 코드 유일'),
    c(DT, 'CHECK', ['code'], "code ~ '^[A-Z][A-Z0-9_]{1,29}$'", '코드 형식'),
    c(DT, 'SERVICE/DB_POLICY', ['id'], '검사 측정값에서 쓴 유형은 삭제를 거부하고 사용 안 함으로 바꾼다', '불량 이력 보존'),
    c(SP, 'UK', S + ['item_code', 'version_no'], reason='품목별 버전 유일'),
    c(SP, 'CHECK', ['version_no'], 'version_no >= 1', '버전은 1부터'),
    c(SP, 'CHECK', ['status'], "status IN ('draft', 'published', 'retired')", '상태 값'),
    c(SP, 'CHECK', ['status', 'published_at'], "status = 'draft' OR published_at IS NOT NULL", '게시·폐기 버전은 게시 시각 필수'),
    c(SP, 'CHECK', ['item_code', 'item_name'], 'length(btrim(item_code)) > 0 AND length(btrim(item_name)) > 0', '빈 품목 스냅샷 차단'),
    uk_partial(SP, ['item_code'], "status = 'published'", '품목당 게시 버전 1건'),
    c(SP, 'SERVICE/DB_POLICY', ['status'], 'published·retired 버전과 그 항목은 수정·삭제를 거부한다. 바꾸려면 개정(새 draft)', '게시 기준 불변'),
    c(SP, 'SERVICE/DB_POLICY', ['status'], '게시는 항목 1개 이상. 게시하면 같은 품목의 기존 published를 같은 트랜잭션에서 retired로 바꾼다(TX-Q1)', '품목당 게시 1건 전환'),
    c(SI, 'UK', S + ['spec_id', 'seq'], reason='기준 내 순서 유일'),
    c(SI, 'CHECK', ['seq'], 'seq >= 1', '순서는 1부터'),
    c(SI, 'CHECK', ['method'], "method IN ('RANGE', 'PASS_FAIL')", '판정 방식 값'),
    c(SI, 'CHECK', ['method', 'lower_limit', 'upper_limit', 'unit'],
      "(method = 'PASS_FAIL' AND lower_limit IS NULL AND upper_limit IS NULL AND unit IS NULL) OR "
      "(method = 'RANGE' AND unit IS NOT NULL AND (lower_limit IS NOT NULL OR upper_limit IS NOT NULL) "
      "AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit))", '판정 방식별 한계·단위'),
    c(IN, 'UK', S + ['inspection_no'], reason='세대 내 검사 번호 유일'),
    c(IN, 'CHECK', ['source'], "source IN ('MES', 'MANUAL')", '출처 값'),
    c(IN, 'CHECK', ['status', 'result', 'confirmed_at'],
      "(status = 'draft' AND result IS NULL AND confirmed_at IS NULL) OR "
      "(status = 'confirmed' AND result IN ('PASS', 'FAIL') AND confirmed_at IS NOT NULL)", '확정과 판정·확정 시각 일치'),
    c(IN, 'CHECK', ['lot_qty', 'sample_qty'], 'lot_qty > 0 AND sample_qty > 0 AND sample_qty <= lot_qty', '표본은 LOT 수량 이하'),
    c(IN, 'CHECK', ['lot_no', 'item_code', 'item_name', 'unit'],
      'length(btrim(lot_no)) > 0 AND length(btrim(item_code)) > 0 AND length(btrim(item_name)) > 0 AND length(btrim(unit)) > 0', '빈 스냅샷 차단'),
    c(IN, 'CHECK', ['inspection_month'], "inspection_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", '연월 문자열 형식'),
    c(IN, 'CHECK', ['reinspection_of_id'], 'reinspection_of_id IS NULL OR reinspection_of_id <> id', '자기 자신 재검사 차단'),
    uk_partial(IN, ['lot_no'], "status = 'draft'", 'LOT당 작성 중 검사 1건'),
    c(IN, 'SERVICE/DB_POLICY', ['status'], 'confirmed 검사와 측정값은 수정·삭제를 거부한다(세대 정리 제외). 정정은 재검사', '확정 검사 불변'),
    c(IN, 'SERVICE/DB_POLICY', ['spec_id'], '만들 때 같은 품목의 published 기준만 고를 수 있다. 이후 기준 개정과 무관하다', '검사 기준 고정'),
    c(IN, 'SERVICE/DB_POLICY', ['result'], '필수 항목 모두 입력·불합격 항목 모두 불량 유형이어야 확정. 한 항목이라도 FAIL이면 FAIL', '검사 판정'),
    c(IN, 'SERVICE/DB_POLICY', ['inspection_month'], "inspected_on의 'YYYY-MM'과 같아야 한다. 세대 복사 시 다시 계산한다", '달력 파생 컬럼'),
    c(IV, 'UK', S + ['inspection_id', 'spec_item_id'], reason='검사당 항목 1회'),
    c(IV, 'CHECK', ['measured_value', 'pass_value'], 'measured_value IS NULL OR pass_value IS NULL', '측정값·합부 입력 중 하나만'),
    c(IV, 'CHECK', ['judgement'], "judgement IS NULL OR judgement IN ('PASS', 'FAIL')", '항목 판정 값'),
    c(IV, 'SERVICE/DB_POLICY', ['spec_item_id'], '측정값의 항목은 검사의 spec_id에 속한 항목이어야 한다', '기준-항목 일치'),
    c(IV, 'SERVICE/DB_POLICY', ['judgement'], '항목 판정은 서버가 한계·합부로 계산한다. 클라이언트 판정을 쓰지 않는다', '서버 판정'),
    c(QH, 'UK', S + ['hold_no'], reason='세대 내 보류 번호 유일'),
    c(QH, 'CHECK', ['status'], "status IN ('held', 'released')", '상태 값'),
    c(QH, 'CHECK', ['status', 'disposition', 'released_at'],
      "(status = 'held' AND disposition IS NULL AND released_at IS NULL AND release_inspection_id IS NULL AND release_reason IS NULL) OR "
      "(status = 'released' AND disposition IN ('REINSPECTED', 'CONCESSION', 'SCRAP') AND released_at IS NOT NULL)", '해제와 처분·해제 시각 일치'),
    c(QH, 'CHECK', ['disposition', 'release_inspection_id', 'release_reason'],
      "(disposition IS NULL) OR (disposition = 'REINSPECTED' AND release_inspection_id IS NOT NULL) OR "
      "(disposition IN ('CONCESSION', 'SCRAP') AND release_inspection_id IS NULL AND release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)",
      '처분별 재검사·사유'),
    c(QH, 'CHECK', ['lot_no', 'item_code'], 'length(btrim(lot_no)) > 0 AND length(btrim(item_code)) > 0', '빈 스냅샷 차단'),
    uk_partial(QH, ['lot_no'], "status = 'held'", 'LOT당 활성 보류 1건'),
    c(QH, 'SERVICE/DB_POLICY', ['status'], 'released 보류는 수정·삭제를 거부한다. 불합격 확정과 같은 트랜잭션에서 생성한다(TX-Q2)', '보류 불변·생성 시점'),
    c(QH, 'SERVICE/DB_POLICY', ['release_inspection_id'], '해제 재검사는 같은 lot_no·confirmed·PASS·보류 이후 확정이어야 한다', '재검사 해제 조건'),
    c(QH, 'SERVICE/DB_POLICY', ['disposition'], '폐기 판정도 기록일 뿐 MES 양품·재고를 차감하지 않는다(D10·WMS 경계)', '수량 불변'),
    c(IN, 'INDEX', S + ['spec_id'], reason='FK 조회'),
    c(IN, 'INDEX', S + ['reinspection_of_id'], reason='FK 조회'),
    c(IN, 'INDEX', S + ['lot_no', 'status'], reason='LOT별 검사 조회·검사 대기 차집합'),
    c(IN, 'INDEX', S + ['inspection_month'], reason='대시보드 월 집계'),
    c(IV, 'INDEX', S + ['spec_item_id'], reason='FK 조회'),
    c(IV, 'INDEX', S + ['defect_type_id'], reason='FK 조회'),
    c(QH, 'INDEX', S + ['inspection_id'], reason='FK 조회'),
    c(QH, 'INDEX', S + ['release_inspection_id'], reason='FK 조회'),
]


def r(source, columns, target, note):
    return dict(source=source, columns=S + columns, target=target, target_columns=S + ['id'],
                on_delete='RESTRICT', on_update='RESTRICT', note=note)


RELATIONS = [dict(source=t['name'], columns=S, target='core.data_generation', target_columns=['workspace_id', 'id'],
                  on_delete='RESTRICT', on_update='RESTRICT', note='같은 참조 범위 유지') for t in TABLES]
RELATIONS += [
    r(SI, ['spec_id'], SP, '기준 소속'),
    r(IN, ['spec_id'], SP, '적용 검사 기준(고정)'),
    r(IN, ['reinspection_of_id'], IN, '재검사의 원 검사'),
    r(IV, ['inspection_id'], IN, '검사 소속'),
    r(IV, ['spec_item_id'], SI, '검사 항목'),
    r(IV, ['defect_type_id'], DT, '불량 유형'),
    r(QH, ['inspection_id'], IN, '보류를 만든 불합격 검사'),
    r(QH, ['release_inspection_id'], IN, '보류를 푼 재검사'),
]

STATES = [
    dict(table=SP, column='status', values=['draft', 'published', 'retired'], default='draft',
         transition='draft→published→retired; 게시 시 같은 품목의 기존 published→retired; 게시 내용 불변'),
    dict(table=IN, column='status', values=['draft', 'confirmed'], default='draft',
         transition='draft→confirmed; 확정 시 판정 계산, FAIL이면 보류 생성(TX-Q2)'),
    dict(table=QH, column='status', values=['held', 'released'], default='held',
         transition='held→released; 처분 REINSPECTED/CONCESSION/SCRAP 중 하나'),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    names = {t['name'] for t in d['tables']}
    if DT in names:
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
            code['values'] = ['core', 'mes', 'erp', 'fems', 'qms']
            code['note'] = 'QMS는 FS-023으로 구현 솔루션. WMS·BEMS·SCM 설명 카드와 도움말은 정적 파일'
    d['code_lists'].extend([
        dict(target=IN, column='source', values=['MES', 'MANUAL'], default=None, note='MES = 읽기 전용 조회로 만든 검사(D9)'),
        dict(target=SI, column='method', values=['RANGE', 'PASS_FAIL'], default=None, note='RANGE는 하한 ≤ 측정값 ≤ 상한(한쪽만 가능)'),
        dict(target=QH, column='disposition', values=['REINSPECTED', 'CONCESSION', 'SCRAP'], default=None, note='재검사 합격 / 특채 / 폐기 판정'),
    ])
    d.update(version='0.10.0', task='FS-023a', date='2026-09-27', migration_revision='fs023a_qms')
    d['change_log'].append(dict(version='0.10.0', task='FS-023a', date='2026-09-27',
                                change='qms 스키마 6테이블(불량 유형·검사 기준·검사 항목·검사·측정값·품질 보류), '
                                       'core.workspace_module module_key에 qms 추가. 스키마 간 FK 0건(D9 읽기 전용 조회는 코드 인터페이스)',
                                status='마이그레이션 fs023a_qms 적용 대상'))
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
