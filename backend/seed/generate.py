from __future__ import annotations
# ruff: noqa: I001, FURB157, PLC0206

from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_CEILING
from typing import Any

from sqlalchemy import MetaData, Table, inspect, insert, text, update
from sqlalchemy.engine import Connection

from seed.common import (
    SEED_VERSION,
    SEOUL,
    at,
    calendar_date,
    codebook,
    decimal,
    month_mondays,
    month_text,
    round_half_up,
)

Row = dict[str, Any]


SCHEDULE: dict[str, list[tuple[str, str, int, int | None]]] = {
    "E01": [
        ("INJ", "INJ-01", -60, -58),
        ("ASM", "ASM-01", -57, -56),
        ("INS", "INS-01", -55, -55),
    ],
    "E02": [
        ("INJ", "INJ-02", -60, -58),
        ("ASM", "ASM-02", -57, -56),
        ("INS", "INS-02", -55, -55),
    ],
    "E03": [
        ("INJ", "INJ-03", -57, -55),
        ("ASM", "ASM-03", -54, -53),
        ("INS", "INS-01", -52, -52),
    ],
    "E04": [
        ("INJ", "INJ-01", -54, -52),
        ("ASM", "ASM-01", -51, -50),
        ("INS", "INS-02", -49, -49),
    ],
    "E05": [
        ("INJ", "INJ-02", -51, -49),
        ("ASM", "ASM-02", -48, -47),
        ("INS", "INS-01", -46, -46),
    ],
    "E06": [
        ("INJ", "INJ-03", -48, -46),
        ("ASM", "ASM-03", -45, -44),
        ("INS", "INS-02", -43, -43),
    ],
    "E07": [
        ("INJ", "INJ-01", -45, -43),
        ("ASM", "ASM-01", -42, -41),
        ("INS", "INS-01", -40, -40),
    ],
    "E08": [
        ("INJ", "INJ-02", -42, -40),
        ("ASM", "ASM-02", -39, -38),
        ("INS", "INS-02", -37, -37),
    ],
    "E09": [
        ("INJ", "INJ-03", -39, -37),
        ("ASM", "ASM-03", -36, -35),
        ("INS", "INS-01", -34, -34),
    ],
    "E10": [
        ("INJ", "INJ-01", -39, -37),
        ("ASM", "ASM-01", -36, -35),
        ("INS", "INS-02", -34, -34),
    ],
    "E11": [
        ("INJ", "INJ-02", -37, -35),
        ("ASM", "ASM-02", -34, -33),
        ("INS", "INS-01", -32, -32),
    ],
    "E12": [
        ("INJ", "INJ-03", -36, -34),
        ("ASM", "ASM-03", -33, -32),
        ("INS", "INS-02", -31, -31),
    ],
    "W01": [
        ("INJ", "INJ-01", -30, -28),
        ("ASM", "ASM-01", -27, -26),
        ("INS", "INS-01", -25, -25),
    ],
    "W02": [
        ("INJ", "INJ-02", -30, -28),
        ("ASM", "ASM-02", -27, -26),
        ("INS", "INS-02", -25, -25),
    ],
    "W03": [
        ("INJ", "INJ-03", -27, -25),
        ("ASM", "ASM-03", -24, -23),
        ("INS", "INS-01", -22, -22),
    ],
    "W04": [
        ("INJ", "INJ-01", -24, -22),
        ("ASM", "ASM-01", -21, -20),
        ("INS", "INS-02", -19, -19),
    ],
    "W05": [
        ("INJ", "INJ-02", -21, -19),
        ("ASM", "ASM-02", -18, -17),
        ("INS", "INS-01", -16, -16),
    ],
    "W06": [
        ("INJ", "INJ-03", -18, -16),
        ("ASM", "ASM-03", -15, -14),
        ("INS", "INS-02", -13, -13),
    ],
    "W07": [("INJ", "INJ-01", -4, -2)],
    "W08": [("INJ", "INJ-02", -3, -1)],
    "W09": [("INJ", "INJ-03", -9, -7), ("ASM", "ASM-03", -6, -5)],
    "W10": [("INJ", "INJ-01", -8, -6), ("ASM", "ASM-02", -3, -2)],
    "W11": [("INJ", "INJ-02", -7, -5), ("ASM", "ASM-03", -1, None)],
    "W12": [("INJ", "INJ-03", -5, -3), ("ASM", "ASM-01", -1, None)],
}

ITEM_FOR_LOT = {
    **{
        f"E{i:02d}": ("FG-C100", "FG-C200", "FG-T300")[(i - 1) % 3]
        for i in range(1, 13)
    },
    **{
        f"W{i:02d}": ("FG-C100", "FG-C200", "FG-T300")[(i - 1) % 3]
        for i in range(1, 13)
    },
    "R01": "FG-C100",
    "R02": "FG-C200",
    "N01": "FG-T300",
    "N02": "FG-C100",
    "N03": "FG-C200",
    "X01": "FG-T300",
}

LOT_QTY = {"FG-C100": 2000, "FG-C200": 2000, "FG-T300": 1000}
RESULT_CHAIN = {
    "FG-C100": [(2000, 1970, 30), (1970, 1950, 20), (1950, 1940, 10)],
    "FG-C200": [(2000, 1960, 40), (1960, 1931, 29), (1931, 1921, 10)],
    "FG-T300": [(1000, 990, 10), (990, 985, 5), (985, 982, 3)],
}
DEFECT_REASON = {
    "INJ": "SHORT_SHOT 미충전",
    "ASM": "PIN_MISALIGN 핀 정렬 불량",
    "INS": "CONTACT_FAIL 접촉 불량",
}


class SeedWriter:
    def __init__(
        self,
        connection: Connection,
        workspace_id: int,
        generation_id: int,
        seed_date: date,
    ):
        self.connection = connection
        self.workspace_id = workspace_id
        self.generation_id = generation_id
        self.seed_date = seed_date
        self.metadata = MetaData()
        for schema in ("core", "mes", "erp", "fems"):
            self.metadata.reflect(connection, schema=schema)
        self.counts: dict[str, int] = defaultdict(int)

    def table(self, name: str) -> Table:
        return self.metadata.tables[name]

    def add(
        self,
        name: str,
        rows: Iterable[Row],
        key: str | tuple[str, ...] | None = None,
    ) -> dict[Any, int]:
        table = self.table(name)
        materialized = []
        for source in rows:
            row = dict(source)
            if "workspace_id" in table.c and "workspace_id" not in row:
                row["workspace_id"] = self.workspace_id
            if "generation_id" in table.c and "generation_id" not in row:
                row["generation_id"] = self.generation_id
            if "created_at" in table.c and "created_at" not in row:
                row["created_at"] = at(self.seed_date, -91, 9)
            materialized.append(row)
        if not materialized:
            return {}
        self.counts[name] += len(materialized)
        if key is None:
            self.connection.execute(insert(table), materialized)
            return {}
        keys = (key,) if isinstance(key, str) else key
        result = self.connection.execute(
            insert(table).returning(table.c.id, *(table.c[column] for column in keys)),
            materialized,
        )
        mapped: dict[Any, int] = {}
        for values in result:
            natural = values[1] if len(keys) == 1 else tuple(values[1:])
            mapped[natural] = values[0]
        return mapped


def create_template(
    connection: Connection, seed_date: date
) -> tuple[int, int, dict[str, int]]:
    """빈 DB에 검증 가능한 불변 템플릿 세대 1개를 만든다."""
    core = MetaData()
    core.reflect(connection, schema="core")
    workspace = core.tables["core.workspace"]
    generation = core.tables["core.data_generation"]
    workspace_id = connection.execute(
        insert(workspace)
        .values(
            owner_user_id=None,
            active_generation_id=None,
            config_version=1,
            energy_input_revision=1,
            created_at=at(seed_date, -91, 9),
            workspace_kind="TEMPLATE",
            guest_session_key=None,
            expires_at=None,
            guest_actor_key=None,
        )
        .returning(workspace.c.id)
    ).scalar_one()
    generation_id = connection.execute(
        insert(generation)
        .values(
            workspace_id=workspace_id,
            seed_version=SEED_VERSION,
            seed_date=seed_date,
            activated_at=at(seed_date, 0),
            retired_at=None,
            purged_at=None,
            created_at=at(seed_date, -91, 9),
            status="active",
        )
        .returning(generation.c.id)
    ).scalar_one()
    connection.execute(
        update(workspace)
        .where(workspace.c.id == workspace_id)
        .values(active_generation_id=generation_id)
    )
    writer = SeedWriter(connection, workspace_id, generation_id, seed_date)
    writer.counts["core.workspace"] = 1
    writer.counts["core.data_generation"] = 1
    writer.add(
        "core.workspace_module",
        [
            {
                "workspace_id": workspace_id,
                "module_key": module,
                "enabled": True,
                "updated_at": at(seed_date, 0),
            }
            for module in ("core", "mes", "erp", "fems")
        ],
    )
    _masters(writer)
    context = _plans_and_mes(writer)
    _erp(writer, context)
    _fems(writer, context)
    normalize_created_at(connection, workspace_id, generation_id, seed_date)
    return workspace_id, generation_id, dict(writer.counts)


def normalize_created_at(
    connection: Connection, workspace_id: int, generation_id: int, seed_date: date
) -> None:
    """업무 시각 우선순위와 부모-자식 순서에 맞춰 created_at을 확정한다."""
    params = {"w": workspace_id, "g": generation_id, "master": at(seed_date, -91, 9)}
    timestamp_priority = (
        "occurred_at",
        "started_at",
        "observed_at",
        "period_start",
        "issued_at",
        "received_at",
        "shipped_at",
        "recognized_at",
        "changed_at",
        "applied_at",
        "released_at",
        "published_at",
        "confirmed_at",
        "completed_at",
    )
    date_priority = (
        "quoted_on",
        "ordered_on",
        "invoice_date",
        "received_on",
        "paid_on",
        "issued_on",
    )
    inspector = inspect(connection)
    tables: list[tuple[str, str, set[str]]] = []
    for schema in ("mes", "erp", "fems"):
        for table in inspector.get_table_names(schema=schema):
            columns = {
                column["name"] for column in inspector.get_columns(table, schema=schema)
            }
            if "created_at" not in columns:
                continue
            tables.append((schema, table, columns))
            candidates = [f'"{name}"' for name in timestamp_priority if name in columns]
            candidates += [
                f"(\"{name}\" + time '09:00') AT TIME ZONE 'Asia/Seoul'"
                for name in date_priority
                if name in columns
            ]
            expression = (
                f"coalesce({','.join(candidates)}, :master)"
                if candidates
                else ":master"
            )
            connection.execute(
                text(
                    f'UPDATE "{schema}"."{table}" SET created_at={expression} '
                    "WHERE workspace_id=:w AND generation_id=:g"
                ),
                params,
            )
    for _ in range(len(tables)):
        changed = 0
        for schema, table, _ in tables:
            for fk in inspector.get_foreign_keys(table, schema=schema):
                parent_schema = fk["referred_schema"]
                parent_table = fk["referred_table"]
                if parent_schema not in {"mes", "erp", "fems"}:
                    continue
                join = " AND ".join(
                    f'c."{local}"=p."{remote}"'
                    for local, remote in zip(
                        fk["constrained_columns"], fk["referred_columns"], strict=True
                    )
                )
                result = connection.execute(
                    text(
                        f'UPDATE "{schema}"."{table}" c SET created_at=p.created_at '
                        f'FROM "{parent_schema}"."{parent_table}" p '
                        f"WHERE {join} AND c.workspace_id=:w AND c.generation_id=:g "
                        "AND c.created_at<p.created_at"
                    ),
                    params,
                )
                changed += result.rowcount
        if changed == 0:
            break


def _masters(writer: SeedWriter) -> None:
    book = codebook()
    site = book["site"]
    for schema in ("mes", "fems"):
        writer.add(
            f"{schema}.site",
            [
                {
                    "site_code": site["code"],
                    "name": site["name"],
                    "timezone": "Asia/Seoul",
                }
            ],
            "site_code",
        )
    for schema in ("mes", "fems"):
        site_id = _id(writer, f"{schema}.site", "site_code", "S01")
        allowed = [
            row
            for row in book["locations"]
            if schema == "fems" or not row.get("fems_only")
        ]
        locations = writer.add(
            f"{schema}.location",
            [
                {
                    "site_id": site_id,
                    "parent_location_id": None,
                    "location_code": row["code"],
                    "name": row["name"],
                    "kind": row["kind"],
                }
                for row in allowed
            ],
            "location_code",
        )
        writer.add(
            f"{schema}.equipment",
            [
                {
                    "location_id": locations[row["location"]],
                    "equipment_code": row["code"],
                    "name": row["name"],
                    "equipment_type": row["type"],
                    "is_active": True,
                }
                for row in book["equipment"]
            ],
            "equipment_code",
        )
    for schema in ("mes", "erp"):
        writer.add(
            f"{schema}.item",
            [
                {
                    "item_code": row["code"],
                    "name": row["name"],
                    "base_unit": row["unit"],
                    "item_type": row["type"],
                    "is_active": True,
                    **({"tax_category": row["tax"]} if schema == "erp" else {}),
                }
                for row in book["items"]
            ],
            "item_code",
        )
        item_id = _id(writer, f"{schema}.item", "item_code", "RM-PIN")
        writer.add(
            f"{schema}.item_unit_conversion",
            [
                {
                    "item_id": item_id,
                    "from_unit": "BOX",
                    "to_unit": "EA",
                    "factor": Decimal("10000"),
                }
            ],
        )


def _id(writer: SeedWriter, table_name: str, column: str, value: Any) -> int:
    table = writer.table(table_name)
    return writer.connection.execute(
        table.select()
        .with_only_columns(table.c.id)
        .where(table.c.workspace_id == writer.workspace_id)
        .where(table.c.generation_id == writer.generation_id)
        .where(table.c[column] == value)
    ).scalar_one()


def _plan_months(seed_date: date) -> list[tuple[int, str]]:
    return [(-1, month_text(seed_date, -1)), (0, month_text(seed_date, 0))]


def _plans_and_mes(writer: SeedWriter) -> dict[str, Any]:
    seed_date = writer.seed_date
    book = codebook()
    mes_items = {
        row["code"]: _id(writer, "mes.item", "item_code", row["code"])
        for row in book["items"]
    }
    equipment = {
        row["code"]: _id(writer, "mes.equipment", "equipment_code", row["code"])
        for row in book["equipment"]
    }
    processes = writer.add(
        "mes.process",
        [
            {
                "process_code": row["code"],
                "name": row["name"],
                "process_type": row["type"],
                "is_active": True,
            }
            for row in book["processes"]
        ],
        "process_code",
    )
    writer.add(
        "mes.process_equipment",
        [
            {
                "process_id": processes[row["type"]],
                "equipment_id": equipment[row["code"]],
            }
            for row in book["equipment"]
        ],
    )
    routes: dict[str, int] = {}
    route_rows = []
    for item_code in ("FG-C100", "FG-C200", "FG-T300", "SF-H100"):
        published = item_code != "SF-H100"
        route_rows.append(
            {
                "item_id": mes_items[item_code],
                "route_code": f"RT-{item_code[3:]}",
                "version": 1,
                "published_at": at(seed_date, -60) if published else None,
                "retired_at": None,
                "status": "published" if published else "draft",
            }
        )
    route_map = writer.add("mes.route_version", route_rows, "route_code")
    for item_code in ("FG-C100", "FG-C200", "FG-T300", "SF-H100"):
        routes[item_code] = route_map[f"RT-{item_code[3:]}"]
        steps = ("INJ",) if item_code == "SF-H100" else ("INJ", "ASM", "INS")
        writer.add(
            "mes.route_step",
            [
                {
                    "route_version_id": routes[item_code],
                    "process_id": processes[process],
                    "sequence_no": index,
                }
                for index, process in enumerate(steps, 1)
            ],
        )
    bom_rows = []
    for item_code in ("FG-C100", "FG-C200", "FG-T300", "SF-H100"):
        published = item_code != "SF-H100"
        bom_rows.append(
            {
                "bom_code": f"BOM-{item_code[3:]}",
                "item_id": mes_items[item_code],
                "version_no": 1,
                "status": "published" if published else "draft",
                "published_at": at(seed_date, -60) if published else None,
            }
        )
    bom_map = writer.add("mes.bom_version", bom_rows, "bom_code")
    bom_spec = {
        "FG-C100": [("RM-PBT", "0.012", "KG", "2.0"), ("RM-PIN", "4", "EA", "0.5")],
        "FG-C200": [("RM-PBT", "0.018", "KG", "2.0"), ("RM-PIN", "6", "EA", "0.5")],
        "FG-T300": [("RM-PBT", "0.025", "KG", "2.0"), ("RM-PIN", "8", "EA", "0.5")],
        "SF-H100": [("RM-PBT", "0.010", "KG", "2.0")],
    }
    for item_code, lines in bom_spec.items():
        writer.add(
            "mes.bom_line",
            [
                {
                    "bom_version_id": bom_map[f"BOM-{item_code[3:]}"],
                    "line_no": index,
                    "material_item_id": mes_items[material],
                    "qty_per_unit": Decimal(quantity),
                    "unit": unit,
                    "loss_rate": Decimal(loss),
                }
                for index, (material, quantity, unit, loss) in enumerate(lines, 1)
            ],
        )
    production_plans = writer.add(
        "mes.production_plan",
        [
            {
                "plan_code": f"PP-{target_month}",
                "target_month": target_month,
                "sales_plan_code": f"SP-{target_month}",
                "status": "confirmed",
            }
            for _, target_month in _plan_months(seed_date)
        ],
        "plan_code",
    )
    plan_lines: dict[tuple[int, str, int], int] = {}
    for month_offset, target_month in _plan_months(seed_date):
        weeks = month_mondays(seed_date, month_offset)
        rows = []
        keys = []
        for item_code, quantity in (
            ("FG-C100", 5000),
            ("FG-C200", 5000),
            ("FG-T300", 3000),
        ):
            for week_index, week in enumerate(weeks, 1):
                rows.append(
                    {
                        "production_plan_id": production_plans[f"PP-{target_month}"],
                        "item_id": mes_items[item_code],
                        "target_week": week,
                        "plan_qty": quantity,
                        "unit": "EA",
                    }
                )
                keys.append((month_offset, item_code, week_index))
        table = writer.table("mes.production_plan_line")
        prepared = [
            {
                **row,
                "workspace_id": writer.workspace_id,
                "generation_id": writer.generation_id,
                "created_at": at(seed_date, 0),
            }
            for row in rows
        ]
        result = writer.connection.execute(
            insert(table).returning(table.c.id), prepared
        )
        for key_value, values in zip(keys, result, strict=True):
            plan_lines[key_value] = values[0]
        writer.counts["mes.production_plan_line"] += len(rows)
    order_names = (
        [f"E{i:02d}" for i in range(1, 13)]
        + [f"W{i:02d}" for i in range(1, 13)]
        + ["R01", "R02", "N01", "N02", "N03", "X01"]
    )
    lots = [name for name in order_names if name[0] in "EW" or name.startswith("R")]
    order_rows = []
    for index, name in enumerate(order_names, 1):
        item_code = ITEM_FOR_LOT[name]
        status = (
            "completed"
            if name[0] in "E" or name in {f"W{i:02d}" for i in range(1, 7)}
            else "in_progress"
            if name in {f"W{i:02d}" for i in range(7, 13)}
            else "released"
            if name.startswith(("R", "N"))
            else "cancelled"
        )
        first = SCHEDULE.get(name, [("", "", -2, -2)])[0][2]
        last = SCHEDULE.get(name, [("", "", -1, -1)])[-1][3]
        month_offset = -1 if name.startswith("E") else 0
        occurrence = int(name[1:])
        week_index = min(3, (occurrence - 1) // 6 + 1)
        if name.startswith(("R", "N", "X")):
            week_index = 3
        completion_reason = (
            "all_defective"
            if name == "W06"
            else "normal"
            if status == "completed"
            else None
        )
        order_rows.append(
            {
                "order_no": f"WO-{index:04d}",
                "item_id": mes_items[item_code],
                "route_version_id": routes[item_code],
                "plan_qty": LOT_QTY[item_code],
                "unit": "EA",
                "plan_start_date": calendar_date(seed_date, first),
                "plan_end_date": calendar_date(
                    seed_date, last if last is not None else 0
                ),
                "released_at": at(seed_date, first - 1, 9)
                if status in {"released", "in_progress", "completed"}
                else None,
                "started_at": at(seed_date, first)
                if status in {"in_progress", "completed"}
                else None,
                "completed_at": at(seed_date, last, 23, 30)
                if status == "completed"
                else None,
                "completion_reason": completion_reason,
                "cancel_reason": "계획 변경으로 발행 전 취소"
                if status == "cancelled"
                else None,
                "status": status,
                "order_type": "STOCK",
                "sales_order_line_id": None,
                "production_plan_line_id": plan_lines[
                    (month_offset, item_code, week_index)
                ],
                "bom_version_id": None
                if name == "N03"
                else bom_map[f"BOM-{item_code[3:]}"],
            }
        )
    order_map = writer.add("mes.work_order", order_rows, "order_no")
    lot_rows = []
    for index, name in enumerate(lots, 1):
        order_index = order_names.index(name) + 1
        status = (
            "completed"
            if name[0] == "E" or name in {f"W{i:02d}" for i in range(1, 7)}
            else "in_progress"
            if name.startswith("W")
            else "ready"
        )
        lot_rows.append(
            {
                "lot_no": f"LT-{index:04d}",
                "work_order_id": order_map[f"WO-{order_index:04d}"],
                "route_version_id": routes[ITEM_FOR_LOT[name]],
                "unit": "EA",
                "completion_reason": "all_defective"
                if name == "W06"
                else "normal"
                if status == "completed"
                else None,
                "status": status,
            }
        )
    lot_map = writer.add("mes.lot", lot_rows, "lot_no")
    lot_number = {name: f"LT-{index:04d}" for index, name in enumerate(lots, 1)}
    step_ids = _route_steps(writer, routes, processes)
    executions: dict[tuple[str, str], dict[str, Any]] = {}
    execution_rows = []
    execution_keys = []
    for name, schedule in SCHEDULE.items():
        item_code = ITEM_FOR_LOT[name]
        for process, equipment_code, start_day, end_day in schedule:
            row = {
                "lot_id": lot_map[lot_number[name]],
                "route_version_id": routes[item_code],
                "route_step_id": step_ids[(item_code, process)],
                "equipment_id": equipment[equipment_code],
                "unit": "EA",
                "started_at": at(seed_date, start_day),
                "ended_at": at(seed_date, end_day, 23) if end_day is not None else None,
                "status": "completed" if end_day is not None else "running",
            }
            execution_rows.append(row)
            execution_keys.append((name, process))
    table = writer.table("mes.operation_execution")
    prepared = [
        {
            **row,
            "workspace_id": writer.workspace_id,
            "generation_id": writer.generation_id,
            "created_at": at(seed_date, 0),
        }
        for row in execution_rows
    ]
    result = writer.connection.execute(insert(table).returning(table.c.id), prepared)
    writer.counts["mes.operation_execution"] += len(prepared)
    for key_value, row, result_row in zip(
        execution_keys, execution_rows, result, strict=True
    ):
        executions[key_value] = {**row, "id": result_row[0]}
    result_rows = []
    for (name, process), execution in executions.items():
        if execution["ended_at"] is None:
            continue
        item_code = ITEM_FOR_LOT[name]
        process_index = ("INJ", "ASM", "INS").index(process)
        input_qty, good_qty, defect_qty = RESULT_CHAIN[item_code][process_index]
        if name == "W06" and process == "INS":
            good_qty, defect_qty = 0, input_qty
        reason = (
            "MOLD_DAMAGE 금형 손상에 의한 치수 불량"
            if name == "W06" and process == "INS"
            else DEFECT_REASON[process]
            if defect_qty
            else None
        )
        result_rows.append(
            {
                "execution_id": execution["id"],
                "input_qty": input_qty,
                "output_qty": input_qty,
                "good_qty": good_qty,
                "defect_qty": defect_qty,
                "unit": "EA",
                "defect_reason": reason,
                "confirmed_at": execution["ended_at"] + timedelta(minutes=30),
            }
        )
    writer.add("mes.operation_result", result_rows)
    issue_rows = []
    for (name, process), execution in executions.items():
        if process not in {"INJ", "ASM"}:
            continue
        item_code = ITEM_FOR_LOT[name]
        material = "RM-PBT" if process == "INJ" else "RM-PIN"
        _, quantity, _, loss = bom_spec[item_code][0 if process == "INJ" else 1]
        issued = (
            Decimal(LOT_QTY[item_code])
            * Decimal(quantity)
            * (Decimal("1") + Decimal(loss) / 100)
        )
        issued = (
            issued.quantize(Decimal("0.001"))
            if material == "RM-PBT"
            else issued.quantize(Decimal("1"), rounding=ROUND_CEILING)
        )
        issue_rows.append(
            {
                "execution_id": execution["id"],
                "material_item_id": mes_items[material],
                "material_lot_id": None,
                "bom_version_id": bom_map[f"BOM-{item_code[3:]}"],
                "issued_qty": issued,
                "unit": "KG" if material == "RM-PBT" else "EA",
                "issued_at": execution["started_at"],
            }
        )
    writer.add("mes.material_issue", issue_rows)
    packing_context = _packing(writer, lot_map, lot_number)
    return {
        "mes_items": mes_items,
        "mes_equipment": equipment,
        "processes": processes,
        "routes": routes,
        "lots": lot_map,
        "lot_number": lot_number,
        "executions": executions,
        "packing": packing_context,
        "schedule": SCHEDULE,
    }


def _route_steps(
    writer: SeedWriter, routes: dict[str, int], processes: dict[str, int]
) -> dict[tuple[str, str], int]:
    table = writer.table("mes.route_step")
    result: dict[tuple[str, str], int] = {}
    for item_code, route_id in routes.items():
        rows = writer.connection.execute(
            table.select()
            .where(table.c.workspace_id == writer.workspace_id)
            .where(table.c.generation_id == writer.generation_id)
            .where(table.c.route_version_id == route_id)
        ).mappings()
        by_process = {row["process_id"]: row["id"] for row in rows}
        for process_code, process_id in processes.items():
            if process_id in by_process:
                result[(item_code, process_code)] = by_process[process_id]
    return result


def _packing(
    writer: SeedWriter, lot_map: dict[str, int], lot_number: dict[str, str]
) -> dict[str, int]:
    seed_date = writer.seed_date
    pallet_spec = [
        ("PL-0001", ["E01", "E04"], "shipped", -48),
        ("PL-0002", ["E07", "E10"], "received", -33),
        ("PL-0003", ["E02", "E05"], "shipped", -45),
        ("PL-0004", ["E08", "E11"], "shipped", -31),
        ("PL-0005", ["E03", "E06"], "shipped", -42),
        ("PL-0006", ["E09", "E12"], "received", -30),
    ]
    pallets = writer.add(
        "mes.packing_unit",
        [
            {
                "packing_no": number,
                "packing_kind": "PALLET",
                "parent_packing_unit_id": None,
                "status": status,
            }
            for number, _, status, _ in pallet_spec
        ],
        "packing_no",
    )
    box_lots = [f"E{i:02d}" for i in range(1, 13)] + ["W01", "W02", "W03"]
    pallet_for_lot = {lot: number for number, lots, _, _ in pallet_spec for lot in lots}
    box_rows = []
    member_rows: list[tuple[str, str, int]] = []
    box_index = 1
    for lot_name in box_lots:
        item_code = ITEM_FOR_LOT[lot_name]
        final_good = RESULT_CHAIN[item_code][-1][1]
        first = (final_good + 1) // 2
        for part, quantity in enumerate((first, final_good - first), 1):
            box_no = f"BX-{box_index:04d}"
            status = "open" if lot_name == "W03" and part == 2 else "closed"
            box_rows.append(
                {
                    "packing_no": box_no,
                    "packing_kind": "BOX",
                    "parent_packing_unit_id": pallets.get(pallet_for_lot.get(lot_name)),
                    "status": "shipped"
                    if lot_name.startswith("E")
                    and pallets[pallet_for_lot[lot_name]]
                    and next(
                        spec[2]
                        for spec in pallet_spec
                        if spec[0] == pallet_for_lot[lot_name]
                    )
                    == "shipped"
                    else "received"
                    if lot_name.startswith("E")
                    else status,
                }
            )
            member_rows.append((box_no, lot_name, quantity))
            box_index += 1
    boxes = writer.add("mes.packing_unit", box_rows, "packing_no")
    writer.add(
        "mes.packing_member",
        [
            {
                "packing_unit_id": boxes[box_no],
                "lot_id": lot_map[lot_number[lot]],
                "packed_qty": quantity,
            }
            for box_no, lot, quantity in member_rows
        ],
    )
    writer.add(
        "mes.finished_goods_receipt",
        [
            {
                "packing_unit_id": pallets[number],
                "received_at": at(seed_date, day, 15),
                "status": "confirmed",
            }
            for number, _, _, day in pallet_spec
        ],
    )
    return {**pallets, **boxes}


def _erp(writer: SeedWriter, context: dict[str, Any]) -> None:
    seed_date = writer.seed_date
    book = codebook()
    erp_items = {
        row["code"]: _id(writer, "erp.item", "item_code", row["code"])
        for row in book["items"]
    }
    partners = writer.add(
        "erp.partner",
        [
            {
                "partner_code": "C-001",
                "partner_name": "고객 가",
                "partner_kind": "CUSTOMER",
                "is_active": True,
                "payment_term_days": 30,
            },
            {
                "partner_code": "C-002",
                "partner_name": "고객 나",
                "partner_kind": "CUSTOMER",
                "is_active": True,
                "payment_term_days": 60,
            },
            {
                "partner_code": "C-003",
                "partner_name": "고객 다",
                "partner_kind": "CUSTOMER",
                "is_active": True,
                "payment_term_days": None,
            },
            {
                "partner_code": "V-001",
                "partner_name": "공급사 라",
                "partner_kind": "SUPPLIER",
                "is_active": True,
                "payment_term_days": 30,
            },
        ],
        "partner_code",
    )
    price_spec = [
        ("C-001", "FG-C100", 820, -12, -3),
        ("C-001", "FG-C100", 850, -2, None),
        ("C-001", "FG-C200", 1180, -12, None),
        ("C-002", "FG-C100", 870, -12, None),
        ("C-002", "FG-T300", 2400, -12, None),
        ("C-003", "FG-C200", 1200, -12, None),
        ("C-003", "FG-T300", 2450, -12, None),
    ]
    writer.add(
        "erp.partner_item_price",
        [
            {
                "partner_id": partners[partner],
                "item_id": erp_items[item],
                "price_kind": "SALE",
                "unit_price": price,
                "currency": "KRW",
                "effective_from": month_text(seed_date, start),
                "effective_to": month_text(seed_date, end) if end is not None else None,
                "is_active": end is None,
            }
            for partner, item, price, start, end in price_spec
        ],
    )
    accounts_spec = [
        ("AR", "외상매출금"),
        ("PRODUCT_SALES", "제품매출"),
        ("VAT_PAYABLE", "부가세예수금"),
        ("BANK", "보통예금"),
        ("RAW_MATERIAL", "원재료"),
        ("VAT_RECEIVABLE", "부가세대급금"),
        ("AP", "외상매입금"),
    ]
    accounts = writer.add(
        "erp.account",
        [{"account_code": code, "account_name": name} for code, name in accounts_spec],
        "account_code",
    )
    posting_spec = [
        ("SALE", 1, "DEBIT", "AR", "TOTAL"),
        ("SALE", 2, "CREDIT", "PRODUCT_SALES", "SUPPLY"),
        ("SALE", 3, "CREDIT", "VAT_PAYABLE", "TAX"),
        ("RECEIPT", 1, "DEBIT", "BANK", "APPLY"),
        ("RECEIPT", 2, "CREDIT", "AR", "APPLY"),
        ("PURCHASE", 1, "DEBIT", "RAW_MATERIAL", "SUPPLY"),
        ("PURCHASE", 2, "DEBIT", "VAT_RECEIVABLE", "TAX"),
        ("PURCHASE", 3, "CREDIT", "AP", "TOTAL"),
        ("PAYMENT", 1, "DEBIT", "AP", "APPLY"),
        ("PAYMENT", 2, "CREDIT", "BANK", "APPLY"),
    ]
    writer.add(
        "erp.posting_rule",
        [
            {
                "transaction_kind": kind,
                "line_no": line,
                "entry_side": side,
                "account_id": accounts[account],
                "account_code": account,
                "amount_basis": basis,
            }
            for kind, line, side, account, basis in posting_spec
        ],
    )
    sales_plans = writer.add(
        "erp.sales_plan",
        [
            {
                "plan_code": f"SP-{target_month}",
                "target_month": target_month,
                "status": "confirmed",
                "confirmed_at": at(seed_date, -30 if offset == -1 else 0),
            }
            for offset, target_month in _plan_months(seed_date)
        ],
        "plan_code",
    )
    writer.add(
        "erp.sales_plan_line",
        [
            {
                "sales_plan_id": sales_plans[f"SP-{target_month}"],
                "item_id": erp_items[item],
                "plan_qty": quantity,
                "unit": "EA",
            }
            for _, target_month in _plan_months(seed_date)
            for item, quantity in (
                ("FG-C100", 15000),
                ("FG-C200", 15000),
                ("FG-T300", 9000),
            )
        ],
    )
    shipment_days = [-45, -40, -35, -25]
    order_partner = [
        "C-001",
        "C-003",
        "C-002",
        "C-001",
        "C-002",
        "C-003",
        "C-002",
        "C-001",
        "C-003",
        "C-001",
    ]
    order_dates = [day - 10 for day in shipment_days] + [-12, -10, -8, -6, -4, -3]
    order_lines_spec: list[list[tuple[str, int, int]]] = [
        [("FG-C100", 3880, 850)],
        [("FG-C200", 3842, 1200)],
        [("FG-T300", 1964, 2400)],
        [("FG-C200", 3842, 1180)],
        [("FG-C100", 3940, 870), ("FG-T300", 1964, 2400), ("FG-C100", 3000, 870)],
        [("FG-C200", 3842, 1200), ("FG-T300", 982, 2450), ("FG-C200", 2000, 1200)],
        [("FG-C100", 2000, 870), ("FG-T300", 2000, 2400)],
        [("FG-C100", 2000, 850), ("FG-C200", 2000, 1180)],
        [("FG-C200", 2000, 1200), ("FG-T300", 2000, 2450)],
        [("FG-C100", 2000, 850), ("FG-C200", 2000, 1180)],
    ]
    quote_spec = [
        ("Q-0001", 1, "C-001", order_dates[0] - 7, "accepted", order_lines_spec[0]),
        ("Q-0002", 1, "C-002", order_dates[6] - 14, "sent", order_lines_spec[6]),
        ("Q-0002", 2, "C-002", order_dates[6] - 7, "accepted", order_lines_spec[6]),
        ("Q-0003", 1, "C-003", -18, "rejected", [("FG-C200", 2000, 1200)]),
        (
            "Q-0004",
            1,
            "C-001",
            -5,
            "draft",
            [("FG-C100", 2000, 850), ("FG-C200", 2000, 1180)],
        ),
    ]
    quote_rows = [
        {
            "quote_no": number,
            "revision_no": revision,
            "partner_id": partners[partner],
            "quoted_on": calendar_date(seed_date, day),
            "valid_until": calendar_date(seed_date, day + 30),
            "status": status,
            "remark": None,
        }
        for number, revision, partner, day, status, _ in quote_spec
    ]
    quote_map = writer.add("erp.quotation", quote_rows, ("quote_no", "revision_no"))
    quote_line_rows = []
    history_rows = []
    history_sequences = {
        "accepted": ["draft", "confirmed", "sent", "accepted"],
        "sent": ["draft", "confirmed", "sent"],
        "rejected": ["draft", "confirmed", "sent", "rejected"],
        "draft": ["draft"],
    }
    for number, revision, _, day, status, lines in quote_spec:
        quote_id = quote_map[(number, revision)]
        for line_no, (item, quantity, price) in enumerate(lines, 1):
            quote_line_rows.append(
                {
                    "quotation_id": quote_id,
                    "line_no": line_no,
                    "item_id": erp_items[item],
                    "quote_qty": quantity,
                    "unit": "EA",
                    "unit_price": price,
                    "discount_rate": 0,
                }
            )
        for sequence, state in enumerate(history_sequences[status]):
            history_rows.append(
                {
                    "quotation_id": quote_id,
                    "status": state,
                    "changed_at": at(seed_date, day + sequence, 9),
                    "reason": "조건 불일치" if state == "rejected" else None,
                }
            )
    writer.add("erp.quotation_line", quote_line_rows)
    writer.add("erp.quotation_status_history", history_rows)
    quotation_for_order = {1: quote_map[("Q-0001", 1)], 7: quote_map[("Q-0002", 2)]}
    orders = writer.add(
        "erp.sales_order",
        [
            {
                "order_no": f"SO-{index:04d}",
                "partner_id": partners[order_partner[index - 1]],
                "ordered_on": calendar_date(seed_date, order_dates[index - 1]),
                "due_on": calendar_date(seed_date, shipment_days[index - 1] - 3)
                if index <= 4
                else calendar_date(seed_date, order_dates[index - 1] + 14),
                "status": "closed"
                if index <= 4
                else "shipping"
                if index <= 6
                else "open",
                "quotation_id": quotation_for_order.get(index),
            }
            for index in range(1, 11)
        ],
        "order_no",
    )
    order_line_map: dict[tuple[int, int], int] = {}
    table = writer.table("erp.sales_order_line")
    for order_index, lines in enumerate(order_lines_spec, 1):
        rows = [
            {
                "workspace_id": writer.workspace_id,
                "generation_id": writer.generation_id,
                "sales_order_id": orders[f"SO-{order_index:04d}"],
                "line_no": line_no,
                "item_id": erp_items[item],
                "order_qty": quantity,
                "unit": "EA",
                "unit_price": price,
                "created_at": at(seed_date, 0),
            }
            for line_no, (item, quantity, price) in enumerate(lines, 1)
        ]
        result = writer.connection.execute(
            insert(table).returning(table.c.id, table.c.line_no), rows
        )
        writer.counts["erp.sales_order_line"] += len(rows)
        for row in result:
            order_line_map[(order_index, row.line_no)] = row.id
    shipment_order_spec = [
        (1, 1, 3880, "shipped"),
        (2, 1, 3842, "shipped"),
        (3, 1, 1964, "shipped"),
        (4, 1, 3842, "shipped"),
        (5, 1, 3880, "open"),
        (5, 2, 1964, "open"),
        (6, 1, 3842, "open"),
        (6, 2, 982, "open"),
    ]
    shipment_orders = writer.add(
        "erp.shipment_order",
        [
            {
                "ship_order_no": f"SH-O-{index:04d}",
                "sales_order_id": orders[f"SO-{order_index:04d}"],
                "ordered_on": calendar_date(seed_date, shipment_days[index - 1] - 2)
                if index <= 4
                else calendar_date(seed_date, order_dates[order_index - 1] + 1),
                "status": status,
                "cancel_reason": None,
            }
            for index, (order_index, _, _, status) in enumerate(shipment_order_spec, 1)
        ],
        "ship_order_no",
    )
    shipment_order_lines: dict[int, int] = {}
    table = writer.table("erp.shipment_order_line")
    rows = []
    for index, (order_index, line_no, quantity, _) in enumerate(shipment_order_spec, 1):
        rows.append(
            {
                "workspace_id": writer.workspace_id,
                "generation_id": writer.generation_id,
                "shipment_order_id": shipment_orders[f"SH-O-{index:04d}"],
                "sales_order_line_id": order_line_map[(order_index, line_no)],
                "order_qty": quantity,
                "created_at": at(seed_date, 0),
                "sales_order_id": orders[f"SO-{order_index:04d}"],
            }
        )
    result = writer.connection.execute(insert(table).returning(table.c.id), rows)
    writer.counts["erp.shipment_order_line"] += len(rows)
    for index, row in enumerate(result, 1):
        shipment_order_lines[index] = row.id
    shipments = writer.add(
        "erp.shipment",
        [
            {
                "shipment_no": f"SH-{index:04d}",
                "shipment_order_id": shipment_orders[f"SH-O-{index:04d}"],
                "shipped_at": at(seed_date, shipment_days[index - 1], 10),
                "status": "confirmed",
            }
            for index in range(1, 5)
        ],
        "shipment_no",
    )
    shipped_items = ["FG-C100", "FG-C200", "FG-T300", "FG-C200"]
    packing_numbers = ["PL-0001", "PL-0003", "PL-0005", "PL-0004"]
    shipped_quantities = [3880, 3842, 1964, 3842]
    writer.add(
        "erp.shipment_line",
        [
            {
                "shipment_id": shipments[f"SH-{index:04d}"],
                "shipment_order_line_id": shipment_order_lines[index],
                "packing_no": packing_numbers[index - 1],
                "shipped_qty": shipped_quantities[index - 1],
                "shipment_order_id": shipment_orders[f"SH-O-{index:04d}"],
                "item_id": erp_items[shipped_items[index - 1]],
                "shipped_uom": "EA",
            }
            for index in range(1, 5)
        ],
    )
    amount_spec = [
        (3298000, 329800, 3627800),
        (4610400, 461040, 5071440),
        (4713600, 0, 4713600),
        (4533560, 453356, 4986916),
    ]
    sales_records = writer.add(
        "erp.sales_record",
        [
            {
                "shipment_id": shipments[f"SH-{index:04d}"],
                "partner_id": partners[order_partner[index - 1]],
                "supply_amount": supply,
                "tax_amount": tax,
                "total_amount": total,
                "recognized_at": at(seed_date, shipment_days[index - 1], 10),
                "currency": "KRW",
                "cancelled_at": None,
                "cancel_reason": None,
            }
            for index, (supply, tax, total) in enumerate(amount_spec, 1)
        ],
        "shipment_id",
    )
    receivables = writer.add(
        "erp.receivable",
        [
            {
                "sales_record_id": sales_records[shipments[f"SH-{index:04d}"]],
                "partner_id": partners[order_partner[index - 1]],
                "amount": amount_spec[index - 1][2],
                "currency": "KRW",
                "due_date": None
                if index == 2
                else calendar_date(seed_date, (-15, 0, 25, 5)[index - 1]),
            }
            for index in range(1, 5)
        ],
        "sales_record_id",
    )
    receipt_spec = [
        ("RC-0001", "C-001", -10, 2000000, "confirmed"),
        ("RC-0002", "C-002", -20, 4813600, "confirmed"),
        ("RC-0003", "C-001", -2, 1827800, "draft"),
    ]
    receipts = writer.add(
        "erp.receipt",
        [
            {
                "receipt_no": number,
                "partner_id": partners[partner],
                "received_on": calendar_date(seed_date, day),
                "amount": amount,
                "currency": "KRW",
                "status": status,
                "confirmed_at": at(seed_date, day, 10)
                if status == "confirmed"
                else None,
            }
            for number, partner, day, amount, status in receipt_spec
        ],
        "receipt_no",
    )
    writer.add(
        "erp.receipt_apply",
        [
            {
                "receipt_id": receipts["RC-0001"],
                "receivable_id": receivables[sales_records[shipments["SH-0001"]]],
                "partner_id": partners["C-001"],
                "currency": "KRW",
                "amount": 1800000,
                "apply_key": "SEED:RA-0001",
                "applied_at": at(seed_date, -10, 10),
            },
            {
                "receipt_id": receipts["RC-0001"],
                "receivable_id": receivables[sales_records[shipments["SH-0004"]]],
                "partner_id": partners["C-001"],
                "currency": "KRW",
                "amount": 200000,
                "apply_key": "SEED:RA-0002",
                "applied_at": at(seed_date, -10, 10),
            },
            {
                "receipt_id": receipts["RC-0002"],
                "receivable_id": receivables[sales_records[shipments["SH-0003"]]],
                "partner_id": partners["C-002"],
                "currency": "KRW",
                "amount": 4713600,
                "apply_key": "SEED:RA-0003",
                "applied_at": at(seed_date, -20, 10),
            },
        ],
    )
    writer.add(
        "erp.tax_invoice",
        [
            {
                "sales_record_id": sales_records[shipments["SH-0001"]],
                "partner_id": partners["C-001"],
                "currency": "KRW",
                "status": "issued",
                "approval_no": "SYNTH-TI-0001",
                "issued_on": calendar_date(seed_date, -44),
            },
            {
                "sales_record_id": sales_records[shipments["SH-0002"]],
                "partner_id": partners["C-003"],
                "currency": "KRW",
                "status": "pending",
                "approval_no": None,
                "issued_on": None,
            },
            {
                "sales_record_id": sales_records[shipments["SH-0003"]],
                "partner_id": partners["C-002"],
                "currency": "KRW",
                "status": "issued",
                "approval_no": "SYNTH-TI-0003",
                "issued_on": calendar_date(seed_date, -34),
            },
        ],
    )
    _purchases(writer, partners, erp_items)


def _purchases(
    writer: SeedWriter, partners: dict[str, int], erp_items: dict[str, int]
) -> None:
    seed_date = writer.seed_date
    invoice_spec = [
        (
            -55,
            [("RM-PBT", 300, "KG", 3500), ("RM-PIN", 10, "BOX", 180000)],
            "confirmed",
            -25,
        ),
        (
            -40,
            [("RM-PBT", 250, "KG", 3500), ("RM-PIN", 8, "BOX", 180000)],
            "confirmed",
            -10,
        ),
        (
            -25,
            [("RM-PBT", 250, "KG", 3500), ("RM-PIN", 8, "BOX", 180000)],
            "confirmed",
            15,
        ),
        (
            -10,
            [("RM-PBT", 200, "KG", 3500), ("RM-PIN", 6, "BOX", 180000)],
            "confirmed",
            20,
        ),
        (-3, [("RM-PBT", 150, "KG", 3500)], "draft", None),
        (
            -30,
            [("RM-PBT", 100, "KG", 3500), ("RM-PIN", 3, "BOX", 180000)],
            "cancelled",
            0,
        ),
    ]
    totals: list[tuple[int, int, int]] = []
    for _, lines, _, _ in invoice_spec:
        supply = sum(quantity * price for _, quantity, _, price in lines)
        tax = round_half_up(Decimal(supply) * Decimal("0.10"))
        totals.append((supply, tax, supply + tax))
    invoices = writer.add(
        "erp.purchase_invoice",
        [
            {
                "invoice_no": f"PI-{index:04d}",
                "partner_id": partners["V-001"],
                "invoice_date": calendar_date(seed_date, day),
                "due_date": calendar_date(seed_date, due) if due is not None else None,
                "currency": "KRW",
                "supply_amount": totals[index - 1][0],
                "tax_amount": totals[index - 1][1],
                "total_amount": totals[index - 1][2],
                "status": status,
                "confirmed_at": at(seed_date, day, 10) if status != "draft" else None,
                "cancelled_at": at(seed_date, -29, 10) if index == 6 else None,
                "cancel_reason": "수량 오입력" if index == 6 else None,
            }
            for index, (day, _, status, due) in enumerate(invoice_spec, 1)
        ],
        "invoice_no",
    )
    writer.add(
        "erp.purchase_invoice_line",
        [
            {
                "purchase_invoice_id": invoices[f"PI-{invoice_index:04d}"],
                "line_no": line_index,
                "item_id": erp_items[item],
                "quantity": quantity,
                "unit": unit,
                "unit_price": price,
                "currency": "KRW",
                "supply_amount": quantity * price,
                "tax_amount": round_half_up(
                    Decimal(quantity * price) * Decimal("0.10")
                ),
                "total_amount": quantity * price
                + round_half_up(Decimal(quantity * price) * Decimal("0.10")),
            }
            for invoice_index, (_, lines, _, _) in enumerate(invoice_spec, 1)
            for line_index, (item, quantity, unit, price) in enumerate(lines, 1)
        ],
    )
    payable_invoice_indices = [1, 2, 3, 4, 6]
    payables = writer.add(
        "erp.payable",
        [
            {
                "purchase_invoice_id": invoices[f"PI-{index:04d}"],
                "partner_id": partners["V-001"],
                "amount": totals[index - 1][2],
                "currency": "KRW",
                "due_date": calendar_date(seed_date, invoice_spec[index - 1][3]),
            }
            for index in payable_invoice_indices
        ],
        "purchase_invoice_id",
    )
    payment_spec = [
        ("PM-0001", -25, totals[0][2], "confirmed"),
        ("PM-0002", -8, 1500000, "confirmed"),
        ("PM-0003", -1, 2000000, "draft"),
    ]
    payments = writer.add(
        "erp.payment",
        [
            {
                "payment_no": number,
                "partner_id": partners["V-001"],
                "paid_on": calendar_date(seed_date, day),
                "amount": amount,
                "currency": "KRW",
                "status": status,
                "confirmed_at": at(seed_date, day, 10)
                if status == "confirmed"
                else None,
            }
            for number, day, amount, status in payment_spec
        ],
        "payment_no",
    )
    writer.add(
        "erp.payment_apply",
        [
            {
                "payment_id": payments["PM-0001"],
                "payable_id": payables[invoices["PI-0001"]],
                "partner_id": partners["V-001"],
                "currency": "KRW",
                "amount": totals[0][2],
                "apply_key": "SEED:PA-0001",
                "applied_at": at(seed_date, -25, 10),
            },
            {
                "payment_id": payments["PM-0002"],
                "payable_id": payables[invoices["PI-0002"]],
                "partner_id": partners["V-001"],
                "currency": "KRW",
                "amount": 1500000,
                "apply_key": "SEED:PA-0002",
                "applied_at": at(seed_date, -8, 10),
            },
        ],
    )


def _fems(writer: SeedWriter, context: dict[str, Any]) -> None:
    seed_date = writer.seed_date
    site_id = _id(writer, "fems.site", "site_code", "S01")
    location = {
        code: _id(writer, "fems.location", "location_code", code)
        for code in ("L-INJ", "L-ASM", "L-INS", "L-UTL")
    }
    equipment = {
        row["code"]: _id(writer, "fems.equipment", "equipment_code", row["code"])
        for row in codebook()["equipment"]
    }
    sources = writer.add(
        "fems.energy_source",
        [
            {
                "source_code": "ELEC",
                "name": "전력",
                "source_kind": "ELECTRIC",
                "measure_unit": "kWh",
                "is_billable": True,
                "is_active": True,
            },
            {
                "source_code": "GAS",
                "name": "도시가스",
                "source_kind": "FUEL",
                "measure_unit": "Nm3",
                "is_billable": True,
                "is_active": True,
            },
            {
                "source_code": "WATER",
                "name": "용수",
                "source_kind": "UTILITY",
                "measure_unit": "m3",
                "is_billable": True,
                "is_active": True,
            },
        ],
        "source_code",
    )
    meter_specs = [("M-MAIN", "수전 전력량계", "L-UTL", None, None, "site_total")]
    meter_specs += [
        (
            f"M-{code}",
            f"{row['name']} 전력량계",
            row["location"],
            "M-MAIN",
            code,
            "factory",
        )
        for row in codebook()["equipment"]
        for code in [row["code"]]
    ]
    meter_specs += [
        ("M-GAS", "가스 계량기", "L-UTL", None, None, "site_total"),
        ("M-WTR", "용수 계량기", "L-UTL", None, None, "site_total"),
    ]
    meter_rows = [
        {
            "site_id": site_id,
            "location_id": location[location_code],
            "parent_meter_id": None,
            "equipment_id": equipment.get(equipment_code),
            "meter_code": code,
            "name": name,
            "scope_kind": scope,
        }
        for code, name, location_code, _, equipment_code, scope in meter_specs
    ]
    meters = writer.add("fems.meter", meter_rows, "meter_code")
    meter_table = writer.table("fems.meter")
    writer.connection.execute(
        update(meter_table)
        .where(meter_table.c.workspace_id == writer.workspace_id)
        .where(meter_table.c.generation_id == writer.generation_id)
        .where(meter_table.c.meter_code.like("M-%"))
        .where(meter_table.c.meter_code.notin_(["M-MAIN", "M-GAS", "M-WTR"]))
        .values(parent_meter_id=meters["M-MAIN"])
    )
    channel_specs = [("M-MAIN", "CH-MAIN-KWH", "수전 전력", "ELEC", "kWh")]
    channel_specs += [
        (
            f"M-{row['code']}",
            f"CH-{row['code']}-KWH",
            f"{row['name']} 전력",
            "ELEC",
            "kWh",
        )
        for row in codebook()["equipment"]
    ]
    channel_specs += [
        ("M-GAS", "CH-GAS-NM3", "도시가스", "GAS", "Nm3"),
        ("M-WTR", "CH-WTR-M3", "용수", "WATER", "m3"),
    ]
    channels = writer.add(
        "fems.meter_channel",
        [
            {
                "meter_id": meters[meter],
                "energy_source_id": sources[source],
                "channel_code": code,
                "name": name,
                "measurement_kind": "CUMULATIVE",
                "unit": unit,
                "multiplier": Decimal("1"),
                "is_active": True,
            }
            for meter, code, name, source, unit in channel_specs
        ],
        "channel_code",
    )
    readings, hourly = _energy_readings(writer, channels)
    writer.add("fems.energy_reading", readings)
    allocations = _energy_allocations(writer, channels, equipment, hourly)
    writer.add("fems.energy_allocation", allocations)
    years = (seed_date.year - 1, seed_date.year)
    writer.add(
        "fems.energy_factor",
        [
            {
                "energy_source_id": sources[source],
                "factor_kind": kind,
                "effective_year": str(year),
                "factor_value": value,
                "factor_unit": unit,
                "source_note": "합성 예시값 — 공표 계수 아님",
            }
            for source, kind, unit, values in (
                (
                    "ELEC",
                    "PRIMARY",
                    "TOE/kWh",
                    (Decimal("0.000229"), Decimal("0.000229")),
                ),
                (
                    "ELEC",
                    "EMISSION",
                    "tCO2eq/kWh",
                    (Decimal("0.000470"), Decimal("0.000460")),
                ),
                (
                    "GAS",
                    "PRIMARY",
                    "TOE/Nm3",
                    (Decimal("0.001040"), Decimal("0.001040")),
                ),
                (
                    "GAS",
                    "EMISSION",
                    "tCO2eq/Nm3",
                    (Decimal("0.002220"), Decimal("0.002220")),
                ),
            )
            for year, value in zip(years, values, strict=True)
        ],
    )
    writer.add(
        "fems.tariff",
        [
            {
                "energy_source_id": sources["ELEC"],
                "tariff_code": "TR-ELEC-01",
                "name": "산업용(갑) 저압 · 단일요금",
                "contract_type": "산업용",
                "basic_charge": 250000,
                "usage_rate": 120,
                "currency": "KRW",
                "effective_from": month_text(seed_date, -12),
                "effective_to": month_text(seed_date, -1),
            },
            {
                "energy_source_id": sources["ELEC"],
                "tariff_code": "TR-ELEC-02",
                "name": "산업용(갑) 저압 · 단일요금",
                "contract_type": "산업용",
                "basic_charge": 250000,
                "usage_rate": 130,
                "currency": "KRW",
                "effective_from": month_text(seed_date),
                "effective_to": None,
            },
            {
                "energy_source_id": sources["GAS"],
                "tariff_code": "TR-GAS-01",
                "name": "산업용 도시가스",
                "contract_type": "산업용",
                "basic_charge": 30000,
                "usage_rate": 1100,
                "currency": "KRW",
                "effective_from": month_text(seed_date, -12),
                "effective_to": None,
            },
            {
                "energy_source_id": sources["WATER"],
                "tariff_code": "TR-WTR-01",
                "name": "산업용 상수도",
                "contract_type": "산업용",
                "basic_charge": 15000,
                "usage_rate": 1300,
                "currency": "KRW",
                "effective_from": month_text(seed_date, -12),
                "effective_to": None,
            },
        ],
    )
    _energy_targets_and_baselines(
        writer,
        sources,
        site_id,
        equipment,
        channels,
        readings,
        allocations,
        hourly,
    )
    _production_records(writer, context, equipment)


def _is_running(equipment_code: str, instant: datetime, seed_date: date) -> bool:
    for schedule in SCHEDULE.values():
        for _, code, start_day, end_day in schedule:
            if code != equipment_code:
                continue
            start = at(seed_date, start_day)
            end = (
                at(seed_date, end_day + 1) if end_day is not None else at(seed_date, 0)
            )
            if start <= instant < end:
                return True
    return False


def _energy_readings(
    writer: SeedWriter, channels: dict[str, int]
) -> tuple[list[Row], dict[tuple[str, int], list[Decimal]]]:
    loads = {
        "INJ": (Decimal("45.0"), Decimal("3.0")),
        "ASM": (Decimal("12.0"), Decimal("1.5")),
        "INS": (Decimal("6.0"), Decimal("0.8")),
    }
    equipment_codes = [row["code"] for row in codebook()["equipment"]]
    rows: list[Row] = []
    hourly: dict[tuple[str, int], list[Decimal]] = {}
    for day in range(-30, 0):
        for equipment_code in equipment_codes:
            values = []
            kind = equipment_code.split("-")[0]
            active, idle = loads[kind]
            channel_code = f"CH-{equipment_code}-KWH"
            for hour in range(24):
                start = at(writer.seed_date, day, hour)
                value = (
                    active
                    if _is_running(equipment_code, start, writer.seed_date)
                    else idle
                )
                if value == active and hour in (6, 14, 22):
                    value *= Decimal("0.85")
                invalid = equipment_code == "ASM-02" and day == -17 and 10 <= hour < 16
                actual = Decimal("0") if invalid else decimal(value)
                values.append(actual)
                rows.append(
                    {
                        "meter_channel_id": channels[channel_code],
                        "observed_at": start + timedelta(hours=1),
                        "period_start": start,
                        "value": actual,
                        "unit": "kWh",
                        "quality": "invalid" if invalid else "valid",
                        "source_key": f"{channel_code}:H{day * 24 + hour}",
                        "input_revision": 1,
                    }
                )
            hourly[(equipment_code, day)] = values
        for hour in range(24):
            start = at(writer.seed_date, day, hour)
            total = sum(
                (
                    _raw_equipment_value(code, start, writer.seed_date)
                    for code in equipment_codes
                ),
                Decimal("0"),
            )
            total += Decimal("25.0") if 8 <= hour < 20 else Decimal("15.0")
            rows.append(
                {
                    "meter_channel_id": channels["CH-MAIN-KWH"],
                    "observed_at": start + timedelta(hours=1),
                    "period_start": start,
                    "value": decimal(total),
                    "unit": "kWh",
                    "quality": "valid",
                    "source_key": f"CH-MAIN-KWH:H{day * 24 + hour}",
                    "input_revision": 1,
                }
            )
        active_injection = sum(
            _is_running(
                f"INJ-{number:02d}", at(writer.seed_date, day, 12), writer.seed_date
            )
            for number in range(1, 4)
        )
        for code, value, unit in (
            ("CH-GAS-NM3", 45 + 5 * (abs(day) % 3), "Nm3"),
            ("CH-WTR-M3", 8 + 6 * active_injection, "m3"),
        ):
            rows.append(
                {
                    "meter_channel_id": channels[code],
                    "observed_at": at(writer.seed_date, day + 1),
                    "period_start": at(writer.seed_date, day),
                    "value": decimal(value),
                    "unit": unit,
                    "quality": "valid",
                    "source_key": f"{code}:D{day}",
                    "input_revision": 1,
                }
            )
    return rows, hourly


def _raw_equipment_value(code: str, instant: datetime, seed_date: date) -> Decimal:
    active, idle = {
        "INJ": (Decimal("45"), Decimal("3")),
        "ASM": (Decimal("12"), Decimal("1.5")),
        "INS": (Decimal("6"), Decimal("0.8")),
    }[code.split("-")[0]]
    value = active if _is_running(code, instant, seed_date) else idle
    if value == active and instant.astimezone(SEOUL).hour in (6, 14, 22):
        value *= Decimal("0.85")
    return decimal(value)


def _energy_allocations(
    writer: SeedWriter,
    channels: dict[str, int],
    equipment: dict[str, int],
    hourly: dict[tuple[str, int], list[Decimal]],
) -> list[Row]:
    rows: list[Row] = []
    for day in range(-30, 0):
        for code in equipment:
            invalid = code == "ASM-02" and day == -17
            rows.append(
                {
                    "meter_channel_id": channels[f"CH-{code}-KWH"],
                    "equipment_id": equipment[code],
                    "period_start": at(writer.seed_date, day),
                    "period_end": at(writer.seed_date, day + 1),
                    "quantity": sum(hourly[(code, day)]),
                    "unit": "kWh",
                    "method_key": "DIRECT_METER",
                    "method_version": 1,
                    "input_revision": 1,
                    "quality": "estimated" if invalid else "valid",
                    "basis": {
                        "summed_hours": 18 if invalid else 24,
                        "missing_hours": 6 if invalid else 0,
                    },
                }
            )
        active = [
            f"INJ-{number:02d}"
            for number in range(1, 4)
            if _is_running(
                f"INJ-{number:02d}", at(writer.seed_date, day, 12), writer.seed_date
            )
        ]
        for code in active:
            rows.append(
                {
                    "meter_channel_id": channels["CH-WTR-M3"],
                    "equipment_id": equipment[code],
                    "period_start": at(writer.seed_date, day),
                    "period_end": at(writer.seed_date, day + 1),
                    "quantity": Decimal("6"),
                    "unit": "m3",
                    "method_key": "RUNTIME_SHARE",
                    "method_version": 1,
                    "input_revision": 1,
                    "quality": "valid",
                    "basis": {
                        "runtime_hours": 24,
                        "active_equipment_count": len(active),
                        "common_unallocated": 8,
                    },
                }
            )
    return rows


def _energy_targets_and_baselines(
    writer: SeedWriter,
    sources: dict[str, int],
    site_id: int,
    equipment: dict[str, int],
    channels: dict[str, int],
    readings: list[Row],
    allocations: list[Row],
    hourly: dict[tuple[str, int], list[Decimal]],
) -> None:
    site_channels = {
        "ELEC": channels["CH-MAIN-KWH"],
        "GAS": channels["CH-GAS-NM3"],
        "WATER": channels["CH-WTR-M3"],
    }
    site_actual: dict[tuple[str, str], Decimal] = defaultdict(Decimal)
    for row in readings:
        if row["quality"] == "invalid":
            continue
        month = row["period_start"].astimezone(SEOUL).strftime("%Y-%m")
        for source, channel_id in site_channels.items():
            if row["meter_channel_id"] == channel_id:
                site_actual[(source, month)] += row["value"]
    equipment_actual: dict[tuple[int, str], Decimal] = defaultdict(Decimal)
    for row in allocations:
        if row["method_key"] != "DIRECT_METER":
            continue
        month = row["period_start"].astimezone(SEOUL).strftime("%Y-%m")
        equipment_actual[(row["equipment_id"], month)] += row["quantity"]
    targets: list[Row] = []
    for month_offset in (-1, 0):
        month = month_text(writer.seed_date, month_offset)
        for source, unit in (
            ("ELEC", "kWh"),
            ("GAS", "Nm3"),
            ("WATER", "m3"),
        ):
            targets.append(
                {
                    "site_id": site_id,
                    "equipment_id": None,
                    "energy_source_id": sources[source],
                    "target_scope": "SITE",
                    "target_month": month,
                    "target_value": decimal(
                        site_actual[(source, month)] * Decimal("0.95"), "0.000001"
                    ),
                    "unit": unit,
                }
            )
        toe = site_actual[("ELEC", month)] * Decimal("0.000229") + site_actual[
            ("GAS", month)
        ] * Decimal("0.001040")
        targets.append(
            {
                "site_id": site_id,
                "equipment_id": None,
                "energy_source_id": None,
                "target_scope": "SITE",
                "target_month": month,
                "target_value": decimal(toe * Decimal("0.95"), "0.000001"),
                "unit": "TOE",
            }
        )
        for code, equipment_id in equipment.items():
            if code == "INS-02" and month_offset == 0:
                continue
            targets.append(
                {
                    "site_id": None,
                    "equipment_id": equipment_id,
                    "energy_source_id": sources["ELEC"],
                    "target_scope": "EQUIPMENT",
                    "target_month": month,
                    "target_value": decimal(
                        equipment_actual[(equipment_id, month)] * Decimal("0.95"),
                        "0.000001",
                    ),
                    "unit": "kWh",
                }
            )
    writer.add("fems.energy_target", targets)
    baseline: dict[str, Decimal] = {}
    for item_code in ("FG-C100", "FG-C200", "FG-T300"):
        energy = Decimal("0")
        production = Decimal("0")
        for lot_name in (f"W{index:02d}" for index in range(1, 7)):
            if ITEM_FOR_LOT[lot_name] != item_code:
                continue
            for _, equipment_code, start_day, end_day in SCHEDULE[lot_name]:
                for day in range(start_day, end_day + 1):
                    energy += sum(hourly[(equipment_code, day)])
            production += Decimal(
                0 if lot_name == "W06" else RESULT_CHAIN[item_code][-1][1]
            )
        baseline[item_code] = decimal(energy / production, "0.000001")
    writer.add(
        "fems.energy_baseline",
        [
            {
                "baseline_code": code,
                "baseline_scope": "ITEM",
                "item_code": item,
                "equipment_id": None,
                "energy_source_id": sources["ELEC"],
                "baseline_value": value,
                "unit": "kWh/EA",
                "period_from": month_text(writer.seed_date, -4),
                "period_to": month_text(writer.seed_date, -3),
                "status": status,
            }
            for code, item, value, status in (
                ("BL-C100-01", "FG-C100", baseline["FG-C100"], "confirmed"),
                ("BL-C200-01", "FG-C200", baseline["FG-C200"], "confirmed"),
                ("BL-T300-01", "FG-T300", baseline["FG-T300"], "confirmed"),
                (
                    "BL-T300-02",
                    "FG-T300",
                    decimal(baseline["FG-T300"] * Decimal("0.99"), "0.000001"),
                    "draft",
                ),
            )
        ],
    )


def _production_records(
    writer: SeedWriter, context: dict[str, Any], equipment: dict[str, int]
) -> None:
    result_table = writer.table("mes.operation_result")
    results = {
        row["execution_id"]: row
        for row in writer.connection.execute(
            result_table.select()
            .where(result_table.c.workspace_id == writer.workspace_id)
            .where(result_table.c.generation_id == writer.generation_id)
        ).mappings()
    }
    rows: list[Row] = []
    for (lot_name, process), execution in context["executions"].items():
        if not lot_name.startswith("W") or execution["id"] not in results:
            continue
        result = results[execution["id"]]
        end_day = next(entry[3] for entry in SCHEDULE[lot_name] if entry[0] == process)
        source_key = f"MES:{context['lot_number'][lot_name]}:{process}"
        rows.append(
            {
                "source_key": source_key,
                "version_no": 1,
                "equipment_id": equipment[
                    next(
                        entry[1] for entry in SCHEDULE[lot_name] if entry[0] == process
                    )
                ],
                "item_code": ITEM_FOR_LOT[lot_name],
                "period_start": at(
                    writer.seed_date,
                    next(
                        entry[2] for entry in SCHEDULE[lot_name] if entry[0] == process
                    ),
                ),
                "period_end": at(writer.seed_date, end_day + 1),
                "production_qty": Decimal("1904")
                if lot_name == "W04" and process == "INS"
                else result["good_qty"],
                "unit": "EA",
                "status": "confirmed",
                "confirmed_at": result["confirmed_at"],
            }
        )
        if lot_name == "W04" and process == "INS":
            rows.append(
                {
                    **rows[-1],
                    "version_no": 2,
                    "production_qty": result["good_qty"],
                    "confirmed_at": result["confirmed_at"] + timedelta(hours=1),
                }
            )
    writer.add("fems.production_record", rows)
