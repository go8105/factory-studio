"""HR-TIME-01 승인 휴가 취소 요청.

설계 schema.json 0.23.1(W1-HR-TIME)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: 691baf541c29a0a3b0f32d1e137d81cf25f92c16af1e96a62fc1417c099c829c
"""

from alembic import op

revision = "hr_time_cancel"
down_revision = "hr_time_company"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE hr.work_request DROP CONSTRAINT c1375_check",
    "ALTER TABLE hr.work_request ADD CONSTRAINT c1375_check CHECK (kind IN ('ANNUAL','HALF_AM','HALF_PM','HOURLY','TRIP') AND status IN ('REQUESTED','APPROVED','REJECTED','CANCELLED','CANCEL_REQUESTED') AND starts_at < ends_at AND minutes >= 0)",
]
DROPS = [
    "ALTER TABLE hr.work_request DROP CONSTRAINT c1375_check",
    "ALTER TABLE hr.work_request ADD CONSTRAINT c1375_check CHECK (kind IN ('ANNUAL','HALF_AM','HALF_PM','HOURLY','TRIP') AND status IN ('REQUESTED','APPROVED','REJECTED','CANCELLED') AND starts_at < ends_at AND minutes >= 0)",
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
