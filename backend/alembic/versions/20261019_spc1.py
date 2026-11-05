"""SPC-1a SPC 5표·칼럼 보강.

설계 schema.json 0.28.0(SPC-1a)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: 05084eeafbcbb1d476f5846416f6a12cc57d1ee7112f2308739fc0bb391e2485
"""

from alembic import op

revision = "spc1"
down_revision = "gw_wms_merge"
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE TABLE spc.characteristic_rule (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, characteristic_id bigint NOT NULL, rule_no integer NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE spc.spec_violation (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, subgroup_id bigint NOT NULL, characteristic_id bigint NOT NULL, seq integer NOT NULL, lot_no varchar(50) NOT NULL, value numeric(18,6) NOT NULL, side varchar(4) NOT NULL, limit_value numeric(18,6) NOT NULL, detected_at timestamptz NOT NULL, voided_at timestamptz, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE spc.ocap_item (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, characteristic_id bigint, rule_no integer, seq integer NOT NULL, check_text varchar(300) NOT NULL, cause_category varchar(12), is_active boolean DEFAULT true NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE spc.ocap_check (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, signal_id bigint NOT NULL, ocap_item_id bigint NOT NULL, result varchar(3) NOT NULL, note varchar(300), checked_at timestamptz NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE spc.capability_report (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, characteristic_id bigint NOT NULL, report_start_on date NOT NULL, report_end_on date NOT NULL, version integer NOT NULL, status varchar(12) DEFAULT 'draft' NOT NULL, subgroup_count integer NOT NULL, mean numeric(18,6) NOT NULL, sigma_within numeric(18,6) NOT NULL, sigma_overall numeric(18,6) NOT NULL, cp numeric(8,3), cpk numeric(8,3), pp numeric(8,3), ppk numeric(8,3), skewness numeric(8,4), kurtosis numeric(8,4), comment varchar(1000), confirmed_at timestamptz, created_at timestamptz DEFAULT now() NOT NULL)",
    "ALTER TABLE spc.characteristic ADD COLUMN chart_type varchar(8) DEFAULT 'XBAR_R' NOT NULL",
    "ALTER TABLE spc.characteristic ADD COLUMN defect_source varchar(6)",
    "ALTER TABLE spc.control_limit ADD COLUMN attr_center numeric(18,6)",
    "ALTER TABLE spc.subgroup ADD COLUMN inspected_qty numeric(18,3)",
    "ALTER TABLE spc.subgroup ADD COLUMN defect_count numeric(18,3)",
    "ALTER TABLE spc.subgroup ADD COLUMN gauge_code varchar(30)",
    "ALTER TABLE spc.characteristic DROP CONSTRAINT c739_check",
    "ALTER TABLE spc.characteristic DROP CONSTRAINT c741_check",
    "ALTER TABLE spc.subgroup DROP CONSTRAINT c756_check",
    "ALTER TABLE spc.measurement DROP CONSTRAINT c760_check",
    "ALTER TABLE spc.signal DROP CONSTRAINT c763_check",
    "ALTER TABLE spc.signal DROP CONSTRAINT c764_check",
    "ALTER TABLE spc.signal DROP CONSTRAINT c765_check",
    "ALTER TABLE spc.characteristic ADD CONSTRAINT c739_check CHECK ((chart_type IN ('P', 'NP', 'C', 'U') OR lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl))",
    "ALTER TABLE spc.characteristic ADD CONSTRAINT c741_check CHECK (subgroup_size BETWEEN 1 AND 10)",
    "ALTER TABLE spc.subgroup ADD CONSTRAINT c756_check CHECK (source IN ('SEED', 'MANUAL', 'MES', 'FILE'))",
    "ALTER TABLE spc.measurement ADD CONSTRAINT c760_check CHECK (seq BETWEEN 1 AND 10)",
    "ALTER TABLE spc.signal ADD CONSTRAINT c763_check CHECK (chart IN ('XBAR', 'R', 'I', 'MR', 'P', 'NP', 'C', 'U'))",
    "ALTER TABLE spc.signal ADD CONSTRAINT c764_check CHECK (rule BETWEEN 1 AND 8)",
    "ALTER TABLE spc.signal ADD CONSTRAINT c765_check CHECK (rule = 1 OR chart IN ('XBAR', 'I', 'P', 'NP', 'C', 'U'))",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT c1549_pk PRIMARY KEY (id)",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT c1550_uk UNIQUE (workspace_id,generation_id,id)",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT c1551_pk PRIMARY KEY (id)",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT c1552_uk UNIQUE (workspace_id,generation_id,id)",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT c1553_pk PRIMARY KEY (id)",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT c1554_uk UNIQUE (workspace_id,generation_id,id)",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT c1555_pk PRIMARY KEY (id)",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT c1556_uk UNIQUE (workspace_id,generation_id,id)",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT c1557_pk PRIMARY KEY (id)",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT c1558_uk UNIQUE (workspace_id,generation_id,id)",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT c1559_uk UNIQUE (workspace_id,generation_id,characteristic_id,rule_no)",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT c1560_check CHECK (rule_no BETWEEN 1 AND 8)",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT c1562_uk UNIQUE (workspace_id,generation_id,subgroup_id,seq)",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT c1563_check CHECK ((side = 'LOW' AND value < limit_value) OR (side = 'HIGH' AND value > limit_value))",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT c1565_uk UNIQUE (workspace_id,generation_id,characteristic_id,rule_no,seq)",
    "CREATE UNIQUE INDEX c1566_uidx ON spc.ocap_item (workspace_id,generation_id,seq) WHERE characteristic_id IS NULL AND rule_no IS NULL",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT c1567_check CHECK ((rule_no IS NULL OR rule_no BETWEEN 1 AND 8) AND seq >= 1 AND length(btrim(check_text)) >= 2 AND (cause_category IS NULL OR cause_category IN ('MACHINE', 'MATERIAL', 'MAN', 'METHOD', 'MEASUREMENT', 'ENVIRONMENT')))",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT c1568_uk UNIQUE (workspace_id,generation_id,signal_id,ocap_item_id)",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT c1569_check CHECK (result IN ('OK', 'NG', 'NA') AND (result <> 'NG' OR length(btrim(note)) >= 2))",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT c1571_uk UNIQUE (workspace_id,generation_id,characteristic_id,report_start_on,report_end_on,version)",
    "CREATE UNIQUE INDEX c1572_uidx ON spc.capability_report (workspace_id,generation_id,characteristic_id,report_start_on,report_end_on) WHERE status = 'confirmed'",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT c1573_check CHECK (status IN ('draft', 'confirmed', 'superseded') AND version >= 1 AND ((status = 'draft') = (confirmed_at IS NULL)))",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT c1574_check CHECK (report_end_on >= report_start_on AND subgroup_count >= 20 AND sigma_within >= 0 AND sigma_overall >= 0)",
    "CREATE INDEX c1576_idx ON spc.spec_violation (workspace_id,generation_id,characteristic_id,detected_at)",
    "CREATE INDEX c1577_idx ON spc.ocap_check (workspace_id,generation_id,signal_id)",
    "CREATE INDEX c1578_idx ON spc.capability_report (workspace_id,generation_id,characteristic_id)",
    "ALTER TABLE spc.characteristic ADD CONSTRAINT c1579_check CHECK (chart_type IN ('XBAR_R', 'I_MR', 'P', 'NP', 'C', 'U') AND ((chart_type = 'I_MR') = (subgroup_size = 1)) AND ((chart_type IN ('P', 'NP', 'C', 'U')) = (defect_source IS NOT NULL)) AND (defect_source IS NULL OR defect_source IN ('MES', 'MANUAL')))",
    "ALTER TABLE spc.subgroup ADD CONSTRAINT c1580_check CHECK ((xbar IS NOT NULL AND inspected_qty IS NULL AND defect_count IS NULL) OR (xbar IS NULL AND r IS NULL AND inspected_qty > 0 AND defect_count >= 0))",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT r524_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT r525_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT r526_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT r527_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT r528_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.characteristic_rule ADD CONSTRAINT r529_fk FOREIGN KEY (workspace_id,generation_id,characteristic_id) REFERENCES spc.characteristic (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT r530_fk FOREIGN KEY (workspace_id,generation_id,subgroup_id) REFERENCES spc.subgroup (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.spec_violation ADD CONSTRAINT r531_fk FOREIGN KEY (workspace_id,generation_id,characteristic_id) REFERENCES spc.characteristic (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.ocap_item ADD CONSTRAINT r532_fk FOREIGN KEY (workspace_id,generation_id,characteristic_id) REFERENCES spc.characteristic (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT r533_fk FOREIGN KEY (workspace_id,generation_id,signal_id) REFERENCES spc.signal (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.ocap_check ADD CONSTRAINT r534_fk FOREIGN KEY (workspace_id,generation_id,ocap_item_id) REFERENCES spc.ocap_item (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE spc.capability_report ADD CONSTRAINT r535_fk FOREIGN KEY (workspace_id,generation_id,characteristic_id) REFERENCES spc.characteristic (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
]
DROPS = [
    "ALTER TABLE spc.capability_report DROP CONSTRAINT r535_fk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT r534_fk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT r533_fk",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT r532_fk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT r531_fk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT r530_fk",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT r529_fk",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT r528_fk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT r527_fk",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT r526_fk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT r525_fk",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT r524_fk",
    "ALTER TABLE spc.subgroup DROP CONSTRAINT c1580_check",
    "ALTER TABLE spc.characteristic DROP CONSTRAINT c1579_check",
    "DROP INDEX spc.c1578_idx",
    "DROP INDEX spc.c1577_idx",
    "DROP INDEX spc.c1576_idx",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT c1574_check",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT c1573_check",
    "DROP INDEX spc.c1572_uidx",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT c1571_uk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT c1569_check",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT c1568_uk",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT c1567_check",
    "DROP INDEX spc.c1566_uidx",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT c1565_uk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT c1563_check",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT c1562_uk",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT c1560_check",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT c1559_uk",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT c1558_uk",
    "ALTER TABLE spc.capability_report DROP CONSTRAINT c1557_pk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT c1556_uk",
    "ALTER TABLE spc.ocap_check DROP CONSTRAINT c1555_pk",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT c1554_uk",
    "ALTER TABLE spc.ocap_item DROP CONSTRAINT c1553_pk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT c1552_uk",
    "ALTER TABLE spc.spec_violation DROP CONSTRAINT c1551_pk",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT c1550_uk",
    "ALTER TABLE spc.characteristic_rule DROP CONSTRAINT c1549_pk",
    "ALTER TABLE spc.signal DROP CONSTRAINT c765_check",
    "ALTER TABLE spc.signal DROP CONSTRAINT c764_check",
    "ALTER TABLE spc.signal DROP CONSTRAINT c763_check",
    "ALTER TABLE spc.measurement DROP CONSTRAINT c760_check",
    "ALTER TABLE spc.subgroup DROP CONSTRAINT c756_check",
    "ALTER TABLE spc.characteristic DROP CONSTRAINT c741_check",
    "ALTER TABLE spc.characteristic DROP CONSTRAINT c739_check",
    "ALTER TABLE spc.subgroup DROP COLUMN gauge_code",
    "ALTER TABLE spc.subgroup DROP COLUMN defect_count",
    "ALTER TABLE spc.subgroup DROP COLUMN inspected_qty",
    "ALTER TABLE spc.control_limit DROP COLUMN attr_center",
    "ALTER TABLE spc.characteristic DROP COLUMN defect_source",
    "ALTER TABLE spc.characteristic DROP COLUMN chart_type",
    "DROP TABLE spc.capability_report",
    "DROP TABLE spc.ocap_check",
    "DROP TABLE spc.ocap_item",
    "DROP TABLE spc.spec_violation",
    "DROP TABLE spc.characteristic_rule",
    "ALTER TABLE spc.signal ADD CONSTRAINT c765_check CHECK (rule = 1 OR chart = 'XBAR')",
    "ALTER TABLE spc.signal ADD CONSTRAINT c764_check CHECK (rule BETWEEN 1 AND 3)",
    "ALTER TABLE spc.signal ADD CONSTRAINT c763_check CHECK (chart IN ('XBAR', 'R'))",
    "ALTER TABLE spc.measurement ADD CONSTRAINT c760_check CHECK (seq BETWEEN 1 AND 5)",
    "ALTER TABLE spc.subgroup ADD CONSTRAINT c756_check CHECK (source IN ('SEED', 'MANUAL'))",
    "ALTER TABLE spc.characteristic ADD CONSTRAINT c741_check CHECK (subgroup_size = 5)",
    "ALTER TABLE spc.characteristic ADD CONSTRAINT c739_check CHECK ((lsl IS NOT NULL OR usl IS NOT NULL) AND (lsl IS NULL OR usl IS NULL OR lsl < usl))",
]
# 모듈 키: (표, 제약 이름, 옛 식, 새 식)
MODULE_CHECKS = []


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)
    for table, name, _old, new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({new})")


def downgrade() -> None:
    # 모듈 행·평가가 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 멈추는 쪽이 안전하다.
    for table, name, old, _new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({old})")
    for statement in DROPS:
        op.execute(statement)
