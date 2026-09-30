"""FS-028a SPC schema: spc 5 tables + core.workspace_module 'spc' key.

Hand-frozen from schema.json v0.13.0 (FS-028a). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY rules are implemented in the SPC service, not as database constraints.
Source SHA256: e13fb0339fb586d23d5c5a4a5deb5e91221e1b6a43f179ff97e16ba3b876c4f9
"""

from alembic import op

revision = "fs028a_spc"
down_revision = "fs025b_bems_module"
branch_labels = None
depends_on = None

MODULE_CHECK = "c22_check"
OLD_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms','wms','bems')"
NEW_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms','wms','bems','spc')"

# 생성 순서(부모 → 자식). 컬럼 순서는 schema.json과 같다.
# C 번호·테이블·컬럼. S는 (workspace_id,generation_id) 축약이다.
TABLES = [
    (
        "spc.characteristic",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(20) NOT NULL, item_code varchar(40) NOT NULL, item_name varchar(100) NOT NULL, process_code varchar(20) NOT NULL, name varchar(100) NOT NULL, unit varchar(10) NOT NULL, lsl numeric(12,4), usl numeric(12,4), target numeric(12,4), subgroup_size smallint NOT NULL DEFAULT 5, decimals smallint NOT NULL DEFAULT 3, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "spc.control_limit",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, characteristic_id bigint NOT NULL, version integer NOT NULL, effective_at timestamptz NOT NULL, basis_from timestamptz NOT NULL, basis_to timestamptz NOT NULL, basis_count integer NOT NULL, xbar_cl numeric(14,6) NOT NULL, xbar_ucl numeric(14,6) NOT NULL, xbar_lcl numeric(14,6) NOT NULL, r_cl numeric(14,6) NOT NULL, r_ucl numeric(14,6) NOT NULL, r_lcl numeric(14,6) NOT NULL, reason varchar(200) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "spc.subgroup",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, characteristic_id bigint NOT NULL, lot_no varchar(50) NOT NULL, item_code varchar(40) NOT NULL, process_code varchar(20) NOT NULL, equipment_code varchar(40) NOT NULL, run_started_at timestamptz NOT NULL, run_ended_at timestamptz, measured_at timestamptz NOT NULL, xbar numeric(14,6) NOT NULL, r numeric(14,6) NOT NULL, status varchar(10) NOT NULL DEFAULT 'valid', void_reason varchar(200), voided_at timestamptz, source varchar(10) NOT NULL, note varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "spc.measurement",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, subgroup_id bigint NOT NULL, seq smallint NOT NULL, value numeric(12,4) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "spc.signal",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, subgroup_id bigint NOT NULL, characteristic_id bigint NOT NULL, control_limit_id bigint NOT NULL, lot_no varchar(50) NOT NULL, chart varchar(4) NOT NULL, rule smallint NOT NULL, value numeric(14,6) NOT NULL, detected_at timestamptz NOT NULL, status varchar(10) NOT NULL DEFAULT 'open', cause_category varchar(12), action varchar(500), resolved_at timestamptz, voided_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()",
    ),
]
KEYS = """
736 spc.characteristic S,code
737 spc.characteristic S,item_code,process_code,name
744 spc.control_limit S,characteristic_id,version
745 spc.control_limit S,characteristic_id,effective_at
752 spc.subgroup S,characteristic_id,lot_no,measured_at
759 spc.measurement S,subgroup_id,seq
762 spc.signal S,subgroup_id,chart,rule
"""
CHECKS = """
738 spc.characteristic code ~ '^[A-Z][A-Z0-9-]{1,19}$'
739 spc.characteristic (lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl)
740 spc.characteristic target IS NULL OR ((lsl IS NULL OR target >= lsl) AND (usl IS NULL OR target <= usl))
741 spc.characteristic subgroup_size = 5
742 spc.characteristic decimals BETWEEN 0 AND 4
746 spc.control_limit version >= 1
747 spc.control_limit basis_count >= 20
748 spc.control_limit basis_from <= basis_to
749 spc.control_limit xbar_lcl < xbar_cl AND xbar_cl < xbar_ucl
750 spc.control_limit r_lcl >= 0 AND r_lcl < r_cl AND r_cl < r_ucl
753 spc.subgroup r >= 0
754 spc.subgroup status IN ('valid', 'void')
755 spc.subgroup (status = 'valid' AND void_reason IS NULL AND voided_at IS NULL) OR (status = 'void' AND void_reason IS NOT NULL AND voided_at IS NOT NULL)
756 spc.subgroup source IN ('SEED', 'MANUAL')
757 spc.subgroup measured_at >= run_started_at AND (run_ended_at IS NULL OR (run_started_at <= run_ended_at AND measured_at <= run_ended_at))
760 spc.measurement seq BETWEEN 1 AND 5
763 spc.signal chart IN ('XBAR', 'R')
764 spc.signal rule BETWEEN 1 AND 3
765 spc.signal rule = 1 OR chart = 'XBAR'
766 spc.signal status IN ('open', 'resolved', 'void')
767 spc.signal cause_category IS NULL OR cause_category IN ('MACHINE', 'MATERIAL', 'MAN', 'METHOD', 'MEASUREMENT', 'ENVIRONMENT')
768 spc.signal action IS NULL OR char_length(btrim(action)) >= 2
769 spc.signal (status = 'open' AND cause_category IS NULL AND action IS NULL AND resolved_at IS NULL AND voided_at IS NULL) OR (status = 'resolved' AND cause_category IS NOT NULL AND action IS NOT NULL AND resolved_at IS NOT NULL AND voided_at IS NULL) OR (status = 'void' AND voided_at IS NOT NULL)
"""
INDEXES = """
772 spc.subgroup S,characteristic_id,measured_at
773 spc.signal S,characteristic_id
774 spc.signal S,control_limit_id
775 spc.signal S,status,lot_no
"""
FKS = """
214 spc.control_limit S,characteristic_id spc.characteristic S,id
215 spc.subgroup S,characteristic_id spc.characteristic S,id
216 spc.measurement S,subgroup_id spc.subgroup S,id
217 spc.signal S,subgroup_id spc.subgroup S,id
218 spc.signal S,characteristic_id spc.characteristic S,id
219 spc.signal S,control_limit_id spc.control_limit S,id
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    op.execute("CREATE SCHEMA spc")
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
    # spc 모듈 행이 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 중단하는 쪽이 안전하다.
    op.execute(f"ALTER TABLE core.workspace_module DROP CONSTRAINT {MODULE_CHECK}")
    op.execute(
        f"ALTER TABLE core.workspace_module ADD CONSTRAINT {MODULE_CHECK} CHECK ({OLD_MODULE_KEYS})"
    )
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP SCHEMA spc")
