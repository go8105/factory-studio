"""내 공간 즐겨찾기 및 사이드바 메뉴 구성.

설계 schema.json 0.22.0(W0-FAV)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: 3290edfb6ab449c85fa220b2b7498a73a1970b6a4ad7c2f9a039cf75ecdd937b
"""

from alembic import op

revision = "w0_fav_workspace_menus"
down_revision = "gw_a_dsn31"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE core.workspace ADD COLUMN menu_preferences jsonb",
    "ALTER TABLE core.workspace ADD COLUMN menu_preferences_version bigint DEFAULT 1 NOT NULL",
    "ALTER TABLE core.workspace ADD CONSTRAINT c1345_check CHECK (menu_preferences IS NULL OR (jsonb_typeof(menu_preferences) = 'object' AND menu_preferences ?& ARRAY['menuIds','sidebarMode'] AND jsonb_typeof(menu_preferences->'menuIds') = 'array' AND menu_preferences->>'sidebarMode' IN ('all','favorites')))",
    "ALTER TABLE core.workspace ADD CONSTRAINT c1346_check CHECK (menu_preferences_version > 0)",
]
DROPS = [
    "ALTER TABLE core.workspace DROP CONSTRAINT c1346_check",
    "ALTER TABLE core.workspace DROP CONSTRAINT c1345_check",
    "ALTER TABLE core.workspace DROP COLUMN menu_preferences_version",
    "ALTER TABLE core.workspace DROP COLUMN menu_preferences",
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
