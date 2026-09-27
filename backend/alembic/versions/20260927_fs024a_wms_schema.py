"""FS-024a WMS schema: wms 6 tables + core.workspace_module 'wms' key.

Hand-frozen from schema.json v0.11.0 (FS-024a). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY rules are implemented in the WMS service, not as database constraints.
Source SHA256: 0a8ed3798ad6e919a2caa7ab8f434e868ec6f28283b09238bda8f5e50e031ba9
"""

from alembic import op

revision = "fs024a_wms"
down_revision = "fs023b_qms_module"
branch_labels = None
depends_on = None

MODULE_CHECK = "c22_check"
OLD_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms')"
NEW_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms','wms')"

# 생성 순서(부모 → 자식). 컬럼 순서는 schema.json과 같다.
TABLES = [
    (
        "wms.warehouse",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, purpose varchar(10) NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "wms.storage_location",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, warehouse_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, is_default boolean NOT NULL DEFAULT false, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "wms.item",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, item_code varchar(40) NOT NULL, name varchar(100) NOT NULL, base_unit varchar(10) NOT NULL, item_class varchar(10) NOT NULL, lot_tracked boolean NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "wms.item_unit_conversion",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, item_id bigint NOT NULL, from_unit varchar(10) NOT NULL, factor numeric(18,6) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "wms.stock_document",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, document_no varchar(40) NOT NULL, document_type varchar(20) NOT NULL, status varchar(10) NOT NULL DEFAULT 'draft', source_key varchar(100), source_ref varchar(40), reverses_document_id bigint, reason_code varchar(10), document_on date NOT NULL, document_month varchar(7) NOT NULL, posted_at timestamptz, note varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "wms.stock_move",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, document_id bigint NOT NULL, line_no integer NOT NULL, item_id bigint NOT NULL, location_id bigint NOT NULL, lot_no varchar(50), qty_delta numeric(18,3) NOT NULL, source_qty numeric(18,3), source_unit varchar(10), moved_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
]
# C 번호·테이블·컬럼. S는 (workspace_id,generation_id) 축약이다.
KEYS = """
599 wms.warehouse S,code
605 wms.storage_location S,warehouse_id,code
611 wms.item S,item_code
616 wms.item_unit_conversion S,item_id,from_unit
619 wms.stock_document S,document_no
636 wms.stock_move S,document_id,line_no
"""
CHECKS = """
600 wms.warehouse code ~ '^[A-Z][A-Z0-9-]{1,19}$'
601 wms.warehouse purpose IN ('RAW', 'FG')
602 wms.warehouse length(btrim(name)) > 0
606 wms.storage_location code ~ '^[A-Z][A-Z0-9-]{1,19}$'
607 wms.storage_location length(btrim(name)) > 0
608 wms.storage_location NOT is_default OR is_active
612 wms.item item_class IN ('RAW', 'FG')
613 wms.item lot_tracked = (item_class = 'FG')
614 wms.item length(btrim(item_code)) > 0 AND length(btrim(name)) > 0 AND length(btrim(base_unit)) > 0
617 wms.item_unit_conversion factor > 0
620 wms.stock_document document_type IN ('OPENING', 'MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'ADJUSTMENT', 'TRANSFER', 'REVERSAL')
621 wms.stock_document status IN ('draft', 'posted')
622 wms.stock_document (status = 'posted') = (posted_at IS NOT NULL)
623 wms.stock_document document_type IN ('OPENING', 'ADJUSTMENT', 'TRANSFER') OR status = 'posted'
624 wms.stock_document (document_type IN ('MES_RECEIPT', 'MES_ISSUE', 'ERP_SHIPMENT', 'ERP_PURCHASE', 'REVERSAL')) = (source_key IS NOT NULL)
625 wms.stock_document (document_type = 'REVERSAL') = (reverses_document_id IS NOT NULL)
626 wms.stock_document reverses_document_id IS NULL OR reverses_document_id <> id
627 wms.stock_document (document_type = 'ADJUSTMENT' AND reason_code IN ('RETURN', 'SCRAP', 'COUNT', 'OTHER')) OR (document_type <> 'ADJUSTMENT' AND reason_code IS NULL)
628 wms.stock_document reason_code IS DISTINCT FROM 'OTHER' OR (note IS NOT NULL AND length(btrim(note)) > 0)
629 wms.stock_document document_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
637 wms.stock_move line_no >= 1
638 wms.stock_move qty_delta <> 0
639 wms.stock_move (source_qty IS NULL) = (source_unit IS NULL)
640 wms.stock_move lot_no IS NULL OR length(btrim(lot_no)) > 0
"""
INDEXES = """
643 wms.stock_document S,reverses_document_id
644 wms.stock_document S,document_month
645 wms.stock_move S,item_id,location_id,lot_no
646 wms.stock_move S,location_id
"""
PARTIALS = """
603 wms.warehouse S,purpose | is_active
609 wms.storage_location S,warehouse_id | is_default
630 wms.stock_document S,source_key | document_type <> 'REVERSAL'
631 wms.stock_document S,reverses_document_id | reverses_document_id IS NOT NULL
"""
FKS = """
181 wms.storage_location S,warehouse_id wms.warehouse S,id
182 wms.item_unit_conversion S,item_id wms.item S,id
183 wms.stock_document S,reverses_document_id wms.stock_document S,id
184 wms.stock_move S,document_id wms.stock_document S,id
185 wms.stock_move S,item_id wms.item S,id
186 wms.stock_move S,location_id wms.storage_location S,id
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    op.execute("CREATE SCHEMA wms")
    for name, columns in TABLES:
        op.execute(f"CREATE TABLE {name} ({columns})")
        op.execute(f"ALTER TABLE {name} ADD PRIMARY KEY (id)")
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT {name.split('.')[1]}_scope_uk UNIQUE (workspace_id,generation_id,id)"
        )
    for row in rows(KEYS):
        number, name, columns = row.split()
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT c{number}_uk UNIQUE ({expand(columns)})"
        )
    for row in rows(CHECKS):
        number, name, expression = row.split(" ", 2)
        try:
            op.execute(
                f"ALTER TABLE {name} ADD CONSTRAINT c{number}_check CHECK ({expression})"
            )
        except Exception as exc:
            raise RuntimeError(f"C{number} {name}: {expression}\n{exc}") from exc
    for row in rows(INDEXES):
        number, name, columns = row.split()
        op.execute(f"CREATE INDEX c{number}_idx ON {name} ({expand(columns)})")
    for row in rows(PARTIALS):
        definition, predicate = row.split(" | ", 1)
        number, name, columns = definition.split()
        op.execute(
            f"CREATE UNIQUE INDEX c{number}_uidx ON {name} ({expand(columns)}) WHERE {predicate}"
        )
    for name, _ in TABLES:
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT generation_anchor FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation(workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT"
        )
    for row in rows(FKS):
        number, name, columns, target, target_columns = row.split()
        op.execute(
            f"ALTER TABLE {name} ADD CONSTRAINT r{number}_fk FOREIGN KEY ({expand(columns)}) REFERENCES {target} ({expand(target_columns)}) ON DELETE RESTRICT ON UPDATE RESTRICT"
        )
    op.execute(f"ALTER TABLE core.workspace_module DROP CONSTRAINT {MODULE_CHECK}")
    op.execute(
        f"ALTER TABLE core.workspace_module ADD CONSTRAINT {MODULE_CHECK} CHECK ({NEW_MODULE_KEYS})"
    )


def downgrade() -> None:
    # wms 모듈 행이 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 중단하는 쪽이 안전하다.
    op.execute(f"ALTER TABLE core.workspace_module DROP CONSTRAINT {MODULE_CHECK}")
    op.execute(
        f"ALTER TABLE core.workspace_module ADD CONSTRAINT {MODULE_CHECK} CHECK ({OLD_MODULE_KEYS})"
    )
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP SCHEMA wms")
