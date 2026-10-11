"""FLOW-03 자유 컬럼·그룹 보관·검토 상태. 기존 원장은 보존한다."""

from alembic import op

revision = "flow_board_custom"
down_revision = "flow_split"
branch_labels = None
depends_on = None
STATEMENTS = [
    "CREATE TABLE flow.work_column (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,workspace_id bigint NOT NULL,generation_id bigint NOT NULL,board_id bigint NOT NULL,name varchar(120) NOT NULL,kind varchar(16) NOT NULL,builtin_key varchar(32),position integer DEFAULT 0 NOT NULL,width integer DEFAULT 160 NOT NULL,options jsonb DEFAULT '{}'::jsonb NOT NULL,archived_at timestamptz,deleted_at timestamptz,version integer DEFAULT 1 NOT NULL,created_at timestamptz DEFAULT now() NOT NULL,updated_at timestamptz DEFAULT now() NOT NULL)",
    "CREATE TABLE flow.work_cell (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL,workspace_id bigint NOT NULL,generation_id bigint NOT NULL,board_id bigint NOT NULL,task_id bigint NOT NULL,column_id bigint NOT NULL,kind varchar(16) NOT NULL,value jsonb NOT NULL,version integer DEFAULT 1 NOT NULL,created_at timestamptz DEFAULT now() NOT NULL,updated_at timestamptz DEFAULT now() NOT NULL)",
    "ALTER TABLE flow.work_group ADD COLUMN archived_at timestamptz",
    "ALTER TABLE flow.work_group ADD COLUMN deleted_at timestamptz",
    "ALTER TABLE flow.work_task DROP CONSTRAINT c1404_check",
    "ALTER TABLE flow.work_task ADD CONSTRAINT c1404_check CHECK (length(trim(title))>0 AND status IN ('WAITING','WORKING','REVIEW','BLOCKED','DONE','CANCELLED') AND priority IN ('LOW','NORMAL','HIGH','URGENT') AND (starts_on IS NULL OR ends_on IS NULL OR starts_on<=ends_on) AND progress BETWEEN 0 AND 100 AND (status!='DONE' OR progress=100) AND (status IN ('DONE','CANCELLED') OR progress<100) AND version>0 AND parent_id IS DISTINCT FROM id)",
    "ALTER TABLE flow.work_task ADD CONSTRAINT c1429_uk UNIQUE (workspace_id,generation_id,board_id,id)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1430_pk PRIMARY KEY (id)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1431_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1432_idx ON flow.work_column (workspace_id,generation_id)",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT c1433_pk PRIMARY KEY (id)",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT c1434_uk UNIQUE (workspace_id,generation_id,id)",
    "CREATE INDEX c1435_idx ON flow.work_cell (workspace_id,generation_id)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1436_uk UNIQUE (workspace_id,generation_id,board_id,id)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1437_uk UNIQUE (workspace_id,generation_id,board_id,id,kind)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1438_uk UNIQUE (workspace_id,generation_id,board_id,builtin_key)",
    "ALTER TABLE flow.work_column ADD CONSTRAINT c1439_check CHECK (length(trim(name))>0 AND position>=0 AND width BETWEEN 80 AND 600 AND version>0 AND jsonb_typeof(options)='object' AND ((kind='BUILTIN' AND builtin_key IN ('assignee','status','timeline','priority','progress','description')) OR (kind IN ('TEXT','NUMBER','DATE','STATUS','CHECKBOX','TIMELINE') AND builtin_key IS NULL)))",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT c1440_uk UNIQUE (workspace_id,generation_id,task_id,column_id)",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT c1441_check CHECK (version>0 AND (value='null'::jsonb OR CASE kind WHEN 'TEXT' THEN jsonb_typeof(value)='string' AND length(value#>>'{}')<=4000 WHEN 'NUMBER' THEN jsonb_typeof(value)='number' WHEN 'DATE' THEN jsonb_typeof(value)='string' WHEN 'STATUS' THEN jsonb_typeof(value)='string' WHEN 'CHECKBOX' THEN jsonb_typeof(value)='boolean' WHEN 'TIMELINE' THEN jsonb_typeof(value)='object' AND value ?& ARRAY['start','end'] ELSE false END))",
    "ALTER TABLE flow.work_column ADD CONSTRAINT r465_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_column ADD CONSTRAINT r466_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT r467_fk FOREIGN KEY (workspace_id) REFERENCES core.workspace (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT r468_fk FOREIGN KEY (workspace_id,generation_id) REFERENCES core.data_generation (workspace_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_column ADD CONSTRAINT r469_fk FOREIGN KEY (workspace_id,generation_id,board_id) REFERENCES flow.work_board (workspace_id,generation_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT r470_fk FOREIGN KEY (workspace_id,generation_id,board_id,task_id) REFERENCES flow.work_task (workspace_id,generation_id,board_id,id) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "ALTER TABLE flow.work_cell ADD CONSTRAINT r471_fk FOREIGN KEY (workspace_id,generation_id,board_id,column_id,kind) REFERENCES flow.work_column (workspace_id,generation_id,board_id,id,kind) ON DELETE RESTRICT ON UPDATE RESTRICT",
    "INSERT INTO flow.work_column(workspace_id,generation_id,board_id,name,kind,builtin_key,position) SELECT b.workspace_id,b.generation_id,b.id,v.name,'BUILTIN',v.key,v.position FROM flow.work_board b CROSS JOIN (VALUES ('담당자','assignee',0),('상태','status',1),('일정','timeline',2),('진행률','progress',3),('중요도','priority',4),('설명','description',5)) v(name,key,position)",
]
DOWN = [
    "DROP TABLE flow.work_cell",
    "DROP TABLE flow.work_column",
    "ALTER TABLE flow.work_group DROP COLUMN deleted_at",
    "ALTER TABLE flow.work_group DROP COLUMN archived_at",
    "ALTER TABLE flow.work_task DROP CONSTRAINT c1404_check",
    "UPDATE flow.work_task SET status='WORKING' WHERE status='REVIEW'",
    "ALTER TABLE flow.work_task ADD CONSTRAINT c1404_check CHECK (length(trim(title))>0 AND status IN ('WAITING','WORKING','BLOCKED','DONE','CANCELLED') AND priority IN ('LOW','NORMAL','HIGH','URGENT') AND (starts_on IS NULL OR ends_on IS NULL OR starts_on<=ends_on) AND progress BETWEEN 0 AND 100 AND (status!='DONE' OR progress=100) AND (status IN ('DONE','CANCELLED') OR progress<100) AND version>0 AND parent_id IS DISTINCT FROM id)",
    "ALTER TABLE flow.work_task DROP CONSTRAINT c1429_uk",
]


def upgrade():
    for sql in STATEMENTS:
        op.execute(sql)


def downgrade():
    count = (
        op.get_bind()
        .exec_driver_sql(
            "SELECT (SELECT count(*) FROM flow.work_cell)+(SELECT count(*) FROM flow.work_column WHERE kind<>'BUILTIN')"
        )
        .scalar_one()
    )
    if count:
        raise RuntimeError(
            "자유 열·셀 데이터가 있는 FLOW-03 DB는 백업과 명시적 이관 없이 downgrade할 수 없습니다."
        )
    for sql in DOWN:
        op.execute(sql)
