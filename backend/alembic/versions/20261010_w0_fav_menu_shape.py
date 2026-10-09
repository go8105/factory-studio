"""개인 메뉴 구성 JSON 모드 형식 검사.

설계 schema.json 0.22.1(W0-FAV)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: 1fabd8eab1ec7d2de09892cb4858f6b31a0f525c5e8ac668fa951f0e3ee1c5a6
"""

from alembic import op

revision = "w0_fav_menu_shape"
down_revision = "w0_fav_workspace_menus"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE core.workspace ADD CONSTRAINT c1347_check CHECK (menu_preferences IS NULL OR jsonb_typeof(menu_preferences->'sidebarMode') = 'string')",
]
DROPS = [
    "ALTER TABLE core.workspace DROP CONSTRAINT c1347_check",
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
