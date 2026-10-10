"""FLOW-02a: preserve company boards while moving their ownership to Flow."""

from alembic import op

revision = "flow_split"
down_revision = "gw_projects"
branch_labels = None
depends_on = None
TABLES = (
    "work_board",
    "work_board_member",
    "work_group",
    "work_task",
    "work_task_assignee",
    "work_task_comment",
    "work_task_event",
    "work_board_favorite",
    "work_view_preference",
    "work_project_settings",
)
CHECKS = (
    ("core.workspace_module", "c22_check", "'core',"),
    ("core.app_review", "c856_check", ""),
)


def module_checks(flow):
    for table, name, extra in CHECKS:
        op.execute(f"ALTER TABLE {table} DROP CONSTRAINT {name}")
        values = extra + "'mes','erp','fems','qms','wms','bems','spc','gw','cmms','hr'"
        if flow:
            values += ",'flow'"
        op.execute(
            f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK (module_key IN ({values}))"
        )


def favorites(forward):
    old, new = (
        ("gw:projects", "flow:boards") if forward else ("flow:boards", "gw:projects")
    )
    old_task, new_task = (
        ("gw:my-tasks", "flow:my-tasks")
        if forward
        else ("flow:my-tasks", "gw:my-tasks")
    )
    op.execute(f"""UPDATE core.workspace w SET menu_preferences=jsonb_set(menu_preferences,'{{menuIds}}',
      (SELECT jsonb_agg(menu ORDER BY position) FROM
        (SELECT menu,min(position) position FROM
          (SELECT CASE value WHEN '{old}' THEN '{new}' WHEN '{old_task}' THEN '{new_task}' ELSE value END menu,ordinality position
           FROM jsonb_array_elements_text(w.menu_preferences->'menuIds') WITH ORDINALITY) mapped
         GROUP BY menu) unique_menus)), menu_preferences_version=menu_preferences_version+1
      WHERE menu_preferences->'menuIds' ?| ARRAY['{old}','{old_task}']""")


def upgrade():
    # ALTER SET SCHEMA moves owned identity sequences and preserves FK/index OIDs.
    op.execute("CREATE SCHEMA flow")
    for table in TABLES:
        op.execute(f"ALTER TABLE gw.{table} SET SCHEMA flow")
    module_checks(True)
    op.execute("""INSERT INTO core.workspace_module(workspace_id,module_key,enabled,seeded_generation_id)
      SELECT workspace_id,'flow',enabled,seeded_generation_id FROM core.workspace_module WHERE module_key='gw'
      ON CONFLICT(workspace_id,module_key) DO NOTHING""")
    favorites(True)


def downgrade():
    if (
        op.get_bind()
        .exec_driver_sql(
            "SELECT 1 FROM core.app_review WHERE module_key='flow' LIMIT 1"
        )
        .first()
    ):
        raise RuntimeError(
            "Flow 이용 후기는 보존해야 합니다. 이전 제품으로 역이관할 수 없습니다."
        )
    favorites(False)
    op.execute("DELETE FROM core.workspace_module WHERE module_key='flow'")
    module_checks(False)
    for table in reversed(TABLES):
        op.execute(f"ALTER TABLE flow.{table} SET SCHEMA gw")
    op.execute("DROP SCHEMA flow")
