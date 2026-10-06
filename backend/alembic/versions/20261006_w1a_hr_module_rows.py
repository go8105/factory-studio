"""W1a: 기존 공간마다 core.workspace_module 'hr' 행(enabled)을 채운다.

범위 확인(read_scope/write_scope)은 모듈 행이 없으면 꺼진 것으로 본다. 스키마는 바꾸지 않는다(데이터만).
W0-1 지연 복사: seeded_generation_id는 NULL로 둔다 — HR을 처음 열 때 그 시드만 복사한다.
"""

from alembic import op

revision = "w1a_hr_module"
down_revision = "w1a_hr"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO core.workspace_module (workspace_id, module_key, enabled)
        SELECT w.id, 'hr', true FROM core.workspace w
        WHERE NOT EXISTS (
          SELECT 1 FROM core.workspace_module m
          WHERE m.workspace_id = w.id AND m.module_key = 'hr'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM core.workspace_module WHERE module_key = 'hr'")
