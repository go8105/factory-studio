"""승인 휴가 취소 대기 상태의 길이. 전용 DB에 적용된 revision은 보존한다."""
from alembic import op

revision='hr_time_status_len'
down_revision='hr_time_cancel'
branch_labels=None
depends_on=None

def upgrade():
    op.execute('ALTER TABLE hr.work_request ALTER COLUMN status TYPE varchar(24)')

def downgrade():
    # 긴 상태가 남아 있으면 축소를 거부한다. 기록을 삭제하거나 잘라내지 않는다.
    op.execute('ALTER TABLE hr.work_request ALTER COLUMN status TYPE varchar(12)')
