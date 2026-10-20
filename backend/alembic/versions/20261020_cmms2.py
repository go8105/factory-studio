"""CMMS-1e 사용량 기준 PM을 위한 NULL 허용.

설계 schema.json 0.31.0(CMMS-1e)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: bac97d2f9b0698e2711e9822a4f54b28a0727fcfe60b621a6d340ddd52b09e54
"""

from alembic import op

revision = "cmms2"
down_revision = "cmms1"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE cmms.pm_plan ALTER COLUMN interval_days DROP NOT NULL",
]
DROPS = [
    "ALTER TABLE cmms.pm_plan ALTER COLUMN interval_days SET NOT NULL",
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
