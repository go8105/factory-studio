"""SPC-1c 계수형 부분군을 위한 NULL 허용.

설계 schema.json 0.29.0(SPC-1c)에서 tools/build_migration.py로 생성했다. 실행할 때 JSON을 읽지 않는다.
c·r 번호는 schema.json의 constraints·relations 순번이다. SERVICE/DB_POLICY는 서비스가 지키는 규칙이라 DB 제약이 아니다.
Source SHA256: a5d408b77c2786735e62247b02c8cd57c0052f51ed07abaa42f34265af4e7849
"""

from alembic import op

revision = "spc2"
down_revision = "spc1"
branch_labels = None
depends_on = None

STATEMENTS = [
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_cl DROP NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_ucl DROP NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_lcl DROP NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_cl DROP NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_ucl DROP NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_lcl DROP NOT NULL",
    "ALTER TABLE spc.subgroup ALTER COLUMN xbar DROP NOT NULL",
    "ALTER TABLE spc.subgroup ALTER COLUMN r DROP NOT NULL",
]
DROPS = [
    "ALTER TABLE spc.subgroup ALTER COLUMN r SET NOT NULL",
    "ALTER TABLE spc.subgroup ALTER COLUMN xbar SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_lcl SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_ucl SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN r_cl SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_lcl SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_ucl SET NOT NULL",
    "ALTER TABLE spc.control_limit ALTER COLUMN xbar_cl SET NOT NULL",
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
