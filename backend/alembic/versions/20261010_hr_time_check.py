"""Rebuild work request CHECK after varchar widening to preserve canonical DDL."""

from alembic import op

revision = "hr_time_check"
down_revision = "hr_time_status_len"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE hr.work_request DROP CONSTRAINT c1375_check")
    op.execute(
        "ALTER TABLE hr.work_request ADD CONSTRAINT c1375_check CHECK (kind IN ('ANNUAL','HALF_AM','HALF_PM','HOURLY','TRIP') AND status IN ('REQUESTED','APPROVED','REJECTED','CANCELLED','CANCEL_REQUESTED') AND starts_at < ends_at AND minutes >= 0)"
    )


def downgrade():
    # Previous revision has the same semantic CHECK; no data transformation.
    pass
