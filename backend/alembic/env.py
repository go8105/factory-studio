"""FS-009: schema.json을 변경하거나 DDL로 자동 변환하지 않는다."""

import os

from sqlalchemy import create_engine, pool

from alembic import context

url = os.environ["DATABASE_URL"]
if context.is_offline_mode():
    context.configure(url=url, literal_binds=True, dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()
else:
    engine = create_engine(url, poolclass=pool.NullPool)
    with engine.connect() as connection:
        if (
            connection.dialect.name != "postgresql"
            or connection.dialect.server_version_info[0] != 18
        ):
            raise RuntimeError("FS-009 requires PostgreSQL 18")
        context.configure(connection=connection, transactional_ddl=True)
        with context.begin_transaction():
            context.run_migrations()
