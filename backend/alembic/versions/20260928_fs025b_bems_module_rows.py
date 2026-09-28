"""FS-025a: 기존 공간마다 core.workspace_module 'bems' 행(enabled)을 채운다.

범위 확인(read_scope/write_scope)은 모듈 행이 없으면 꺼진 것으로 본다. 스키마는 바꾸지 않는다(데이터만).
WMS(FS-024)에서 API 단계로 미뤘다가 로컬 개발 DB에서 "꺼짐"으로 보였던 일이 있어, BEMS는 DB 단계에 함께 둔다.
"""

from alembic import op

revision = "fs025b_bems_module"
down_revision = "fs025a_bems"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO core.workspace_module (workspace_id, module_key, enabled)
        SELECT w.id, 'bems', true FROM core.workspace w
        WHERE NOT EXISTS (
          SELECT 1 FROM core.workspace_module m
          WHERE m.workspace_id = w.id AND m.module_key = 'bems'
        )
        """
    )


def downgrade() -> None:
    op.execute("DELETE FROM core.workspace_module WHERE module_key = 'bems'")
