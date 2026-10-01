"""FS-029a CMMS schema: cmms 6 tables + module key 'cmms' (workspace_module·app_review).

Hand-frozen from schema.json v0.17.0 (FS-029a). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY rules are implemented in the CMMS service, not as database constraints.
Source SHA256: 2b3af513ca97d3478f8f5b5300f66f42a2fa37a89f55aee637f008d0af796727
"""

from alembic import op

revision = "fs029a_cmms"
down_revision = "fs030b_gw_module"
branch_labels = None
depends_on = None

MODULE_CHECKS = [
    (
        "core.workspace_module",
        "c22_check",
        "module_key IN ('core','mes','erp','fems','qms','wms','bems','spc', 'gw')",
        "module_key IN ('core','mes','erp','fems','qms','wms','bems','spc', 'gw', 'cmms')",
    ),
    (
        "core.app_review",
        "c856_check",
        "module_key IN ('mes', 'erp', 'fems', 'qms', 'wms', 'bems', 'spc', 'gw')",
        "module_key IN ('mes', 'erp', 'fems', 'qms', 'wms', 'bems', 'spc', 'gw', 'cmms')",
    ),
]

# 생성 순서(부모 → 자식). 컬럼 순서는 schema.json과 같다.
# C 번호·테이블·컬럼. S는 (workspace_id,generation_id) 축약이다.
TABLES = [
    (
        "cmms.asset",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, asset_type varchar(12) NOT NULL, location varchar(100), source varchar(6) NOT NULL, source_code varchar(40), is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "cmms.pm_plan",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, asset_id bigint NOT NULL, code varchar(20) NOT NULL, title varchar(200) NOT NULL, checklist varchar(500) NOT NULL, interval_days integer NOT NULL, start_on date NOT NULL, last_done_on date, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "cmms.work_order",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, wo_no varchar(30) NOT NULL, asset_id bigint NOT NULL, kind varchar(2) NOT NULL, source varchar(12) NOT NULL, source_ref varchar(60), source_summary varchar(300), pm_plan_id bigint, due_on date, title varchar(200) NOT NULL, description varchar(1000), status varchar(12) NOT NULL DEFAULT 'REQUESTED', requested_at timestamptz NOT NULL, failure_at timestamptz, started_at timestamptz, completed_at timestamptz, restored_at timestamptz, cause_category varchar(12), action varchar(500), cancelled_at timestamptz, cancel_reason varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "cmms.work_log",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, work_order_id bigint NOT NULL, logged_at timestamptz NOT NULL, minutes integer NOT NULL, note varchar(300) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "cmms.spare_part",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, unit varchar(10) NOT NULL, safety_stock numeric(12,3) NOT NULL DEFAULT 0, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "cmms.part_usage",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, work_order_id bigint NOT NULL, spare_part_id bigint NOT NULL, qty numeric(12,3) NOT NULL, used_at timestamptz NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
]
KEYS = """
990 cmms.asset S,code
997 cmms.pm_plan S,code
1002 cmms.work_order S,wo_no
1022 cmms.spare_part S,code
"""
CHECKS = """
991 cmms.asset code ~ '^[A-Z][A-Z0-9-]{1,19}$'
992 cmms.asset asset_type IN ('INJECTION', 'ASSEMBLY', 'INSPECTION', 'HVAC', 'UTILITY', 'OTHER')
993 cmms.asset source IN ('MES', 'BEMS', 'CMMS')
994 cmms.asset (source = 'CMMS') = (source_code IS NULL)
998 cmms.pm_plan code ~ '^[A-Z][A-Z0-9-]{1,19}$'
999 cmms.pm_plan interval_days BETWEEN 1 AND 365
1000 cmms.pm_plan last_done_on IS NULL OR last_done_on >= start_on
1003 cmms.work_order kind IN ('BM', 'PM')
1004 cmms.work_order source IN ('MANUAL', 'BEMS_ALARM', 'SPC_SIGNAL', 'PM_PLAN')
1005 cmms.work_order (kind = 'PM') = (source = 'PM_PLAN')
1006 cmms.work_order (kind = 'PM' AND pm_plan_id IS NOT NULL AND due_on IS NOT NULL) OR (kind = 'BM' AND pm_plan_id IS NULL AND due_on IS NULL)
1007 cmms.work_order (source IN ('BEMS_ALARM', 'SPC_SIGNAL')) = (source_ref IS NOT NULL)
1008 cmms.work_order (kind = 'BM') = (failure_at IS NOT NULL)
1009 cmms.work_order status IN ('REQUESTED', 'IN_PROGRESS', 'COMPLETED', 'CANCELLED')
1010 cmms.work_order cause_category IS NULL OR cause_category IN ('WEAR', 'LUBRICATION', 'ELECTRICAL', 'SETTING', 'EXTERNAL', 'OTHER')
1011 cmms.work_order (status = 'REQUESTED' AND started_at IS NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (status = 'IN_PROGRESS' AND started_at IS NOT NULL AND completed_at IS NULL AND cancelled_at IS NULL) OR (status = 'COMPLETED' AND started_at IS NOT NULL AND completed_at IS NOT NULL AND cause_category IS NOT NULL AND action IS NOT NULL AND cancelled_at IS NULL) OR (status = 'CANCELLED' AND completed_at IS NULL AND cancelled_at IS NOT NULL AND cancel_reason IS NOT NULL)
1012 cmms.work_order restored_at IS NULL OR restored_at >= failure_at
1013 cmms.work_order NOT (kind = 'BM' AND status = 'COMPLETED' AND restored_at IS NULL) AND (restored_at IS NULL OR kind = 'BM')
1014 cmms.work_order (started_at IS NULL OR started_at >= requested_at) AND (completed_at IS NULL OR completed_at >= started_at)
1015 cmms.work_order (action IS NULL OR char_length(btrim(action)) >= 2) AND (cancel_reason IS NULL OR char_length(btrim(cancel_reason)) >= 2)
1020 cmms.work_log minutes BETWEEN 1 AND 1440
1023 cmms.spare_part code ~ '^[A-Z][A-Z0-9-]{1,19}$'
1024 cmms.spare_part safety_stock >= 0
1025 cmms.part_usage qty > 0
"""
INDEXES = """
1027 cmms.pm_plan S,asset_id
1028 cmms.work_order S,asset_id,status
1029 cmms.work_order S,pm_plan_id
1030 cmms.work_order S,status,requested_at
1031 cmms.work_log S,work_order_id
1032 cmms.part_usage S,work_order_id
1033 cmms.part_usage S,spare_part_id,used_at
"""
PARTIALS = """
995 cmms.asset S,source,source_code | source <> 'CMMS'
1016 cmms.work_order S,source,source_ref | source IN ('BEMS_ALARM', 'SPC_SIGNAL') AND status <> 'CANCELLED'
1017 cmms.work_order S,pm_plan_id,due_on | kind = 'PM' AND status <> 'CANCELLED'
"""
FKS = """
264 cmms.pm_plan S,asset_id cmms.asset S,id
265 cmms.work_order S,asset_id cmms.asset S,id
266 cmms.work_order S,pm_plan_id cmms.pm_plan S,id
267 cmms.work_log S,work_order_id cmms.work_order S,id
268 cmms.part_usage S,work_order_id cmms.work_order S,id
269 cmms.part_usage S,spare_part_id cmms.spare_part S,id
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    op.execute("CREATE SCHEMA cmms")
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
    for table, name, _old, new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({new})")


def downgrade() -> None:
    # cmms 모듈 행·평가가 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 중단하는 쪽이 안전하다.
    for table, name, old, _new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({old})")
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP SCHEMA cmms")
