"""FS-023b: 기존 공간마다 core.workspace_module 'qms' 행(enabled)을 채운다.

범위 확인(read_scope/write_scope)은 모듈 행이 없으면 꺼진 것으로 본다. FS-023a는 CHECK만 넓혔으므로
이미 있던 템플릿·회원·게스트 공간에 행을 넣어야 QMS를 쓸 수 있다. 스키마는 바꾸지 않는다(데이터만).
"""

from alembic import op

revision = "fs023b_qms_module"
down_revision = "fs023a_qms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO core.workspace_module (workspace_id, module_key, enabled)
        SELECT w.id, 'qms', true FROM core.workspace w
        WHERE NOT EXISTS (
          SELECT 1 FROM core.workspace_module m
          WHERE m.workspace_id = w.id AND m.module_key = 'qms'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM core.workspace_module WHERE module_key = 'qms'")
