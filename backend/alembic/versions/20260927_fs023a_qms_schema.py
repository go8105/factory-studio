"""FS-023a QMS schema: qms 6 tables + core.workspace_module 'qms' key.

Hand-frozen from schema.json v0.10.0 (FS-023a). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY rules are implemented in the QMS service, not as database constraints.
Source SHA256: d20fdf86d08173b2a30b415088ab71e225158f38c7c037c930105107a28cc06c
"""

from alembic import op

revision = "fs023a_qms"
down_revision = "7e97937e7bd0"
branch_labels = None
depends_on = None

MODULE_CHECK = "c22_check"
OLD_MODULE_KEYS = "module_key IN ('core','mes','erp','fems')"
NEW_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms')"

# 생성 순서(부모 → 자식). 컬럼 순서는 schema.json과 같다.
TABLES = [
    (
        "qms.defect_type",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(30) NOT NULL, name varchar(100) NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "qms.inspection_spec",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, item_code varchar(40) NOT NULL, item_name varchar(100) NOT NULL, version_no integer NOT NULL DEFAULT 1, status varchar(20) NOT NULL DEFAULT 'draft', published_at timestamptz, note varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "qms.inspection_spec_item",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, spec_id bigint NOT NULL, seq integer NOT NULL, name varchar(100) NOT NULL, method varchar(12) NOT NULL, lower_limit numeric(15,4), upper_limit numeric(15,4), unit varchar(10), is_required boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "qms.inspection",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, inspection_no varchar(40) NOT NULL, source varchar(10) NOT NULL, lot_no varchar(50) NOT NULL, item_code varchar(40) NOT NULL, item_name varchar(100) NOT NULL, lot_qty numeric(15,3) NOT NULL, unit varchar(10) NOT NULL, sample_qty numeric(15,3) NOT NULL, spec_id bigint NOT NULL, reinspection_of_id bigint, status varchar(20) NOT NULL DEFAULT 'draft', result varchar(10), inspected_on date NOT NULL, inspection_month varchar(7) NOT NULL, confirmed_at timestamptz, note varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "qms.inspection_value",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, inspection_id bigint NOT NULL, spec_item_id bigint NOT NULL, measured_value numeric(15,4), pass_value boolean, judgement varchar(4), defect_type_id bigint, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "qms.quality_hold",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, hold_no varchar(40) NOT NULL, lot_no varchar(50) NOT NULL, item_code varchar(40) NOT NULL, inspection_id bigint NOT NULL, status varchar(20) NOT NULL DEFAULT 'held', held_at timestamptz NOT NULL, disposition varchar(12), release_inspection_id bigint, release_reason varchar(300), released_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()",
    ),
]

# C 번호·테이블·컬럼. S는 (workspace_id,generation_id) 축약이다.
KEYS = """
538 qms.defect_type S,code
541 qms.inspection_spec S,item_code,version_no
549 qms.inspection_spec_item S,spec_id,seq
553 qms.inspection S,inspection_no
565 qms.inspection_value S,inspection_id,spec_item_id
570 qms.quality_hold S,hold_no
"""
CHECKS = """
539 qms.defect_type code ~ '^[A-Z][A-Z0-9_]{1,29}$'
542 qms.inspection_spec version_no >= 1
543 qms.inspection_spec status IN ('draft', 'published', 'retired')
544 qms.inspection_spec status = 'draft' OR published_at IS NOT NULL
545 qms.inspection_spec length(btrim(item_code)) > 0 AND length(btrim(item_name)) > 0
550 qms.inspection_spec_item seq >= 1
551 qms.inspection_spec_item method IN ('RANGE', 'PASS_FAIL')
552 qms.inspection_spec_item (method = 'PASS_FAIL' AND lower_limit IS NULL AND upper_limit IS NULL AND unit IS NULL) OR (method = 'RANGE' AND unit IS NOT NULL AND (lower_limit IS NOT NULL OR upper_limit IS NOT NULL) AND (lower_limit IS NULL OR upper_limit IS NULL OR lower_limit <= upper_limit))
554 qms.inspection source IN ('MES', 'MANUAL')
555 qms.inspection (status = 'draft' AND result IS NULL AND confirmed_at IS NULL) OR (status = 'confirmed' AND result IN ('PASS', 'FAIL') AND confirmed_at IS NOT NULL)
556 qms.inspection lot_qty > 0 AND sample_qty > 0 AND sample_qty <= lot_qty
557 qms.inspection length(btrim(lot_no)) > 0 AND length(btrim(item_code)) > 0 AND length(btrim(item_name)) > 0 AND length(btrim(unit)) > 0
558 qms.inspection inspection_month ~ '^[0-9]{4}-(0[1-9]|1[0-2])$'
559 qms.inspection reinspection_of_id IS NULL OR reinspection_of_id <> id
566 qms.inspection_value measured_value IS NULL OR pass_value IS NULL
567 qms.inspection_value judgement IS NULL OR judgement IN ('PASS', 'FAIL')
571 qms.quality_hold status IN ('held', 'released')
572 qms.quality_hold (status = 'held' AND disposition IS NULL AND released_at IS NULL AND release_inspection_id IS NULL AND release_reason IS NULL) OR (status = 'released' AND disposition IN ('REINSPECTED', 'CONCESSION', 'SCRAP') AND released_at IS NOT NULL)
573 qms.quality_hold (disposition IS NULL) OR (disposition = 'REINSPECTED' AND release_inspection_id IS NOT NULL) OR (disposition IN ('CONCESSION', 'SCRAP') AND release_inspection_id IS NULL AND release_reason IS NOT NULL AND length(btrim(release_reason)) > 0)
574 qms.quality_hold length(btrim(lot_no)) > 0 AND length(btrim(item_code)) > 0
"""
INDEXES = """
579 qms.inspection S,spec_id
580 qms.inspection S,reinspection_of_id
581 qms.inspection S,lot_no,status
582 qms.inspection S,inspection_month
583 qms.inspection_value S,spec_item_id
584 qms.inspection_value S,defect_type_id
585 qms.quality_hold S,inspection_id
586 qms.quality_hold S,release_inspection_id
"""
PARTIALS = """
546 qms.inspection_spec S,item_code | status = 'published'
560 qms.inspection S,lot_no | status = 'draft'
575 qms.quality_hold S,lot_no | status = 'held'
"""
FKS = """
167 qms.inspection_spec_item S,spec_id qms.inspection_spec S,id
168 qms.inspection S,spec_id qms.inspection_spec S,id
169 qms.inspection S,reinspection_of_id qms.inspection S,id
170 qms.inspection_value S,inspection_id qms.inspection S,id
171 qms.inspection_value S,spec_item_id qms.inspection_spec_item S,id
172 qms.inspection_value S,defect_type_id qms.defect_type S,id
173 qms.quality_hold S,inspection_id qms.inspection S,id
174 qms.quality_hold S,release_inspection_id qms.inspection S,id
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    op.execute("CREATE SCHEMA qms")
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
    # qms 모듈 행이 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 중단하는 쪽이 안전하다.
    op.execute(f"ALTER TABLE core.workspace_module DROP CONSTRAINT {MODULE_CHECK}")
    op.execute(
        f"ALTER TABLE core.workspace_module ADD CONSTRAINT {MODULE_CHECK} CHECK ({OLD_MODULE_KEYS})"
    )
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP SCHEMA qms")
