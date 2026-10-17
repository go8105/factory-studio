"""GW-COMPANY-02 회사 보안 기반.

설계 schema.json 0.26.0(GW-COMPANY-02)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: acefeb23a8387828682a85e7418bcd8583f9bc16822f28acb5b2d8e488731f1f
"""

from alembic import op

revision = "gw_company_identity"
down_revision = "flow_board_custom"
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE TABLE gw.collaboration_settings (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, authz_version bigint DEFAULT 1 NOT NULL, initialized_by_user_id bigint NOT NULL, initialized_at timestamptz DEFAULT clock_timestamp() NOT NULL, created_at timestamptz DEFAULT clock_timestamp() NOT NULL)",
    "CREATE TABLE gw.person_identity_binding (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, person_id bigint NOT NULL, user_id bigint NOT NULL, state varchar(12) NOT NULL, version integer DEFAULT 1 NOT NULL, requested_by_user_id bigint NOT NULL, activated_at timestamptz, closed_at timestamptz, reason varchar(500), created_at timestamptz DEFAULT clock_timestamp() NOT NULL)",
    "CREATE TABLE gw.role_grant (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, person_id bigint NOT NULL, role_key varchar(30) NOT NULL, is_active boolean DEFAULT true NOT NULL, version integer DEFAULT 1 NOT NULL, changed_by_user_id bigint NOT NULL, reason varchar(500) NOT NULL, created_at timestamptz DEFAULT clock_timestamp() NOT NULL)",
    "CREATE TABLE gw.document_reader (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, document_id bigint NOT NULL, person_id bigint NOT NULL, is_active boolean DEFAULT true NOT NULL, version integer DEFAULT 1 NOT NULL, granted_by_user_id bigint NOT NULL, reason varchar(500) NOT NULL, created_at timestamptz DEFAULT clock_timestamp() NOT NULL)",
    "CREATE TABLE gw.step_assignment (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, workspace_id bigint NOT NULL, generation_id bigint NOT NULL, document_id bigint NOT NULL, step_id bigint NOT NULL, person_id bigint NOT NULL, assignment_seq integer NOT NULL, reason varchar(500) NOT NULL, assigned_by_user_id bigint NOT NULL, created_at timestamptz DEFAULT clock_timestamp() NOT NULL)",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT c1441_pk PRIMARY KEY (id)",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT c1442_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1443_idx ON gw.collaboration_settings (workspace_id,generation_id)",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT c1444_pk PRIMARY KEY (id)",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT c1445_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1446_idx ON gw.person_identity_binding (workspace_id,generation_id)",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT c1447_check CHECK (version>0)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1448_pk PRIMARY KEY (id)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1449_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1450_idx ON gw.role_grant (workspace_id,generation_id)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1451_check CHECK (version>0)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1452_check CHECK (char_length(btrim(reason)) BETWEEN 2 AND 500)",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT c1453_pk PRIMARY KEY (id)",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT c1454_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1455_idx ON gw.document_reader (workspace_id,generation_id)",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT c1456_check CHECK (version>0)",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT c1457_check CHECK (char_length(btrim(reason)) BETWEEN 2 AND 500)",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT c1458_pk PRIMARY KEY (id)",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT c1459_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1460_idx ON gw.step_assignment (workspace_id,generation_id)",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT c1461_check CHECK (char_length(btrim(reason)) BETWEEN 2 AND 500)",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT c1462_uk UNIQUE (workspace_id,generation_id)",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT c1463_check CHECK (authz_version>0)",
    "CREATE UNIQUE INDEX c1464_uidx ON gw.person_identity_binding (workspace_id,generation_id,person_id) WHERE state<>'CANCELLED'",
    "CREATE UNIQUE INDEX c1465_uidx ON gw.person_identity_binding (workspace_id,generation_id,user_id) WHERE state<>'CANCELLED'",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT c1466_check CHECK ((state='PENDING' AND activated_at IS NULL AND closed_at IS NULL) OR (state='ACTIVE' AND activated_at IS NOT NULL AND closed_at IS NULL) OR (state='SUSPENDED' AND activated_at IS NOT NULL AND closed_at IS NOT NULL AND closed_at>=activated_at) OR (state='CANCELLED' AND activated_at IS NULL AND closed_at IS NOT NULL))",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT c1467_check CHECK (reason IS NULL OR char_length(btrim(reason)) BETWEEN 2 AND 500)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1468_uk UNIQUE (workspace_id,generation_id,person_id,role_key)",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT c1469_check CHECK (role_key IN ('ORG_ADMIN','ROUTE_ADMIN','POLICY_ADMIN','BOARD_PUBLISHER','SECURITY_ADMIN','AUDITOR'))",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT c1470_uk UNIQUE (workspace_id,generation_id,document_id,person_id)",
    "CREATE INDEX c1471_idx ON gw.document_reader (workspace_id,generation_id,person_id,is_active)",
    "ALTER TABLE gw.approval_step ADD CONSTRAINT c1472_uk UNIQUE (workspace_id,generation_id,document_id,id)",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT c1473_uk UNIQUE (workspace_id,generation_id,step_id,assignment_seq)",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT c1474_check CHECK (assignment_seq>0)",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT r471_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.collaboration_settings ADD CONSTRAINT r472_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT r473_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT r474_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.person_identity_binding ADD CONSTRAINT r475_fk FOREIGN KEY (workspace_id,generation_id,person_id) REFERENCES gw.person (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT r476_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT r477_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.role_grant ADD CONSTRAINT r478_fk FOREIGN KEY (workspace_id,generation_id,person_id) REFERENCES gw.person (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT r479_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT r480_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT r481_fk FOREIGN KEY (workspace_id,generation_id,person_id) REFERENCES gw.person (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.document_reader ADD CONSTRAINT r482_fk FOREIGN KEY (workspace_id,generation_id,document_id) REFERENCES gw.approval_document (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT r483_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT r484_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT r485_fk FOREIGN KEY (workspace_id,generation_id,person_id) REFERENCES gw.person (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT r486_fk FOREIGN KEY (workspace_id,generation_id,document_id) REFERENCES gw.approval_document (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE gw.step_assignment ADD CONSTRAINT r487_fk FOREIGN KEY (workspace_id,generation_id,document_id,step_id) REFERENCES gw.approval_step (workspace_id,generation_id,document_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
]
DROPS = [
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT r487_fk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT r486_fk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT r485_fk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT r484_fk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT r483_fk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT r482_fk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT r481_fk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT r480_fk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT r479_fk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT r478_fk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT r477_fk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT r476_fk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT r475_fk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT r474_fk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT r473_fk",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT r472_fk",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT r471_fk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT c1474_check",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT c1473_uk",
    "ALTER TABLE gw.approval_step DROP CONSTRAINT c1472_uk",
    "DROP INDEX gw.c1471_idx",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT c1470_uk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1469_check",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1468_uk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT c1467_check",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT c1466_check",
    "DROP INDEX gw.c1465_uidx",
    "DROP INDEX gw.c1464_uidx",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT c1463_check",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT c1462_uk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT c1461_check",
    "DROP INDEX gw.c1460_idx",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT c1459_uk",
    "ALTER TABLE gw.step_assignment DROP CONSTRAINT c1458_pk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT c1457_check",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT c1456_check",
    "DROP INDEX gw.c1455_idx",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT c1454_uk",
    "ALTER TABLE gw.document_reader DROP CONSTRAINT c1453_pk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1452_check",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1451_check",
    "DROP INDEX gw.c1450_idx",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1449_uk",
    "ALTER TABLE gw.role_grant DROP CONSTRAINT c1448_pk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT c1447_check",
    "DROP INDEX gw.c1446_idx",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT c1445_uk",
    "ALTER TABLE gw.person_identity_binding DROP CONSTRAINT c1444_pk",
    "DROP INDEX gw.c1443_idx",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT c1442_uk",
    "ALTER TABLE gw.collaboration_settings DROP CONSTRAINT c1441_pk",
    "DROP TABLE gw.step_assignment",
    "DROP TABLE gw.document_reader",
    "DROP TABLE gw.role_grant",
    "DROP TABLE gw.person_identity_binding",
    "DROP TABLE gw.collaboration_settings",
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
    # Company authorization history must not disappear through a rollback.
    connection = op.get_bind()
    for table in (
        "collaboration_settings",
        "person_identity_binding",
        "role_grant",
        "document_reader",
        "step_assignment",
    ):
        if connection.exec_driver_sql(
            f"SELECT EXISTS (SELECT 1 FROM gw.{table})"
        ).scalar():
            raise RuntimeError(
                "GW 회사 보안 데이터가 있어 downgrade를 중단합니다. 보호 백업과 복구 계획이 필요합니다."
            )
    # 모듈 행·평가가 남아 있으면 옛 CHECK 복원이 실패한다. CASCADE 없이 멈추는 쪽이 안전하다.
    for table, name, old, _new in MODULE_CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        op.execute(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({old})")
    for statement in DROPS:
        op.execute(statement)
