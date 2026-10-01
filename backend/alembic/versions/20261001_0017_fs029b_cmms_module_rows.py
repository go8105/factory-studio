"""FS-029a: 기존 공간마다 core.workspace_module 'cmms' 행(enabled)을 채운다.

범위 확인(read_scope/write_scope)은 모듈 행이 없으면 꺼진 것으로 본다. 스키마는 바꾸지 않는다(데이터만).
새 솔루션 킷 a단계 규칙: 모듈 행은 DB 단계에서 함께 넣는다(WMS 때 빠뜨려 로컬에서 "꺼짐"으로 보였다).
"""

from alembic import op

revision = "fs029b_cmms_module"
down_revision = "fs029a_cmms"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO core.workspace_module (workspace_id, module_key, enabled)
        SELECT w.id, 'cmms', true FROM core.workspace w
        WHERE NOT EXISTS (
          SELECT 1 FROM core.workspace_module m
          WHERE m.workspace_id = w.id AND m.module_key = 'cmms'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM core.workspace_module WHERE module_key = 'cmms'")
