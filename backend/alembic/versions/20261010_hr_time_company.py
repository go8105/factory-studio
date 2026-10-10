"""HR-TIME-01 회사 공동 근무.

설계 schema.json 0.23.0(W1-HR-TIME)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: 94f0534c8525997baa17f48df0032cf8fd489362caaf454ed0d6c1067fd49ec6
"""

from alembic import op

revision = "hr_time_company"
down_revision = "w0_fav_menu_shape"
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE TABLE core.company (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, name varchar(100) NOT NULL, is_example boolean DEFAULT false NOT NULL, timezone varchar(40) DEFAULT 'Asia/Seoul' NOT NULL, status varchar(10) DEFAULT 'ACTIVE' NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE core.company_member (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, user_id bigint NOT NULL, role varchar(10) NOT NULL, is_active boolean DEFAULT true NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.work_account (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, user_id bigint NOT NULL, employee_id bigint NOT NULL, work_role varchar(10) NOT NULL, is_active boolean DEFAULT true NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.work_policy (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, start_time time DEFAULT '09:00' NOT NULL, end_time time DEFAULT '18:00' NOT NULL, break_start time DEFAULT '12:00' NOT NULL, break_end time DEFAULT '13:00' NOT NULL, daily_minutes integer DEFAULT 480 NOT NULL, annual_days integer DEFAULT 15 NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.clock_session (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, employee_id bigint NOT NULL, work_date date NOT NULL, clock_in timestamptz NOT NULL, clock_out timestamptz, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.work_request (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, employee_id bigint NOT NULL, kind varchar(12) NOT NULL, starts_at timestamptz NOT NULL, ends_at timestamptz NOT NULL, minutes integer NOT NULL, reason varchar(500) NOT NULL, destination varchar(200), status varchar(12) DEFAULT 'REQUESTED' NOT NULL, decided_by bigint, decided_at timestamptz, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.work_event (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, employee_id bigint NOT NULL, actor_user_id bigint NOT NULL, action varchar(40) NOT NULL, entity_id bigint NOT NULL, summary jsonb NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE hr.work_close (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, month varchar(7) NOT NULL, closed_by bigint NOT NULL, created_at timestamptz DEFAULT now() NOT NULL)",
    "ALTER TABLE core.workspace DROP CONSTRAINT c278_check",
    "ALTER TABLE core.workspace DROP CONSTRAINT c279_check",
    "ALTER TABLE core.workspace ADD CONSTRAINT c278_check CHECK (workspace_kind IN ('MEMBER','GUEST','TEMPLATE','COMPANY'))",
    "ALTER TABLE core.workspace ADD CONSTRAINT c279_check CHECK ((workspace_kind = 'MEMBER' AND owner_user_id IS NOT NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL) OR (workspace_kind = 'GUEST' AND owner_user_id IS NULL AND guest_session_key IS NOT NULL AND expires_at IS NOT NULL AND guest_actor_key IS NOT NULL) OR (workspace_kind IN ('TEMPLATE','COMPANY') AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL))",
    "ALTER TABLE core.company ADD CONSTRAINT c1348_pk PRIMARY KEY (id)",
    "ALTER TABLE core.company ADD CONSTRAINT c1349_uk UNIQUE (workspace_id)",
    "ALTER TABLE core.company ADD CONSTRAINT c1350_check CHECK (status IN ('ACTIVE','INACTIVE'))",
    "ALTER TABLE core.company_member ADD CONSTRAINT c1351_pk PRIMARY KEY (id)",
    "ALTER TABLE core.company_member ADD CONSTRAINT c1352_uk UNIQUE (workspace_id,user_id)",
    "ALTER TABLE core.company_member ADD CONSTRAINT c1353_check CHECK (role IN ('OWNER','MEMBER'))",
    "CREATE INDEX c1354_idx ON core.company_member (user_id)",
    "ALTER TABLE hr.work_account ADD CONSTRAINT c1355_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.work_account ADD CONSTRAINT c1356_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1357_idx ON hr.work_account (workspace_id,generation_id)",
    "ALTER TABLE hr.work_account ADD CONSTRAINT c1358_uk UNIQUE (workspace_id,generation_id,user_id)",
    "ALTER TABLE hr.work_account ADD CONSTRAINT c1359_uk UNIQUE (workspace_id,generation_id,employee_id)",
    "ALTER TABLE hr.work_account ADD CONSTRAINT c1360_check CHECK (work_role IN ('ADMIN','STAFF'))",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT c1361_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT c1362_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1363_idx ON hr.work_policy (workspace_id,generation_id)",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT c1364_uk UNIQUE (workspace_id,generation_id)",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT c1365_check CHECK (start_time < break_start AND break_start < break_end AND break_end < end_time AND daily_minutes > 0 AND annual_days >= 0)",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT c1366_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT c1367_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1368_idx ON hr.clock_session (workspace_id,generation_id)",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT c1369_uk UNIQUE (workspace_id,generation_id,employee_id,work_date)",
    "CREATE UNIQUE INDEX c1370_uidx ON hr.clock_session (workspace_id,generation_id,employee_id) WHERE clock_out IS NULL",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT c1371_check CHECK (clock_out IS NULL OR clock_out >= clock_in)",
    "ALTER TABLE hr.work_request ADD CONSTRAINT c1372_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.work_request ADD CONSTRAINT c1373_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1374_idx ON hr.work_request (workspace_id,generation_id)",
    "ALTER TABLE hr.work_request ADD CONSTRAINT c1375_check CHECK (kind IN ('ANNUAL','HALF_AM','HALF_PM','HOURLY','TRIP') AND status IN ('REQUESTED','APPROVED','REJECTED','CANCELLED') AND starts_at < ends_at AND minutes >= 0)",
    "CREATE INDEX c1376_idx ON hr.work_request (workspace_id,generation_id,employee_id)",
    "ALTER TABLE hr.work_event ADD CONSTRAINT c1377_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.work_event ADD CONSTRAINT c1378_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1379_idx ON hr.work_event (workspace_id,generation_id)",
    "ALTER TABLE hr.work_close ADD CONSTRAINT c1381_pk PRIMARY KEY (id)",
    "ALTER TABLE hr.work_close ADD CONSTRAINT c1382_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1383_idx ON hr.work_close (workspace_id,generation_id)",
    "ALTER TABLE hr.work_close ADD CONSTRAINT c1384_uk UNIQUE (workspace_id,generation_id,month)",
    r"ALTER TABLE hr.work_close ADD CONSTRAINT c1385_check CHECK (month ~ '^\d{4}-(0[1-9]|1[0-2])$')",
    "ALTER TABLE core.company ADD CONSTRAINT r412_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE core.company_member ADD CONSTRAINT r413_fk FOREIGN KEY (workspace_id) REFERENCES core.company (workspace_id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE core.company_member ADD CONSTRAINT r414_fk FOREIGN KEY (user_id) REFERENCES core.app_user (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_account ADD CONSTRAINT r415_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_account ADD CONSTRAINT r416_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_account ADD CONSTRAINT r417_fk FOREIGN KEY (workspace_id,generation_id,employee_id) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT r418_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_policy ADD CONSTRAINT r419_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT r420_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT r421_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.clock_session ADD CONSTRAINT r422_fk FOREIGN KEY (workspace_id,generation_id,employee_id) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_request ADD CONSTRAINT r423_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_request ADD CONSTRAINT r424_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_request ADD CONSTRAINT r425_fk FOREIGN KEY (workspace_id,generation_id,employee_id) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_request ADD CONSTRAINT r426_fk FOREIGN KEY (workspace_id,generation_id,decided_by) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_event ADD CONSTRAINT r427_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_event ADD CONSTRAINT r428_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_event ADD CONSTRAINT r429_fk FOREIGN KEY (workspace_id,generation_id,employee_id) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_close ADD CONSTRAINT r430_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_close ADD CONSTRAINT r431_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE hr.work_close ADD CONSTRAINT r432_fk FOREIGN KEY (workspace_id,generation_id,closed_by) REFERENCES hr.employee (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
]
DROPS = [
    "ALTER TABLE hr.work_close DROP CONSTRAINT r432_fk",
    "ALTER TABLE hr.work_close DROP CONSTRAINT r431_fk",
    "ALTER TABLE hr.work_close DROP CONSTRAINT r430_fk",
    "ALTER TABLE hr.work_event DROP CONSTRAINT r429_fk",
    "ALTER TABLE hr.work_event DROP CONSTRAINT r428_fk",
    "ALTER TABLE hr.work_event DROP CONSTRAINT r427_fk",
    "ALTER TABLE hr.work_request DROP CONSTRAINT r426_fk",
    "ALTER TABLE hr.work_request DROP CONSTRAINT r425_fk",
    "ALTER TABLE hr.work_request DROP CONSTRAINT r424_fk",
    "ALTER TABLE hr.work_request DROP CONSTRAINT r423_fk",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT r422_fk",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT r421_fk",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT r420_fk",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT r419_fk",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT r418_fk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT r417_fk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT r416_fk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT r415_fk",
    "ALTER TABLE core.company_member DROP CONSTRAINT r414_fk",
    "ALTER TABLE core.company_member DROP CONSTRAINT r413_fk",
    "ALTER TABLE core.company DROP CONSTRAINT r412_fk",
    "ALTER TABLE hr.work_close DROP CONSTRAINT c1385_check",
    "ALTER TABLE hr.work_close DROP CONSTRAINT c1384_uk",
    "DROP INDEX hr.c1383_idx",
    "ALTER TABLE hr.work_close DROP CONSTRAINT c1382_uk",
    "ALTER TABLE hr.work_close DROP CONSTRAINT c1381_pk",
    "DROP INDEX hr.c1379_idx",
    "ALTER TABLE hr.work_event DROP CONSTRAINT c1378_uk",
    "ALTER TABLE hr.work_event DROP CONSTRAINT c1377_pk",
    "DROP INDEX hr.c1376_idx",
    "ALTER TABLE hr.work_request DROP CONSTRAINT c1375_check",
    "DROP INDEX hr.c1374_idx",
    "ALTER TABLE hr.work_request DROP CONSTRAINT c1373_uk",
    "ALTER TABLE hr.work_request DROP CONSTRAINT c1372_pk",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT c1371_check",
    "DROP INDEX hr.c1370_uidx",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT c1369_uk",
    "DROP INDEX hr.c1368_idx",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT c1367_uk",
    "ALTER TABLE hr.clock_session DROP CONSTRAINT c1366_pk",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT c1365_check",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT c1364_uk",
    "DROP INDEX hr.c1363_idx",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT c1362_uk",
    "ALTER TABLE hr.work_policy DROP CONSTRAINT c1361_pk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT c1360_check",
    "ALTER TABLE hr.work_account DROP CONSTRAINT c1359_uk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT c1358_uk",
    "DROP INDEX hr.c1357_idx",
    "ALTER TABLE hr.work_account DROP CONSTRAINT c1356_uk",
    "ALTER TABLE hr.work_account DROP CONSTRAINT c1355_pk",
    "DROP INDEX core.c1354_idx",
    "ALTER TABLE core.company_member DROP CONSTRAINT c1353_check",
    "ALTER TABLE core.company_member DROP CONSTRAINT c1352_uk",
    "ALTER TABLE core.company_member DROP CONSTRAINT c1351_pk",
    "ALTER TABLE core.company DROP CONSTRAINT c1350_check",
    "ALTER TABLE core.company DROP CONSTRAINT c1349_uk",
    "ALTER TABLE core.company DROP CONSTRAINT c1348_pk",
    "ALTER TABLE core.workspace DROP CONSTRAINT c279_check",
    "ALTER TABLE core.workspace DROP CONSTRAINT c278_check",
    "DROP TABLE hr.work_close",
    "DROP TABLE hr.work_event",
    "DROP TABLE hr.work_request",
    "DROP TABLE hr.clock_session",
    "DROP TABLE hr.work_policy",
    "DROP TABLE hr.work_account",
    "DROP TABLE core.company_member",
    "DROP TABLE core.company",
    "ALTER TABLE core.workspace ADD CONSTRAINT c279_check CHECK ((workspace_kind = 'MEMBER' AND owner_user_id IS NOT NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL) OR (workspace_kind = 'GUEST' AND owner_user_id IS NULL AND guest_session_key IS NOT NULL AND expires_at IS NOT NULL AND guest_actor_key IS NOT NULL) OR (workspace_kind = 'TEMPLATE' AND owner_user_id IS NULL AND guest_session_key IS NULL AND expires_at IS NULL AND guest_actor_key IS NULL))",
    "ALTER TABLE core.workspace ADD CONSTRAINT c278_check CHECK (workspace_kind IN ('MEMBER','GUEST','TEMPLATE'))",
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
