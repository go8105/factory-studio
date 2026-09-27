"""FS-024a: WMS 6테이블과 core.workspace_module 'wms'를 schema.json에 반영한다(멱등).

근거: docs/modules/wms/WMS_모듈설계_FS-024.md 4장, docs/plan/WMS도입_재고원장_결정_FS-024.md.
이미 반영돼 있으면 아무것도 바꾸지 않는다. 새 제약·관계는 목록 끝에 붙여 기존 C·R 번호를 유지한다.
"""
import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / 'docs/db/schema-metadata/schema.json'
OLD_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms')"
NEW_MODULE_CHECK = "module_key IN ('core','mes','erp','fems','qms','wms')"
SOURCE_TYPES = ('MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE')
MANUAL_TYPES = ('OPENING', 'ADJUSTMENT', 'TRANSFER')
DOCUMENT_TYPES = ('OPENING', *SOURCE_TYPES, 'ADJUSTMENT', 'TRANSFER', 'REVERSAL')
REASONS = ('RETURN', 'SCRAP', 'COUNT', 'OTHER')


def quoted(values):
    return ', '.join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), 'phase': 'W1'}


TABLES = [
    table('wms.warehouse', '창고', 'wms_master', 'FS-024 4.1. 용도(RAW/FG)별 활성 창고 1개가 원천 반영 대상', [
        col('code', '창고 코드', 'varchar(20)'),
        col('name', '창고명', 'varchar(100)'),
        col('purpose', '용도', 'varchar(10)', rule='RAW 원자재 / FG 완제품'),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ]),
    table('wms.storage_location', '보관 위치', 'wms_master', 'FS-024 4.2. 창고 안 1단계 위치. core·mes location(공정 구역)과 다른 개념', [
        col('warehouse_id', '창고', 'bigint'),
        col('code', '위치 코드', 'varchar(20)'),
        col('name', '위치명', 'varchar(100)'),
        col('is_default', '기본 위치', 'boolean', default='false', rule='창고당 1개. 원천 반영 입출고 위치'),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ]),
    table('wms.item', 'WMS 품목', 'wms_master', 'FS-024 4.3. WMS가 소유하는 재고 품목(FS-013 D1). 코드는 MES·ERP와 같게 심되 FK 없음', [
        col('item_code', '품목 코드', 'varchar(40)'),
        col('name', '품목명', 'varchar(100)'),
        col('base_unit', '기본 단위', 'varchar(10)', rule='원장 수량 단위'),
        col('item_class', '분류', 'varchar(10)', rule='RAW / FG'),
        col('lot_tracked', 'LOT 추적', 'boolean', rule='FG = true, RAW = false(D16)'),
        col('is_active', '사용 여부', 'boolean', default='true'),
    ]),
    table('wms.item_unit_conversion', '품목 단위 환산', 'wms_master', 'FS-024 4.4. 1 from_unit = factor 기본 단위', [
        col('item_id', '품목', 'bigint'),
        col('from_unit', '환산 단위', 'varchar(10)'),
        col('factor', '환산 계수', 'numeric(18,6)'),
    ]),
    table('wms.stock_document', '재고 전표', 'ledger', 'FS-024 4.5. 원천 반영·기초·조정·이동·되돌림. 확정 후 불변, 정정은 되돌림 전표', [
        col('document_no', '전표 번호', 'varchar(40)', rule='서버 발번 WD-YYYYMMDD-NNN'),
        col('document_type', '전표 유형', 'varchar(20)', rule=' / '.join(DOCUMENT_TYPES)),
        col('status', '상태', 'varchar(10)', default="'draft'", rule='draft / posted. 원천 반영·되돌림은 만들 때 posted'),
        col('source_key', '원천 키', 'varchar(100)', nullable=True, rule='원천 반영·되돌림이면 필수. 예 MES:RECEIPT:PL-0006 (D14 멱등)'),
        col('source_ref', '원천 번호', 'varchar(40)', nullable=True, rule='화면 표시용 스냅샷(D11)'),
        col('reverses_document_id', '되돌린 전표', 'bigint', nullable=True, rule='REVERSAL이면 필수'),
        col('reason_code', '조정 사유', 'varchar(10)', nullable=True, rule='ADJUSTMENT이면 필수: ' + ' / '.join(REASONS)),
        col('document_on', '업무일', 'date'),
        col('document_month', '업무 월', 'varchar(7)', rule="'YYYY-MM'. document_on에서 파생"),
        col('posted_at', '확정 시각', 'timestamptz', nullable=True),
        col('note', '메모', 'varchar(300)', nullable=True, rule='사유 OTHER이면 필수'),
    ]),
    table('wms.stock_move', '재고 이동', 'ledger', 'FS-024 4.6. 재고 원장. 현재고 = 확정 전표 이동 합(잔량 저장 없음, 음수 허용 D15)', [
        col('document_id', '재고 전표', 'bigint'),
        col('line_no', '줄 번호', 'integer'),
        col('item_id', '품목', 'bigint'),
        col('location_id', '보관 위치', 'bigint'),
        col('lot_no', 'LOT 번호', 'varchar(50)', nullable=True, rule='스냅샷. LOT 추적 품목에서 NULL이면 LOT 미지정, RAW는 NULL만'),
        col('qty_delta', '증감 수량', 'numeric(18,3)', rule='기본 단위, 입고 + / 출고 −, 0 불가'),
        col('source_qty', '원천 수량', 'numeric(18,3)', nullable=True, rule='원천 단위 기준 스냅샷'),
        col('source_unit', '원천 단위', 'varchar(10)', nullable=True),
        col('moved_at', '이동 시각', 'timestamptz', rule='원천 시각 또는 전표 확정 시각'),
    ]),
]
WH, SL, IT, UC, SD, SM = (t['name'] for t in TABLES)

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [c(t['name'], 'PK', ['id'], reason='기본키'),
                    c(t['name'], 'UK', S + ['id'], reason='공간·세대 복합 참조 대상')]
CONSTRAINTS += [
    c(WH, 'UK', S + ['code'], reason='세대 내 창고 코드 유일'),
    c(WH, 'CHECK', ['code'], "code ~ '^[A-Z][A-Z0-9-]{1,19}$'", '코드 형식'),
    c(WH, 'CHECK', ['purpose'], "purpose IN ('RAW', 'FG')", '용도 값'),
    c(WH, 'CHECK', ['name'], 'length(btrim(name)) > 0', '빈 이름 차단'),
    uk_partial(WH, ['purpose'], 'is_active', '용도별 활성 창고 1개(원천 반영 대상)'),
    c(WH, 'SERVICE/DB_POLICY', ['id'], '위치에 이동이 있는 창고는 삭제를 거부하고 사용 안 함으로 바꾼다', '원장 보존'),
    c(SL, 'UK', S + ['warehouse_id', 'code'], reason='창고 내 위치 코드 유일'),
    c(SL, 'CHECK', ['code'], "code ~ '^[A-Z][A-Z0-9-]{1,19}$'", '코드 형식'),
    c(SL, 'CHECK', ['name'], 'length(btrim(name)) > 0', '빈 이름 차단'),
    c(SL, 'CHECK', ['is_default', 'is_active'], 'NOT is_default OR is_active', '기본 위치는 사용 중이어야 한다'),
    uk_partial(SL, ['warehouse_id'], 'is_default', '창고당 기본 위치 1개'),
    c(SL, 'SERVICE/DB_POLICY', ['id'], '이동이 있는 위치는 삭제를 거부한다(참조처별 건수)', '원장 보존'),
    c(IT, 'UK', S + ['item_code'], reason='세대 내 품목 코드 유일'),
    c(IT, 'CHECK', ['item_class'], "item_class IN ('RAW', 'FG')", '분류 값'),
    c(IT, 'CHECK', ['item_class', 'lot_tracked'], "lot_tracked = (item_class = 'FG')", '완제품만 LOT 추적(D16)'),
    c(IT, 'CHECK', ['item_code', 'name', 'base_unit'],
      'length(btrim(item_code)) > 0 AND length(btrim(name)) > 0 AND length(btrim(base_unit)) > 0', '빈 값 차단'),
    c(IT, 'SERVICE/DB_POLICY', ['id'], '이동이 있는 품목은 삭제를 거부하고 사용 안 함으로 바꾼다', '원장 보존'),
    c(UC, 'UK', S + ['item_id', 'from_unit'], reason='품목·단위별 환산 1개'),
    c(UC, 'CHECK', ['factor'], 'factor > 0', '환산 계수 양수'),
    c(UC, 'SERVICE/DB_POLICY', ['from_unit'], '환산 단위는 품목 기본 단위와 달라야 한다', '자기 환산 차단'),
    c(SD, 'UK', S + ['document_no'], reason='세대 내 전표 번호 유일'),
    c(SD, 'CHECK', ['document_type'], f'document_type IN ({quoted(DOCUMENT_TYPES)})', '전표 유형 값'),
    c(SD, 'CHECK', ['status'], "status IN ('draft', 'posted')", '상태 값'),
    c(SD, 'CHECK', ['status', 'posted_at'], "(status = 'posted') = (posted_at IS NOT NULL)", '확정과 확정 시각 일치'),
    c(SD, 'CHECK', ['document_type', 'status'], f"document_type IN ({quoted(MANUAL_TYPES)}) OR status = 'posted'", '원천 반영·되돌림은 만들 때 확정'),
    c(SD, 'CHECK', ['document_type', 'source_key'],
      f"(document_type IN ({quoted(SOURCE_TYPES + ('REVERSAL',))})) = (source_key IS NOT NULL)", '원천 반영·되돌림만 원천 키'),
    c(SD, 'CHECK', ['document_type', 'reverses_document_id'],
      "(document_type = 'REVERSAL') = (reverses_document_id IS NOT NULL)", '되돌림은 원 전표 필수'),
    c(SD, 'CHECK', ['reverses_document_id'], 'reverses_document_id IS NULL OR reverses_document_id <> id', '자기 자신 되돌림 차단'),
    c(SD, 'CHECK', ['document_type', 'reason_code'],
      f"(document_type = 'ADJUSTMENT' AND reason_code IN ({quoted(REASONS)})) OR (document_type <> 'ADJUSTMENT' AND reason_code IS NULL)",
      '조정은 사유 필수'),
    c(SD, 'CHECK', ['reason_code', 'note'],
      "reason_code IS DISTINCT FROM 'OTHER' OR (note IS NOT NULL AND length(btrim(note)) > 0)", '기타 사유는 메모 필수'),
    c(SD, 'CHECK', ['document_month'], "document_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'", '연월 문자열 형식'),
    uk_partial(SD, ['source_key'], "document_type <> 'REVERSAL'", '원천 1건 = 반영 전표 1건(D14)'),
    uk_partial(SD, ['reverses_document_id'], 'reverses_document_id IS NOT NULL', '되돌림은 1번만'),
    c(SD, 'SERVICE/DB_POLICY', ['status'], 'posted 전표와 그 이동은 수정·삭제를 거부한다(세대 정리 제외). 정정은 되돌림 전표', '원장 불변'),
    c(SD, 'SERVICE/DB_POLICY', ['source_key'],
      '원천 반영은 인터페이스로 읽은 확정 원천만. 같은 원천의 동시 반영은 부분 유니크 경합으로 판정하고 기존 전표를 돌려준다(TX-W1)', '멱등 반영'),
    c(SD, 'SERVICE/DB_POLICY', ['document_month'], "document_on의 'YYYY-MM'과 같아야 한다. 세대 복사 시 다시 계산한다", '달력 파생 컬럼'),
    c(SD, 'SERVICE/DB_POLICY', ['document_type'], 'TRANSFER는 품목·LOT별 이동 합이 0이어야 확정한다. 같은 위치 간 이동 금지', '이동 전표 균형'),
    c(SM, 'UK', S + ['document_id', 'line_no'], reason='전표 내 줄 번호 유일'),
    c(SM, 'CHECK', ['line_no'], 'line_no >= 1', '줄 번호는 1부터'),
    c(SM, 'CHECK', ['qty_delta'], 'qty_delta <> 0', '0 이동 차단'),
    c(SM, 'CHECK', ['source_qty', 'source_unit'], '(source_qty IS NULL) = (source_unit IS NULL)', '원천 수량·단위 함께'),
    c(SM, 'CHECK', ['lot_no'], 'lot_no IS NULL OR length(btrim(lot_no)) > 0', '빈 LOT 번호 차단'),
    c(SM, 'SERVICE/DB_POLICY', ['lot_no'], 'LOT 추적하지 않는 품목(RAW)은 lot_no NULL만. LOT 추적 품목의 NULL은 LOT 미지정 출고', 'LOT 규칙(D16)'),
    c(SM, 'SERVICE/DB_POLICY', ['qty_delta'],
      '품목 기본 단위로 저장한다. 원천 단위가 다르면 WMS 단위 환산을 쓰고, 환산이 없으면 반영하지 않는다. 잔량 확인 없음(음수 허용 D15)', '단위·음수'),
    c(SD, 'INDEX', S + ['reverses_document_id'], reason='FK 조회'),
    c(SD, 'INDEX', S + ['document_month'], reason='대시보드 월 집계'),
    c(SM, 'INDEX', S + ['item_id', 'location_id', 'lot_no'], reason='현재고 합계'),
    c(SM, 'INDEX', S + ['location_id'], reason='FK 조회'),
]

RELATIONS = [dict(source=t['name'], columns=S, target='core.data_generation', target_columns=['workspace_id', 'id'],
                  on_delete='RESTRICT', on_update='RESTRICT', note='같은 참조 범위 유지') for t in TABLES]
RELATIONS += [
    r(SL, ['warehouse_id'], WH, '위치의 창고'),
    r(UC, ['item_id'], IT, '환산의 품목'),
    r(SD, ['reverses_document_id'], SD, '되돌린 원 전표'),
    r(SM, ['document_id'], SD, '이동의 전표'),
    r(SM, ['item_id'], IT, '이동 품목'),
    r(SM, ['location_id'], SL, '이동 위치'),
]

STATES = [
    dict(table=SD, column='status', values=['draft', 'posted'], default='draft',
         transition='draft→posted(기초·조정·이동); 원천 반영·되돌림은 posted로 생성; 확정 후 불변'),
]


def apply(d):
    """schema dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if WH in {t['name'] for t in d['tables']}:
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
            code['values'] = ['core', 'mes', 'erp', 'fems', 'qms', 'wms']
            code['note'] = 'QMS(FS-023)·WMS(FS-024)는 구현 솔루션. BEMS·SCM 설명 카드와 도움말은 정적 파일'
    d['code_lists'].extend([
        dict(target=WH, column='purpose', values=['RAW', 'FG'], default=None, note='원천 반영이 들어갈 창고를 정한다'),
        dict(target=IT, column='item_class', values=['RAW', 'FG'], default=None, note='FG만 LOT 추적'),
        dict(target=SD, column='document_type', values=list(DOCUMENT_TYPES), default=None,
             note='MES_*·ERP_* = 읽기 전용 조회로 반영한 원천(D14)'),
        dict(target=SD, column='reason_code', values=list(REASONS), default=None, note='반품 입고 / 폐기 / 실물 차이 / 기타'),
    ])
    d.update(version='0.11.0', task='FS-024a', date='2026-09-27', migration_revision='fs024a_wms')
    d['change_log'].append(dict(version='0.11.0', task='FS-024a', date='2026-09-27',
                                change='wms 스키마 6테이블(창고·보관 위치·품목·단위 환산·재고 전표·재고 이동), '
                                       'core.workspace_module module_key에 wms 추가. 스키마 간 FK 0건(원천은 D9 읽기 전용 조회)',
                                status='마이그레이션 fs024a_wms 적용 대상'))
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
