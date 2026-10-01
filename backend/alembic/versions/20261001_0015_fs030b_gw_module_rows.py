"""FS-030a: enable GW for existing workspaces, preserving other module settings."""

from alembic import op

revision = "fs030b_gw_module"
down_revision = "fs030a_gw"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "INSERT INTO core.workspace_module(workspace_id,module_key,enabled) SELECT id,'gw',true FROM core.workspace ON CONFLICT (workspace_id,module_key) DO NOTHING"
    )


def downgrade():
    op.execute("DELETE FROM core.workspace_module WHERE module_key='gw'")
