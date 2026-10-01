"""FS-040 launcher review: core.app_review (rating + one-line comment).

Hand-frozen from schema.json v0.15.0 (FS-040). Does not read JSON at runtime.
C numbers are zero-based schema.json constraints indexes; R numbers are relations indexes.
No workspace FK: reviews outlive guest workspace cleanup (D73).
"""

from alembic import op

revision = "fs040_app_review"
down_revision = "fs026a_wms_receiving_reservation"
branch_labels = None
depends_on = None

STATEMENTS = [
    "CREATE TABLE core.app_review (id bigint GENERATED ALWAYS AS IDENTITY NOT NULL, module_key varchar(24) NOT NULL, actor_kind varchar(10) NOT NULL, user_id bigint, guest_actor_key uuid, nickname varchar(20) NOT NULL, rating smallint NOT NULL, comment varchar(100) NOT NULL, created_at timestamptz NOT NULL DEFAULT now())",
    "ALTER TABLE core.app_review ADD PRIMARY KEY (id)",
    "ALTER TABLE core.app_review ADD CONSTRAINT c856_check CHECK (module_key IN ('mes', 'erp', 'fems', 'qms', 'wms', 'bems', 'spc'))",
    "ALTER TABLE core.app_review ADD CONSTRAINT c857_check CHECK (actor_kind IN ('MEMBER', 'GUEST'))",
    "ALTER TABLE core.app_review ADD CONSTRAINT c858_check CHECK ((actor_kind = 'MEMBER' AND user_id IS NOT NULL AND guest_actor_key IS NULL) OR (actor_kind = 'GUEST' AND user_id IS NULL AND guest_actor_key IS NOT NULL))",
    "ALTER TABLE core.app_review ADD CONSTRAINT c859_check CHECK (rating BETWEEN 1 AND 5)",
    "ALTER TABLE core.app_review ADD CONSTRAINT c860_check CHECK (char_length(btrim(comment)) >= 2)",
    "ALTER TABLE core.app_review ADD CONSTRAINT c861_check CHECK (char_length(btrim(nickname)) >= 1)",
    "CREATE UNIQUE INDEX c862_uidx ON core.app_review (module_key, user_id) WHERE user_id IS NOT NULL",
    "CREATE UNIQUE INDEX c863_uidx ON core.app_review (module_key, guest_actor_key) WHERE guest_actor_key IS NOT NULL",
    "CREATE UNIQUE INDEX c864_uidx ON core.app_review (module_key, nickname) WHERE actor_kind = 'GUEST'",
    "CREATE INDEX c865_idx ON core.app_review (module_key, created_at)",
    "CREATE INDEX c866_idx ON core.app_review (user_id)",
    "ALTER TABLE core.app_review ADD CONSTRAINT r236_fk FOREIGN KEY (user_id) REFERENCES core.app_user (id) ON DELETE RESTRICT ON UPDATE RESTRICT",
]


def upgrade() -> None:
    for statement in STATEMENTS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE core.app_review")
