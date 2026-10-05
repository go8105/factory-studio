"""DSN-13: WMS 보강 설계를 목표 DB(schema-target.json)에 반영한다(멱등, apply_dsn12 다음).

근거: docs/modules/wms/WMS_보강설계_DSN-13.md 4장(새 테이블 12·기존 테이블 변경 6), 결정 Q1~Q7.
Q1: 창고 스캔은 POP — WMS는 가져오기(pop_import)로 재검증. 잔량 테이블은 두지 않는다(원장 합계, FS-024).
"""

import json
from pathlib import Path

from apply_fs023a import S, c, col, r, uk_partial
from apply_fs023a import table as _table

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "docs/db/schema-metadata/schema-target.json"
CODE = "~ '^[A-Z0-9][A-Z0-9_-]{0,29}$'"
W = "wms."


def q(values):
    return ", ".join(f"'{v}'" for v in values)


def table(name, label, sub, note, columns):
    return {**_table(name, label, sub, note, columns), "phase": "DSN-13"}


PURPOSES = ("RAW", "SEMI", "FG", "MERCH", "LINE", "SUBCON", "DEFECT", "RETURN")
LOCATION_TYPES = ("NORMAL", "QUARANTINE", "LINE", "RECEIVING", "SHIPPING", "RETURN")
LEVELS = ("ZONE", "RACK", "LEVEL", "BIN")
ITEM_CLASSES = ("RAW", "SEMI", "FG", "MERCH", "SUPPLY")
DOC_TYPES = (
    "OPENING",
    "MES_RECEIPT",
    "MES_ISSUE",
    "ERP_SHIPMENT",
    "ERP_PURCHASE",
    "WMS_INSPECTION",
    "ADJUSTMENT",
    "TRANSFER",
    "REVERSAL",
    "MES_ADJUST",
    "MES_SUBCONTRACT",
    "ERP_SALES_RETURN",
    "ERP_PURCHASE_RETURN",
    "PRODUCTION_ISSUE",
    "PUTAWAY",
    "PICK",
    "CYCLE_COUNT",
)
SOURCED = (
    "MES_RECEIPT",
    "MES_ISSUE",
    "ERP_SHIPMENT",
    "ERP_PURCHASE",
    "WMS_INSPECTION",
    "REVERSAL",
    "MES_ADJUST",
    "MES_SUBCONTRACT",
    "ERP_SALES_RETURN",
    "ERP_PURCHASE_RETURN",
)
POP_KINDS = ("RECEIVE", "PUTAWAY", "PICK", "ISSUE", "COUNT", "MOVE")
NOTICE_KINDS = ("PURCHASE", "PO", "SALES_RETURN", "SUBCONTRACT")

LOT, PT, PO, PL, IR, IRL = (
    W + "lot",
    W + "putaway_task",
    W + "pick_order",
    W + "pick_line",
    W + "issue_request",
    W + "issue_request_line",
)
CO, CL, SP, PI, LP, LH = (
    W + "count_order",
    W + "count_line",
    W + "stock_period",
    W + "pop_import",
    W + "label_print",
    W + "lot_hold",
)

TABLES = [
    table(
        LOT,
        "LOT",
        "lot",
        "DSN-13 F13·F36·F53(Q3·Q5). 품목·LOT 속성(입고일·유효기간·공급처 LOT). 수량은 원장 합계(저장 안 함)",
        [
            col("item_id", "품목", "bigint"),
            col(
                "lot_no",
                "LOT 번호",
                "varchar(50)",
                rule="WMS 부여(입고) 또는 MES LOT 번호(완제품)",
            ),
            col(
                "origin",
                "출처",
                "varchar(10)",
                rule="RECEIPT 입고 / MES 생산 / RETURN 반품 / OPENING 기초",
            ),
            col("received_on", "입고일", "date", rule="FIFO 기준"),
            col(
                "expiry_date",
                "유효기간",
                "date",
                nullable=True,
                rule="FEFO 기준. 품목 유효기간 일수에서 계산",
            ),
            col("supplier_lot_no", "공급처 LOT", "varchar(50)", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'AVAILABLE'",
                rule="AVAILABLE / HOLD / EXPIRED",
            ),
        ],
    ),
    table(
        LH,
        "LOT 보류",
        "lot",
        "DSN-13 F36·F38. 보류·해제 이력. QMS 보류는 조회로 받아 기록, 만료는 자동",
        [
            col("lot_id", "LOT", "bigint"),
            col("source", "출처", "varchar(8)", rule="MANUAL / QMS / EXPIRY"),
            col(
                "source_ref",
                "원천 코드",
                "varchar(60)",
                nullable=True,
                rule="QMS 보류 번호 스냅샷",
            ),
            col("held_at", "보류 시각", "timestamptz"),
            col("released_at", "해제 시각", "timestamptz", nullable=True),
            col("reason", "사유", "varchar(300)"),
        ],
    ),
    table(
        PT,
        "적치 작업",
        "inbound",
        "DSN-13 F14. 입고장 → 보관 위치. 추천 위치는 용량·혼적 기준, 실제 위치는 POP 스캔 또는 수동",
        [
            col("task_no", "작업 번호", "varchar(40)"),
            col("source_document_id", "입고 전표", "bigint"),
            col("item_id", "품목", "bigint"),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col("qty", "수량", "numeric(18,3)"),
            col("from_location_id", "출발 위치", "bigint"),
            col("suggested_location_id", "추천 위치", "bigint", nullable=True),
            col("to_location_id", "적치 위치", "bigint", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / DONE / CANCELLED",
            ),
            col("done_at", "완료 시각", "timestamptz", nullable=True),
            col(
                "stock_document_id",
                "적치 전표",
                "bigint",
                nullable=True,
                rule="PUTAWAY 이동 전표",
            ),
        ],
    ),
    table(
        PO,
        "피킹 지시",
        "outbound",
        "DSN-13 F22·F23(Q4). 출고 예약 1건당 피킹 1건. 확정 시 출고장 위치로 이동(PICK)",
        [
            col("pick_no", "피킹 번호", "varchar(40)"),
            col("reservation_id", "출고 예약", "bigint"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / PICKED / CANCELLED",
            ),
            col("picked_at", "피킹 확정 시각", "timestamptz", nullable=True),
            col("stock_document_id", "피킹 전표", "bigint", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        PL,
        "피킹 명세",
        "outbound",
        "DSN-13 F22·F27. 위치 순서·FEFO→FIFO로 LOT 배정, 피킹 수량은 POP 스캔 또는 수동",
        [
            col("pick_order_id", "피킹 지시", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("item_id", "품목", "bigint"),
            col("location_id", "피킹 위치", "bigint"),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col("qty", "지시 수량", "numeric(18,3)"),
            col("picked_qty", "피킹 수량", "numeric(18,3)", nullable=True),
            col("sequence_no", "피킹 순서", "integer"),
        ],
    ),
    table(
        IR,
        "생산 불출 요청",
        "outbound",
        "DSN-13 F25(Q4). MES 작업지시 소요(코드 스냅샷) → 라인 위치로 이동(PRODUCTION_ISSUE). MES 투입은 라인 재고에서 차감",
        [
            col("request_no", "요청 번호", "varchar(40)"),
            col(
                "work_order_no",
                "MES 작업지시",
                "varchar(40)",
                nullable=True,
                rule="MES 코드 스냅샷. 수동이면 비움",
            ),
            col("line_location_id", "라인 위치", "bigint"),
            col("needed_at", "필요 시각", "timestamptz", nullable=True),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / ISSUED / CANCELLED",
            ),
            col("issued_at", "불출 시각", "timestamptz", nullable=True),
            col("stock_document_id", "불출 전표", "bigint", nullable=True),
            col("cancel_reason", "취소 사유", "varchar(300)", nullable=True),
        ],
    ),
    table(
        IRL,
        "생산 불출 명세",
        "outbound",
        "DSN-13 F25",
        [
            col("issue_request_id", "생산 불출 요청", "bigint"),
            col("line_no", "행 번호", "integer"),
            col("item_id", "품목", "bigint"),
            col("qty", "요청 수량", "numeric(18,3)"),
            col("issued_qty", "불출 수량", "numeric(18,3)", nullable=True),
        ],
    ),
    table(
        CO,
        "재고 실사",
        "count",
        "DSN-13 F35. 전수·순환. 시작 시 장부 수량 스냅샷, 차이는 CYCLE_COUNT 조정 전표",
        [
            col("count_no", "실사 번호", "varchar(40)"),
            col("kind", "종류", "varchar(6)", rule="FULL 전수 / CYCLE 순환"),
            col("warehouse_id", "창고", "bigint"),
            col("snapshot_at", "장부 기준 시각", "timestamptz"),
            col(
                "status",
                "상태",
                "varchar(10)",
                default="'OPEN'",
                rule="OPEN / COUNTED / ADJUSTED / CANCELLED",
            ),
            col("adjusted_at", "조정 시각", "timestamptz", nullable=True),
            col("stock_document_id", "조정 전표", "bigint", nullable=True),
        ],
    ),
    table(
        CL,
        "실사 명세",
        "count",
        "DSN-13 F35. 차이 = 실사 − 장부(저장 안 함)",
        [
            col("count_order_id", "재고 실사", "bigint"),
            col("location_id", "위치", "bigint"),
            col("item_id", "품목", "bigint"),
            col("lot_no", "LOT 번호", "varchar(50)", nullable=True),
            col(
                "book_qty",
                "장부 수량",
                "numeric(18,3)",
                rule="시작 시 원장 합계 스냅샷",
            ),
            col("counted_qty", "실사 수량", "numeric(18,3)", nullable=True),
            col("counted_at", "실사 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        SP,
        "재고 기간",
        "closing",
        "DSN-13 F39(Q6). 마감 월 재고 전표 금지. ERP 원가는 마감 월 수불을 기준",
        [
            col("period_month", "재고 월", "varchar(7)", rule="'YYYY-MM'"),
            col(
                "status", "상태", "varchar(10)", default="'open'", rule="open / closed"
            ),
            col("closed_at", "마감 시각", "timestamptz", nullable=True),
        ],
    ),
    table(
        PI,
        "POP 가져오기",
        "pop",
        "DSN-13 Q1. POP 창고 스캔 확정 입력 1건당 1행(멱등). 적용 또는 거부",
        [
            col("pop_entry_ref", "POP 입력 코드", "varchar(60)"),
            col("entry_kind", "입력 종류", "varchar(10)", rule=" / ".join(POP_KINDS)),
            col("barcode_value", "스캔 값", "varchar(80)"),
            col("imported_at", "가져온 시각", "timestamptz"),
            col("result", "결과", "varchar(8)", rule="APPLIED / REJECTED"),
            col("reject_reason", "거부 사유", "varchar(300)", nullable=True),
            col("target_id", "적용 대상 id", "bigint", nullable=True),
        ],
    ),
    table(
        LP,
        "라벨 출력",
        "label",
        "DSN-13 F07·F13. 위치 라벨·자재 LOT 라벨(Code128, 브라우저 인쇄 — MES Q3와 같음)",
        [
            col(
                "label_kind", "라벨 종류", "varchar(12)", rule="LOCATION / MATERIAL_LOT"
            ),
            col(
                "barcode_value", "바코드 값", "varchar(80)", rule="위치 코드 / LOT 번호"
            ),
            col("copies", "매수", "integer", default="1"),
            col("printed_at", "출력 시각", "timestamptz"),
            col("status", "상태", "varchar(6)", default="'VALID'", rule="VALID / VOID"),
            col("reprint_of_id", "재발행 원본", "bigint", nullable=True),
            col("reprint_reason", "재발행 사유", "varchar(300)", nullable=True),
        ],
    ),
]

NEW_COLUMNS = {
    W + "warehouse": [
        col("is_default", "용도별 기본 창고", "boolean", default="false")
    ],
    W + "storage_location": [
        col(
            "parent_location_id",
            "상위 위치",
            "bigint",
            nullable=True,
            rule="F03 구역 > 랙 > 단 > 칸",
        ),
        col(
            "level_kind", "계층", "varchar(6)", default="'BIN'", rule=" / ".join(LEVELS)
        ),
        col("capacity_qty", "용량(기본 단위)", "numeric(18,3)", nullable=True),
        col("mix_items", "품목 혼적", "boolean", default="true"),
        col("mix_lots", "LOT 혼적", "boolean", default="true"),
    ],
    W + "item": [
        col("shelf_life_days", "유효기간(일)", "integer", nullable=True, rule="Q5"),
        col("storage_condition", "보관 조건", "varchar(60)", nullable=True),
        col("safety_stock", "안전 재고", "numeric(18,3)", nullable=True),
        col("max_stock", "최대 재고", "numeric(18,3)", nullable=True),
        col("abc_class", "ABC 등급", "varchar(1)", nullable=True),
    ],
    W + "inbound_notice": [
        col(
            "notice_kind",
            "입고 종류",
            "varchar(12)",
            default="'PURCHASE'",
            rule=" / ".join(NOTICE_KINDS),
        )
    ],
}

CONSTRAINTS = []
for t in TABLES:
    CONSTRAINTS += [
        c(t["name"], "PK", ["id"], reason="기본키"),
        c(t["name"], "UK", S + ["id"], reason="공간·세대 복합 참조 대상"),
    ]
for t, field in [
    (PT, "task_no"),
    (PO, "pick_no"),
    (IR, "request_no"),
    (CO, "count_no"),
]:
    CONSTRAINTS += [
        c(t, "UK", S + [field], reason="세대 내 번호 유일"),
        c(t, "CHECK", [field], f"length(btrim({field})) > 0", "번호 필수"),
    ]
CONSTRAINTS += [
    c(LOT, "UK", S + ["item_id", "lot_no"], reason="품목·LOT 번호 유일"),
    c(
        LOT,
        "CHECK",
        ["origin", "status", "lot_no"],
        "origin IN ('RECEIPT', 'MES', 'RETURN', 'OPENING') AND status IN ('AVAILABLE', 'HOLD', 'EXPIRED') AND length(btrim(lot_no)) > 0",
        "출처·상태",
    ),
    c(
        LOT,
        "CHECK",
        ["received_on", "expiry_date"],
        "expiry_date IS NULL OR expiry_date >= received_on",
        "유효기간 순서",
    ),
    c(
        LOT,
        "SERVICE/DB_POLICY",
        ["status"],
        "HOLD = 활성 보류 있음, EXPIRED = 업무 기준일 > 유효기간(일 1회 갱신 대신 조회 때 판정 후 기록). HOLD·EXPIRED LOT은 예약·피킹·불출 불가(Q5)",
        "LOT 출고 가능성",
    ),
    c(
        LH,
        "CHECK",
        ["source", "source_ref", "reason"],
        "source IN ('MANUAL', 'QMS', 'EXPIRY') AND (source <> 'QMS' OR source_ref IS NOT NULL) AND length(btrim(reason)) >= 2",
        "출처·사유",
    ),
    c(
        LH,
        "CHECK",
        ["held_at", "released_at"],
        "released_at IS NULL OR released_at >= held_at",
        "시각 순서",
    ),
    uk_partial(LH, ["lot_id"], "released_at IS NULL", "LOT당 활성 보류 1건"),
    c(
        PT,
        "CHECK",
        ["qty", "status", "to_location_id", "done_at"],
        "qty > 0 AND status IN ('OPEN', 'DONE', 'CANCELLED') AND ((status = 'DONE') = (done_at IS NOT NULL AND to_location_id IS NOT NULL))",
        "수량·완료",
    ),
    c(PO, "UK", S + ["reservation_id"], reason="예약당 피킹 1건"),
    c(
        PO,
        "CHECK",
        ["status", "picked_at", "stock_document_id", "cancel_reason"],
        "(status = 'OPEN' AND picked_at IS NULL) OR (status = 'PICKED' AND picked_at IS NOT NULL AND stock_document_id IS NOT NULL) OR (status = 'CANCELLED' AND length(btrim(cancel_reason)) > 0)",
        "상태별 값",
    ),
    c(PL, "UK", S + ["pick_order_id", "line_no"], reason="문서 내 행 번호 유일"),
    c(
        PL,
        "CHECK",
        ["qty", "picked_qty", "sequence_no"],
        "qty > 0 AND (picked_qty IS NULL OR (picked_qty >= 0 AND picked_qty <= qty)) AND sequence_no >= 1",
        "수량·순서",
    ),
    c(
        PL,
        "SERVICE/DB_POLICY",
        ["lot_no"],
        "LOT 배정 순서: 유효기간 빠른 것(FEFO) → 입고일 빠른 것(FIFO). HOLD·EXPIRED 제외. 피킹 순서는 위치 코드 순. 피킹 확정 시 피킹 수량만 출고장 위치로 PICK 이동, 부족분은 예약에 남음",
        "피킹 배정(Q4·Q5)",
    ),
    c(
        IR,
        "CHECK",
        ["status", "issued_at", "stock_document_id", "cancel_reason"],
        "(status = 'OPEN' AND issued_at IS NULL) OR (status = 'ISSUED' AND issued_at IS NOT NULL AND stock_document_id IS NOT NULL) OR (status = 'CANCELLED' AND length(btrim(cancel_reason)) > 0)",
        "상태별 값",
    ),
    c(IRL, "UK", S + ["issue_request_id", "line_no"], reason="문서 내 행 번호 유일"),
    c(
        IRL,
        "CHECK",
        ["qty", "issued_qty"],
        "qty > 0 AND (issued_qty IS NULL OR issued_qty >= 0)",
        "수량",
    ),
    c(
        IR,
        "SERVICE/DB_POLICY",
        ["line_location_id"],
        "도착 위치는 location_type = LINE. 불출은 FEFO→FIFO LOT으로 PRODUCTION_ISSUE 이동 전표. MES 자재 투입(MES_ISSUE)은 라인 위치 재고에서 차감, 라인 재고가 모자라면 반영 실패 → 원천 반영 현황",
        "생산 불출·라인 차감(Q4)",
    ),
    c(
        CO,
        "CHECK",
        ["kind", "status"],
        "kind IN ('FULL', 'CYCLE') AND status IN ('OPEN', 'COUNTED', 'ADJUSTED', 'CANCELLED')",
        "종류·상태",
    ),
    c(
        CO,
        "CHECK",
        ["status", "adjusted_at", "stock_document_id"],
        "(status = 'ADJUSTED') = (adjusted_at IS NOT NULL) AND (status <> 'ADJUSTED' OR stock_document_id IS NOT NULL OR adjusted_at IS NOT NULL)",
        "조정 시각",
    ),
    c(
        CO,
        "SERVICE/DB_POLICY",
        ["status"],
        "OPEN 동안 대상 위치 재고 이동 금지(실사 잠금). 차이 행만 CYCLE_COUNT 조정 전표. 차이 없으면 전표 없이 ADJUSTED",
        "실사 잠금·조정",
    ),
    c(
        CL,
        "UK",
        S + ["count_order_id", "location_id", "item_id", "lot_no"],
        reason="실사·위치·품목·LOT 1행",
    ),
    c(
        CL,
        "CHECK",
        ["book_qty", "counted_qty"],
        "book_qty >= 0 AND (counted_qty IS NULL OR counted_qty >= 0)",
        "수량 음수 금지",
    ),
    c(SP, "UK", S + ["period_month"], reason="재고 월 1건"),
    c(
        SP,
        "CHECK",
        ["period_month"],
        "period_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'",
        "'YYYY-MM' 형식",
    ),
    c(
        SP,
        "CHECK",
        ["status", "closed_at"],
        "status IN ('open', 'closed') AND ((status = 'closed') = (closed_at IS NOT NULL))",
        "마감 상태",
    ),
    c(
        SP,
        "SERVICE/DB_POLICY",
        ["status"],
        "마감 월(document_month)의 재고 전표 생성·확정·역전표 금지. 마감 후 발견한 차이는 다음 달 조정. 마감 순서: WMS 재고 마감 → ERP 원가 계산 → ERP 회계 마감(Q6)",
        "재고 월 마감(Q6)",
    ),
    c(PI, "UK", S + ["pop_entry_ref"], reason="POP 입력 1건당 가져오기 1회(멱등)"),
    c(
        PI,
        "CHECK",
        ["entry_kind", "result"],
        f"entry_kind IN ({q(POP_KINDS)}) AND result IN ('APPLIED', 'REJECTED')",
        "종류·결과",
    ),
    c(
        PI,
        "CHECK",
        ["result", "reject_reason", "target_id"],
        "(result = 'REJECTED') = (reject_reason IS NOT NULL) AND (result = 'APPLIED') = (target_id IS NOT NULL)",
        "결과별 사유·대상",
    ),
    c(
        PI,
        "SERVICE/DB_POLICY",
        ["pop_entry_ref"],
        "fs.pop.interface.confirmed_entries()의 창고 입력을 가져올 때 WMS 규칙(위치 유형·용량·혼적·LOT 상태·실사 잠금·마감 월)으로 재검증. POP 행은 바꾸지 않는다",
        "POP 가져오기 재검증(Q1)",
    ),
    c(
        LP,
        "CHECK",
        ["label_kind", "status", "copies"],
        "label_kind IN ('LOCATION', 'MATERIAL_LOT') AND status IN ('VALID', 'VOID') AND copies BETWEEN 1 AND 99",
        "종류·상태·매수",
    ),
    c(
        LP,
        "CHECK",
        ["reprint_of_id", "reprint_reason"],
        "(reprint_of_id IS NULL) = (reprint_reason IS NULL)",
        "재발행 사유",
    ),
    uk_partial(
        LP, ["label_kind", "barcode_value"], "status = 'VALID'", "대상당 유효 라벨 1건"
    ),
]
for t, cols_ in [
    (LH, ["lot_id"]),
    (PT, ["status"]),
    (PL, ["pick_order_id"]),
    (IRL, ["issue_request_id"]),
    (CL, ["count_order_id"]),
    (LOT, ["item_id", "expiry_date"]),
]:
    CONSTRAINTS.append(c(t, "INDEX", S + cols_, reason="FK·목록 조회"))

CHANGED_CONSTRAINTS = [
    c(
        W + "storage_location",
        "CHECK",
        ["level_kind", "capacity_qty", "parent_location_id"],
        f"level_kind IN ({q(LEVELS)}) AND (capacity_qty IS NULL OR capacity_qty > 0) AND (parent_location_id IS NULL OR parent_location_id <> id)",
        "계층·용량",
    ),
    c(
        W + "item",
        "CHECK",
        ["shelf_life_days", "safety_stock", "max_stock", "abc_class"],
        "(shelf_life_days IS NULL OR shelf_life_days > 0) AND (safety_stock IS NULL OR safety_stock >= 0) AND (max_stock IS NULL OR safety_stock IS NULL OR max_stock >= safety_stock) AND (abc_class IS NULL OR abc_class IN ('A', 'B', 'C'))",
        "관리 속성 범위",
    ),
    c(
        W + "inbound_notice",
        "CHECK",
        ["notice_kind"],
        f"notice_kind IN ({q(NOTICE_KINDS)})",
        "입고 종류 값",
    ),
    uk_partial(
        W + "warehouse",
        ["purpose"],
        "is_default AND is_active",
        "용도당 기본 창고 1개(DSN-13 Q2: 다창고)",
    ),
]
REPLACED = {
    (W + "warehouse", "purpose IN ('RAW', 'FG')"): f"purpose IN ({q(PURPOSES)})",
    (
        W + "storage_location",
        "location_type IN ('NORMAL','QUARANTINE')",
    ): f"location_type IN ({q(LOCATION_TYPES)})",
    (W + "item", "item_class IN ('RAW', 'FG')"): f"item_class IN ({q(ITEM_CLASSES)})",
    (
        W + "stock_document",
        "document_type IN ('OPENING', 'MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'WMS_INSPECTION', 'ADJUSTMENT', 'TRANSFER', 'REVERSAL')",
    ): f"document_type IN ({q(DOC_TYPES)})",
    (
        W + "stock_document",
        "(document_type IN ('MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'WMS_INSPECTION', 'REVERSAL')) = (source_key IS NOT NULL)",
    ): f"(document_type IN ({q(SOURCED)})) = (source_key IS NOT NULL)",
    (
        W + "stock_document",
        "document_type IN ('OPENING', 'ADJUSTMENT', 'TRANSFER') OR status = 'posted'",
    ): "document_type IN ('OPENING', 'ADJUSTMENT', 'TRANSFER', 'CYCLE_COUNT') OR status = 'posted'",
    (
        W + "source_claim",
        "source_key ~ '^ERP:PURCHASE:.+$'",
    ): "source_key ~ '^ERP:(PURCHASE|PO|SALES_RETURN):.+$'",
}
REMOVED = [
    (W + "item", "CHECK", "lot_tracked = (item_class = 'FG')"),
    (
        W + "warehouse",
        "UK_PARTIAL",
        "UNIQUE (workspace_id, generation_id, purpose) WHERE is_active",
    ),
]

RELATIONS = [
    dict(
        source=t["name"],
        columns=S,
        target="core.data_generation",
        target_columns=["workspace_id", "id"],
        on_delete="RESTRICT",
        on_update="RESTRICT",
        note="같은 참조 범위 유지",
    )
    for t in TABLES
]
RELATIONS += [
    r(LOT, ["item_id"], W + "item", "LOT 품목"),
    r(LH, ["lot_id"], LOT, "보류 LOT"),
    r(PT, ["source_document_id"], W + "stock_document", "입고 전표"),
    r(PT, ["item_id"], W + "item", "품목"),
    r(PT, ["from_location_id"], W + "storage_location", "출발 위치"),
    r(PT, ["suggested_location_id"], W + "storage_location", "추천 위치"),
    r(PT, ["to_location_id"], W + "storage_location", "적치 위치"),
    r(PT, ["stock_document_id"], W + "stock_document", "적치 전표"),
    r(PO, ["reservation_id"], W + "stock_reservation", "출고 예약"),
    r(PO, ["stock_document_id"], W + "stock_document", "피킹 전표"),
    r(PL, ["pick_order_id"], PO, "피킹 소속"),
    r(PL, ["item_id"], W + "item", "품목"),
    r(PL, ["location_id"], W + "storage_location", "피킹 위치"),
    r(IR, ["line_location_id"], W + "storage_location", "라인 위치"),
    r(IR, ["stock_document_id"], W + "stock_document", "불출 전표"),
    r(IRL, ["issue_request_id"], IR, "불출 소속"),
    r(IRL, ["item_id"], W + "item", "품목"),
    r(CO, ["warehouse_id"], W + "warehouse", "실사 창고"),
    r(CO, ["stock_document_id"], W + "stock_document", "조정 전표"),
    r(CL, ["count_order_id"], CO, "실사 소속"),
    r(CL, ["location_id"], W + "storage_location", "위치"),
    r(CL, ["item_id"], W + "item", "품목"),
    r(LP, ["reprint_of_id"], LP, "재발행 원본"),
    r(
        W + "storage_location",
        ["parent_location_id"],
        W + "storage_location",
        "상위 위치",
    ),
]


def st(t, values, default, transition):
    return dict(
        table=t,
        column="status",
        values=list(values),
        default=default,
        transition=transition,
    )


STATES = [
    st(
        LOT,
        ("AVAILABLE", "HOLD", "EXPIRED"),
        "AVAILABLE",
        "AVAILABLE↔HOLD(보류·해제), →EXPIRED(유효기간 경과)",
    ),
    st(PT, ("OPEN", "DONE", "CANCELLED"), "OPEN", "OPEN→DONE(PUTAWAY 전표)/CANCELLED"),
    st(PO, ("OPEN", "PICKED", "CANCELLED"), "OPEN", "OPEN→PICKED(PICK 전표)/CANCELLED"),
    st(
        IR,
        ("OPEN", "ISSUED", "CANCELLED"),
        "OPEN",
        "OPEN→ISSUED(PRODUCTION_ISSUE 전표)/CANCELLED",
    ),
    st(
        CO,
        ("OPEN", "COUNTED", "ADJUSTED", "CANCELLED"),
        "OPEN",
        "OPEN→COUNTED→ADJUSTED(CYCLE_COUNT 전표); OPEN→CANCELLED",
    ),
    st(SP, ("open", "closed"), "open", "open→closed(Q6)"),
    st(LP, ("VALID", "VOID"), "VALID", "VALID→VOID(재발행)"),
]


def apply(d):
    """목표 dict를 제자리에서 바꾸고, 바뀌었으면 True."""
    if not d.get("target"):
        raise SystemExit("apply_dsn13은 schema-target.json에만 적용한다")
    names = {t["name"] for t in d["tables"]}
    if "mes.pop_import" not in names:
        raise SystemExit("apply_dsn12를 먼저 적용한다")
    if PI in names:
        return False
    # 아무것도 바꾸기 전에 확인한다(반쯤 적용된 목표 파일을 남기지 않게).
    found = {(x["table"], x["kind"], x["expression"]) for x in d["constraints"]} & set(
        REMOVED
    )
    hits = {(x["table"], x["expression"]) for x in d["constraints"]} & set(REPLACED)
    if len(found) != len(REMOVED) or len(hits) != len(REPLACED):
        raise SystemExit(
            f"바꿀 기존 제약을 찾지 못했다: {set(REMOVED) - found} {set(REPLACED) - hits}"
        )
    tables = {t["name"]: t for t in d["tables"]}
    for name, columns in NEW_COLUMNS.items():
        cols = tables[name]["columns"]
        at = len(cols) - 1 if cols[-1]["name"] == "created_at" else len(cols)
        cols[at:at] = columns
    for x in tables[W + "item"]["columns"]:
        if x["name"] == "lot_tracked":
            x["rule"] = (
                "DSN-13 Q3: 품목별 설정(원자재도 가능). 입고 검수 때 WMS가 LOT 부여"
            )
    d["constraints"] = [
        x
        for x in d["constraints"]
        if (x["table"], x["kind"], x["expression"]) not in REMOVED
    ]
    for x in d["constraints"]:
        new = REPLACED.get((x["table"], x["expression"]))
        if new:
            x["expression"] = new
    d["tables"].extend(TABLES)
    d["constraints"].extend(CONSTRAINTS + CHANGED_CONSTRAINTS)
    d["relations"].extend(RELATIONS)
    d["states"].extend(STATES)
    for code in d["code_lists"]:
        if code["target"] == W + "warehouse" and code["column"] == "purpose":
            code["values"] = list(PURPOSES)
        if code["target"] == W + "item" and code["column"] == "item_class":
            code["values"] = list(ITEM_CLASSES)
        if code["target"] == W + "stock_document" and code["column"] == "document_type":
            code["values"] = list(DOC_TYPES)
        if (
            code["target"] == W + "storage_location"
            and code["column"] == "location_type"
        ):
            code["values"] = list(LOCATION_TYPES)
    d["code_lists"].append(
        dict(
            target=PI,
            column="entry_kind",
            values=list(POP_KINDS),
            default=None,
            note="입고 / 적치 / 피킹 / 불출 / 실사 / 이동",
        )
    )
    d.update(version="target-0.4.0", task="DSN-13", date="2026-10-05")
    d["change_log"].append(
        dict(
            version="target-0.4.0",
            task="DSN-13",
            date="2026-10-05",
            change="WMS 보강: 새 테이블 12(LOT·LOT 보류·적치·피킹 2·생산 불출 2·실사 2·재고 기간·POP 가져오기·라벨), 기존 6테이블 변경(창고 다창고·용도 8, 위치 계층·유형 6·용량, 품목 LOT 품목별·유효기간·안전재고, 입고 예정 종류, 재고 전표 종류 17, 원천 선점 키 PO·반품)",
            status="설계 전용",
        )
    )
    return True


def main():
    d = json.loads(TARGET.read_text(encoding="utf-8"))
    changed = apply(d)
    if changed:
        TARGET.write_text(
            json.dumps(d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    wms = [t for t in d["tables"] if t["name"].startswith(W)]
    print(
        json.dumps(
            dict(
                changed=changed,
                tables=len(d["tables"]),
                wms_tables=len(wms),
                constraints=len(d["constraints"]),
                relations=len(d["relations"]),
            ),
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
