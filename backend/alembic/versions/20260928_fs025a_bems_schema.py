"""FS-025a BEMS schema: bems 10 tables + core.workspace_module 'bems' key.

Hand-frozen from schema.json v0.12.0 (FS-025a). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
SERVICE/DB_POLICY rules are implemented in the BEMS service, not as database constraints.
FS-013 R4 (bems schema forbidden) is lifted by FS-025 D18.
Source SHA256: d5e5491504f2777f2d6595effc03e3d1d2fc1c1350a2ddf1727348e319034179
"""

from alembic import op

revision = "fs025a_bems"
down_revision = "fs024b_wms_module"
branch_labels = None
depends_on = None

MODULE_CHECK = "c22_check"
OLD_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms','wms')"
NEW_MODULE_KEYS = "module_key IN ('core','mes','erp','fems','qms','wms','bems')"

# 생성 순서(부모 → 자식). 컬럼 순서는 schema.json과 같다.
TABLES = [
    (
        "bems.zone",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, kind varchar(12) NOT NULL, floor_area_m2 numeric(10,2), is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.meter",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, zone_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, usage varchar(10) NOT NULL, unit varchar(10) NOT NULL DEFAULT 'kWh', is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.sensor",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, zone_id bigint NOT NULL, code varchar(20) NOT NULL, metric varchar(10) NOT NULL, unit varchar(10) NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.hvac_unit",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, zone_id bigint NOT NULL, code varchar(20) NOT NULL, name varchar(100) NOT NULL, meter_id bigint, rated_kw numeric(8,2) NOT NULL, state varchar(4) NOT NULL DEFAULT 'OFF', control_source varchar(10) NOT NULL DEFAULT 'SCHEDULE', state_changed_at timestamptz, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.energy_reading",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, meter_id bigint NOT NULL, period_start timestamptz NOT NULL, value numeric(12,3) NOT NULL, quality varchar(10) NOT NULL DEFAULT 'valid', source varchar(12) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.environment_reading",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, sensor_id bigint NOT NULL, period_start timestamptz NOT NULL, value numeric(8,2) NOT NULL, quality varchar(10) NOT NULL DEFAULT 'valid', source varchar(12) NOT NULL, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.schedule_slot",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, hvac_unit_id bigint NOT NULL, day_kind varchar(8) NOT NULL, start_hour integer NOT NULL, end_hour integer NOT NULL, mode varchar(4) NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.control_command",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, zone_id bigint NOT NULL, hvac_unit_id bigint, command varchar(14) NOT NULL, mode varchar(4), setpoint_kind varchar(10), value numeric(8,2), source varchar(10) NOT NULL, requested_at timestamptz NOT NULL, result varchar(10) NOT NULL, reject_reason varchar(40), note varchar(300), created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.alarm_rule",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, zone_id bigint NOT NULL, metric varchar(10) NOT NULL, comparator varchar(4) NOT NULL, threshold numeric(8,2) NOT NULL, duration_hours integer NOT NULL, severity varchar(10) NOT NULL, is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()",
    ),
    (
        "bems.alarm",
        "id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, alarm_rule_id bigint NOT NULL, sensor_id bigint NOT NULL, status varchar(14) NOT NULL DEFAULT 'raised', raised_at timestamptz NOT NULL, peak_value numeric(8,2) NOT NULL, acknowledged_at timestamptz, ack_note varchar(300), cleared_at timestamptz, created_at timestamptz NOT NULL DEFAULT now()",
    ),
]
# C 번호·테이블·컬럼. S는 (workspace_id,generation_id) 축약이다.
KEYS = """
667 bems.zone S,code
672 bems.meter S,code
677 bems.sensor S,code
678 bems.sensor S,zone_id,metric
681 bems.hvac_unit S,code
688 bems.energy_reading S,meter_id,period_start
693 bems.environment_reading S,sensor_id,period_start
708 bems.alarm_rule S,zone_id,metric,comparator
"""
CHECKS = """
668 bems.zone code ~ '^[A-Z][A-Z0-9-]{1,19}$'
669 bems.zone kind IN ('OFFICE', 'PRODUCTION', 'UTILITY')
670 bems.zone floor_area_m2 IS NULL OR floor_area_m2 > 0
673 bems.meter code ~ '^[A-Z][A-Z0-9-]{1,19}$'
674 bems.meter usage IN ('LIGHTING', 'HVAC', 'OFFICE', 'OTHER')
675 bems.meter unit = 'kWh'
679 bems.sensor code ~ '^[A-Z][A-Z0-9-]{1,19}$'
680 bems.sensor (metric = 'TEMP' AND unit = '℃') OR (metric = 'HUMIDITY' AND unit = '%') OR (metric = 'CO2' AND unit = 'ppm')
682 bems.hvac_unit code ~ '^[A-Z][A-Z0-9-]{1,19}$'
683 bems.hvac_unit rated_kw > 0
684 bems.hvac_unit state IN ('OFF', 'COOL', 'HEAT', 'FAN')
685 bems.hvac_unit control_source IN ('SCHEDULE', 'MANUAL')
689 bems.energy_reading value >= 0
690 bems.energy_reading quality IN ('valid', 'invalid')
691 bems.energy_reading source IN ('SEED', 'SIMULATION')
694 bems.environment_reading quality IN ('valid', 'invalid')
695 bems.environment_reading source IN ('SEED', 'SIMULATION')
697 bems.schedule_slot day_kind IN ('WEEKDAY', 'WEEKEND')
698 bems.schedule_slot start_hour BETWEEN 0 AND 23 AND end_hour BETWEEN 1 AND 24 AND start_hour < end_hour
699 bems.schedule_slot mode IN ('COOL', 'HEAT', 'FAN')
701 bems.control_command command IN ('POWER_ON', 'POWER_OFF', 'SET_MODE', 'SET_SETPOINT')
702 bems.control_command command = 'SET_SETPOINT' OR hvac_unit_id IS NOT NULL
703 bems.control_command (command = 'SET_MODE' AND mode IN ('COOL', 'HEAT', 'FAN')) OR (command <> 'SET_MODE' AND mode IS NULL)
704 bems.control_command (command = 'SET_SETPOINT' AND setpoint_kind IN ('COOL_TEMP', 'HEAT_TEMP', 'CO2_MAX') AND value IS NOT NULL) OR (command <> 'SET_SETPOINT' AND setpoint_kind IS NULL AND value IS NULL)
705 bems.control_command source IN ('MANUAL', 'SCHEDULE', 'SEED')
706 bems.control_command (result = 'APPLIED' AND reject_reason IS NULL) OR (result = 'REJECTED' AND reject_reason IS NOT NULL)
709 bems.alarm_rule metric IN ('TEMP', 'HUMIDITY', 'CO2')
710 bems.alarm_rule comparator IN ('HIGH', 'LOW')
711 bems.alarm_rule duration_hours BETWEEN 1 AND 24
712 bems.alarm_rule severity IN ('WARNING', 'CRITICAL')
713 bems.alarm status IN ('raised', 'acknowledged', 'cleared')
714 bems.alarm (status = 'raised' AND acknowledged_at IS NULL AND cleared_at IS NULL) OR (status = 'acknowledged' AND acknowledged_at IS NOT NULL AND cleared_at IS NULL) OR (status = 'cleared' AND cleared_at IS NOT NULL)
"""
INDEXES = """
717 bems.meter S,zone_id
718 bems.hvac_unit S,zone_id
719 bems.hvac_unit S,meter_id
720 bems.schedule_slot S,hvac_unit_id,day_kind
721 bems.control_command S,zone_id,setpoint_kind,requested_at
722 bems.control_command S,hvac_unit_id
723 bems.alarm S,alarm_rule_id
724 bems.alarm S,sensor_id
725 bems.alarm S,status
"""
PARTIALS = """
715 bems.alarm S,alarm_rule_id,sensor_id | status <> 'cleared'
"""
FKS = """
197 bems.meter S,zone_id bems.zone S,id
198 bems.sensor S,zone_id bems.zone S,id
199 bems.hvac_unit S,zone_id bems.zone S,id
200 bems.hvac_unit S,meter_id bems.meter S,id
201 bems.energy_reading S,meter_id bems.meter S,id
202 bems.environment_reading S,sensor_id bems.sensor S,id
203 bems.schedule_slot S,hvac_unit_id bems.hvac_unit S,id
204 bems.control_command S,zone_id bems.zone S,id
205 bems.control_command S,hvac_unit_id bems.hvac_unit S,id
206 bems.alarm_rule S,zone_id bems.zone S,id
207 bems.alarm S,alarm_rule_id bems.alarm_rule S,id
208 bems.alarm S,sensor_id bems.sensor S,id
"""


def expand(columns: str) -> str:
    return columns.replace("S,", "workspace_id,generation_id,")


def rows(block: str) -> list[str]:
    return block.strip().splitlines()


def upgrade() -> None:
    op.execute("CREATE SCHEMA bems")
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
    # bems 모듈 행이 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 중단하는 쪽이 안전하다.
    op.execute(f"ALTER TABLE core.workspace_module DROP CONSTRAINT {MODULE_CHECK}")
    op.execute(
        f"ALTER TABLE core.workspace_module ADD CONSTRAINT {MODULE_CHECK} CHECK ({OLD_MODULE_KEYS})"
    )
    for row in rows(FKS):
        number, name, *_ = row.split()
        op.execute(f"ALTER TABLE {name} DROP CONSTRAINT r{number}_fk")
    for name, _ in reversed(TABLES):
        op.execute(f"DROP TABLE {name}")
    op.execute("DROP SCHEMA bems")
