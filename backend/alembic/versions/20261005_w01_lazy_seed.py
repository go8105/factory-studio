"""W0-1 게스트·세대 지연 복사: 솔루션 시드를 처음 열 때 복사한다(DSN-01 S2).

core.data_generation.template_generation_id — 이 세대가 복사해 온 템플릿 세대(FK 없음: 템플릿 정리와 무관).
core.workspace_module.seeded_generation_id — 그 솔루션 시드를 복사한 세대. 활성 세대와 같을 때만 '준비됨'.
기존 공간은 모두 전체 복사본이므로 활성 세대로 채운다.
"""

from alembic import op

revision = "w01_lazy_seed"
down_revision = "fs029b_cmms_module"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE core.data_generation ADD COLUMN template_generation_id bigint"
    )
    op.execute(
        "ALTER TABLE core.workspace_module ADD COLUMN seeded_generation_id bigint"
    )
    op.execute(
        "UPDATE core.workspace_module m SET seeded_generation_id=w.active_generation_id "
        "FROM core.workspace w WHERE w.id=m.workspace_id"
    )


def downgrade() -> None:
    op.execute("ALTER TABLE core.workspace_module DROP COLUMN seeded_generation_id")
    op.execute("ALTER TABLE core.data_generation DROP COLUMN template_generation_id")
