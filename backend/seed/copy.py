from __future__ import annotations
# ruff: noqa: I001

from collections import defaultdict
from datetime import UTC, date, datetime
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import MetaData, inspect, text, update
from sqlalchemy.engine import Connection

from seed.common import SEED_VERSION, at


SCHEMAS = ("mes", "erp", "fems", "qms", "wms")
MONTH_COLUMNS = {
    ("erp.partner_item_price", "effective_from"),
    ("erp.partner_item_price", "effective_to"),
    ("fems.tariff", "effective_from"),
    ("fems.tariff", "effective_to"),
    ("fems.energy_target", "target_month"),
    ("fems.energy_baseline", "period_from"),
    ("fems.energy_baseline", "period_to"),
}


def copy_template(
    connection: Connection,
    source_workspace_id: int,
    source_generation_id: int,
    target_date: date,
    guest_session_key: str,
) -> tuple[int, int, dict[str, int], float]:
    """템플릿을 guest 세대로 복사한다. 업무 행은 모두 INSERT ... SELECT로 이동한다."""
    metadata = MetaData()
    for schema in ("core", *SCHEMAS):
        metadata.reflect(connection, schema=schema)
    workspace = metadata.tables["core.workspace"]
    generation = metadata.tables["core.data_generation"]
    source_date = connection.execute(
        text(
            "SELECT seed_date FROM core.data_generation WHERE workspace_id=:w AND id=:g"
        ),
        {"w": source_workspace_id, "g": source_generation_id},
    ).scalar_one()
    started = perf_counter()
    target_workspace_id = connection.execute(
        workspace.insert()
        .values(
            owner_user_id=None,
            active_generation_id=None,
            config_version=1,
            energy_input_revision=1,
            created_at=at(target_date, -91, 9),
            workspace_kind="GUEST",
            guest_session_key=guest_session_key,
            expires_at=at(target_date, 1),
            guest_actor_key=uuid5(NAMESPACE_URL, f"factory-studio:{guest_session_key}"),
        )
        .returning(workspace.c.id)
    ).scalar_one()
    target_generation_id = connection.execute(
        generation.insert()
        .values(
            workspace_id=target_workspace_id,
            seed_version=SEED_VERSION,
            seed_date=target_date,
            activated_at=at(target_date, 0),
            retired_at=None,
            purged_at=None,
            created_at=at(target_date, -91, 9),
            status="active",
        )
        .returning(generation.c.id)
    ).scalar_one()
    connection.execute(
        update(workspace)
        .where(workspace.c.id == target_workspace_id)
        .values(active_generation_id=target_generation_id)
    )
    counts = _copy_business_rows(
        connection,
        metadata,
        source_workspace_id,
        source_generation_id,
        target_workspace_id,
        target_generation_id,
        source_date,
        target_date,
        copy_modules=True,
    )
    return target_workspace_id, target_generation_id, counts, perf_counter() - started


def copy_template_generation(
    connection: Connection,
    source_workspace_id: int,
    source_generation_id: int,
    target_workspace_id: int,
    target_date: date,
) -> tuple[int, dict[str, int], float]:
    """기존 공간에 새 세대를 복사한다. 공간 설정은 유지한다."""
    metadata = MetaData()
    for schema in ("core", *SCHEMAS):
        metadata.reflect(connection, schema=schema)
    workspace = metadata.tables["core.workspace"]
    generation = metadata.tables["core.data_generation"]
    source_date = connection.execute(
        text(
            "SELECT seed_date FROM core.data_generation WHERE workspace_id=:w AND id=:g"
        ),
        {"w": source_workspace_id, "g": source_generation_id},
    ).scalar_one()
    started = perf_counter()
    current_generation_id = connection.execute(
        text("SELECT active_generation_id FROM core.workspace WHERE id=:w FOR UPDATE"),
        {"w": target_workspace_id},
    ).scalar_one()
    target_generation_id = connection.execute(
        generation.insert()
        .values(
            workspace_id=target_workspace_id,
            seed_version=SEED_VERSION,
            seed_date=target_date,
            activated_at=None,
            retired_at=None,
            purged_at=None,
            created_at=at(target_date, 0),
            status="preparing",
        )
        .returning(generation.c.id)
    ).scalar_one()
    counts = _copy_business_rows(
        connection,
        metadata,
        source_workspace_id,
        source_generation_id,
        target_workspace_id,
        target_generation_id,
        source_date,
        target_date,
        copy_modules=False,
    )
    now = datetime.now(UTC)
    connection.execute(
        update(generation)
        .where(generation.c.id == current_generation_id)
        .values(status="retired", retired_at=now)
    )
    connection.execute(
        update(generation)
        .where(generation.c.id == target_generation_id)
        .values(status="active", activated_at=now)
    )
    connection.execute(
        update(workspace)
        .where(workspace.c.id == target_workspace_id)
        .values(active_generation_id=target_generation_id)
    )
    return target_generation_id, counts, perf_counter() - started


def _copy_business_rows(
    connection: Connection,
    metadata: MetaData,
    source_workspace_id: int,
    source_generation_id: int,
    target_workspace_id: int,
    target_generation_id: int,
    source_date: date,
    target_date: date,
    *,
    copy_modules: bool,
) -> dict[str, int]:
    params = {
        "source_workspace": source_workspace_id,
        "source_generation": source_generation_id,
        "target_workspace": target_workspace_id,
        "target_generation": target_generation_id,
        "source_date": source_date,
        "target_date": target_date,
    }
    module_rows = 0
    if copy_modules:
        module_rows = connection.execute(
            text(
                """
                INSERT INTO core.workspace_module (workspace_id,module_key,enabled,updated_at)
                SELECT :target_workspace,module_key,enabled,
                       updated_at + (:target_date - :source_date) * interval '1 day'
                FROM core.workspace_module WHERE workspace_id=:source_workspace
                """
            ),
            params,
        ).rowcount
    seeded = _seeded_tables(connection, source_workspace_id, source_generation_id)
    inspector = inspect(connection)
    foreign_keys = _foreign_keys(inspector, seeded)
    parents = {
        target
        for fks in foreign_keys.values()
        for _, target in fks.values()
        if target in seeded
    }
    for table_name in sorted(parents):
        schema, table = table_name.split(".")
        map_name = _map_name(table_name)
        connection.execute(
            text(
                f'CREATE TEMP TABLE "{map_name}" (old_id bigint PRIMARY KEY, new_id bigint UNIQUE NOT NULL) ON COMMIT DROP'
            )
        )
        connection.execute(
            text(
                f'INSERT INTO "{map_name}" '
                f"SELECT id, nextval(pg_get_serial_sequence('{table_name}','id')) "
                f'FROM "{schema}"."{table}" WHERE workspace_id=:source_workspace AND generation_id=:source_generation ORDER BY id'
            ),
            params,
        )
    counts: dict[str, int] = (
        {"core.workspace_module": module_rows} if copy_modules else {}
    )
    for table_name in _table_order(seeded, foreign_keys):
        result = connection.execute(
            text(
                _insert_select_sql(
                    table_name,
                    metadata.tables[table_name],
                    foreign_keys.get(table_name, {}),
                    table_name in parents,
                )
            ),
            params,
        )
        counts[table_name] = result.rowcount
    return counts


def _seeded_tables(
    connection: Connection, workspace_id: int, generation_id: int
) -> set[str]:
    tables: set[str] = set()
    for schema in SCHEMAS:
        names = inspect(connection).get_table_names(schema=schema)
        for table in names:
            count = connection.execute(
                text(
                    f'SELECT count(*) FROM "{schema}"."{table}" WHERE workspace_id=:w AND generation_id=:g'
                ),
                {"w": workspace_id, "g": generation_id},
            ).scalar_one()
            if count:
                tables.add(f"{schema}.{table}")
    return tables


def _foreign_keys(
    inspector: Any, seeded: set[str]
) -> dict[str, dict[str, tuple[str, str]]]:
    result: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for table_name in seeded:
        schema, table = table_name.split(".")
        for fk in inspector.get_foreign_keys(table, schema=schema):
            target = f"{fk['referred_schema']}.{fk['referred_table']}"
            for local, remote in zip(
                fk["constrained_columns"], fk["referred_columns"], strict=True
            ):
                if (
                    local not in {"workspace_id", "generation_id"}
                    and remote == "id"
                    and target in seeded
                ):
                    result[table_name][local] = (remote, target)
        for column in inspector.get_columns(table, schema=schema):
            local = column["name"]
            if local in result[table_name] or not local.endswith("_id"):
                continue
            target = f"{schema}.{local[:-3]}"
            if target in seeded:
                result[table_name][local] = ("id", target)
    return result


def _table_order(
    seeded: set[str], foreign_keys: dict[str, dict[str, tuple[str, str]]]
) -> list[str]:
    dependencies = {
        table: {
            target
            for _, target in foreign_keys.get(table, {}).values()
            if target != table
        }
        for table in seeded
    }
    ordered: list[str] = []
    remaining = set(seeded)
    while remaining:
        ready = sorted(
            table for table in remaining if not (dependencies[table] & remaining)
        )
        if not ready:
            raise RuntimeError(f"seed table FK cycle: {sorted(remaining)}")
        ordered.extend(ready)
        remaining.difference_update(ready)
    return ordered


def _map_name(table_name: str) -> str:
    return "map_" + table_name.replace(".", "_")


def _insert_select_sql(
    table_name: str, table: Any, fks: dict[str, tuple[str, str]], mapped: bool
) -> str:
    schema, short = table_name.split(".")
    columns = [column.name for column in table.columns if column.name != "id" or mapped]
    select_values: list[str] = []
    joins: list[str] = []
    for column in columns:
        if column == "id":
            select_values.append(f'"{_map_name(table_name)}".new_id')
        elif column == "workspace_id":
            select_values.append(":target_workspace")
        elif column == "generation_id":
            select_values.append(":target_generation")
        elif column in fks:
            target = fks[column][1]
            alias = f"fk_{column}"
            joins.append(
                f'LEFT JOIN "{_map_name(target)}" "{alias}" ON "{alias}".old_id = src."{column}"'
            )
            select_values.append(f'"{alias}".new_id')
        else:
            select_values.append(
                _column_expression(
                    table_name, column, table.c[column].type.__class__.__name__
                )
            )
    if mapped:
        joins.insert(
            0,
            f'JOIN "{_map_name(table_name)}" ON "{_map_name(table_name)}".old_id=src.id',
        )
    override = " OVERRIDING SYSTEM VALUE" if mapped else ""
    quoted_columns = ",".join(f'"{column}"' for column in columns)
    return (
        f'INSERT INTO "{schema}"."{short}" ({quoted_columns}){override} '
        f'SELECT {",".join(select_values)} FROM "{schema}"."{short}" src {" ".join(joins)} '
        "WHERE src.workspace_id=:source_workspace AND src.generation_id=:source_generation ORDER BY src.id"
    )


def _column_expression(table_name: str, column: str, type_name: str) -> str:
    if (
        table_name in {"erp.sales_plan", "mes.production_plan"}
        and column == "target_month"
    ):
        return _month_expression("src.target_month")
    if table_name == "erp.sales_plan" and column == "plan_code":
        return "'SP-' || " + _month_expression("src.target_month")
    if table_name == "mes.production_plan" and column == "plan_code":
        return "'PP-' || " + _month_expression("src.target_month")
    if table_name == "mes.production_plan" and column == "sales_plan_code":
        return "'SP-' || " + _month_expression("src.target_month")
    if table_name == "mes.production_plan_line" and column == "target_week":
        ordinal = "row_number() OVER (PARTITION BY src.production_plan_id,src.item_id ORDER BY src.target_week)"
        source_week = "to_date(src.target_week || '-1','IYYY-\"W\"IW-ID')"
        target_month = f"date_trunc('month', CAST(:target_date AS date) + ((date_part('year',{source_week})-date_part('year',CAST(:source_date AS date)))*12 + date_part('month',{source_week})-date_part('month',CAST(:source_date AS date)))::int * interval '1 month')"
        monday = f"({target_month} + ((8-extract(isodow from {target_month}))::int % 7 + 7*(({ordinal})-1)) * interval '1 day')"
        return f"to_char({monday}, 'IYYY-\"W\"IW')"
    if table_name == "fems.energy_factor" and column == "effective_year":
        ordinal = "dense_rank() OVER (PARTITION BY src.energy_source_id,src.factor_kind ORDER BY src.effective_year)"
        return f"((extract(year from CAST(:target_date AS date))::int - 2 + {ordinal})::text)"
    if table_name == "qms.inspection" and column == "inspection_month":
        # 검사일을 업무일만큼 옮긴 뒤 월을 다시 구한다.
        return "to_char(src.inspected_on + (:target_date - :source_date), 'YYYY-MM')"
    if (table_name, column) in {
        ("qms.inspection", "inspection_no"),
        ("qms.quality_hold", "hold_no"),
    }:
        # QI-/QH-YYYYMMDD-NNN: 번호 속 날짜도 같은 일수만큼 옮긴다.
        return (
            f'left(src."{column}", 3) || to_char(to_date(substr(src."{column}", 4, 8), \'YYYYMMDD\') '
            f"+ (:target_date - :source_date), 'YYYYMMDD') || substr(src.\"{column}\", 12)"
        )
    if (table_name, column) in MONTH_COLUMNS:
        return f'CASE WHEN src."{column}" IS NULL THEN NULL ELSE {_month_expression(f'src."{column}"')} END'
    if type_name in {"TIMESTAMP", "DateTime"}:
        return f"src.\"{column}\" + (:target_date - :source_date) * interval '1 day'"
    if type_name in {"DATE", "Date"}:
        return f'src."{column}" + (:target_date - :source_date)'
    return f'src."{column}"'


def _month_expression(source: str) -> str:
    return (
        "to_char(date_trunc('month', CAST(:target_date AS date)) + "
        f"((date_part('year',({source} || '-01')::date)-date_part('year',CAST(:source_date AS date)))*12 + "
        f"date_part('month',({source} || '-01')::date)-date_part('month',CAST(:source_date AS date)))::int * interval '1 month', 'YYYY-MM')"
    )
