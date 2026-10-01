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
    target_ratio,
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
        for schema in ("core", "mes", "erp", "fems", "qms", "wms", "bems", "spc", "gw"):
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
            for module in (
                "core",
                "mes",
                "erp",
                "fems",
                "qms",
                "wms",
                "bems",
                "spc",
                "gw",
            )
        ],
    )
    _masters(writer)
    context = _plans_and_mes(writer)
    _erp(writer, context)
    _fems(writer, context)
    _qms(writer, context)
    _wms(writer)
    _bems(writer)
    _spc(writer)
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
        "posted_at",
        "moved_at",
        "requested_at",
        "raised_at",
        "measured_at",  # spc.subgroup
        "effective_at",  # spc.control_limit — 게시 시각(publishedAt)
        "detected_at",  # spc.signal
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
    for schema in ("mes", "erp", "fems", "qms", "wms", "bems", "spc", "gw"):
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
                if parent_schema not in {
                    "mes",
                    "erp",
                    "fems",
                    "qms",
                    "wms",
                    "bems",
                    "spc",
                    "gw",
                }:
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
                        site_actual[(source, month)]
                        * target_ratio(source, month_offset),
                        "0.000001",
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
                "target_value": decimal(
                    toe * target_ratio("TOE", month_offset), "0.000001"
                ),
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
                        equipment_actual[(equipment_id, month)]
                        * target_ratio(code, month_offset),
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


# FS-023 §10. (순번, 이름, 방식, 하한, 상한, 단위). 절연 저항은 하한만 둔다.
QMS_SPEC_ITEMS: dict[
    str, list[tuple[int, str, str, str | None, str | None, str | None]]
] = {
    "FG-C100": [
        (1, "외관", "PASS_FAIL", None, None, None),
        (2, "핀 피치", "RANGE", "2.49", "2.59", "mm"),
        (3, "하우징 높이", "RANGE", "8.90", "9.10", "mm"),
        (4, "절연 저항", "RANGE", "100", None, "MΩ"),
    ],
    "FG-C200": [
        (1, "외관", "PASS_FAIL", None, None, None),
        (2, "핀 피치", "RANGE", "2.49", "2.59", "mm"),
        (3, "하우징 높이", "RANGE", "11.90", "12.10", "mm"),
        (4, "절연 저항", "RANGE", "100", None, "MΩ"),
    ],
    "FG-T300": [
        (1, "외관", "PASS_FAIL", None, None, None),
        (2, "단자 간격", "RANGE", "4.95", "5.05", "mm"),
        (3, "조임 토크", "RANGE", "0.40", "0.60", "N·m"),
        (4, "절연 저항", "RANGE", "100", None, "MΩ"),
    ],
}
# 확정 검사 LOT 15건. E08은 핀 피치 초과로 불합격 → 특채 해제, W04는 외관 불합격 → 보류 중(패킹 대기 배지).
# W03은 작성 중, W04 재검사는 작성 중, W05는 검사 대기로 남긴다.
QMS_CONFIRMED = [f"E{i:02d}" for i in range(1, 13)] + ["W01", "W02", "W04"]
QMS_FAILS = {"E08": (2, "2.6100", "PIN_MISALIGN"), "W04": (1, False, "APPEARANCE")}


def _qms_value(
    item: tuple[int, str, str, str | None, str | None, str | None], index: int
) -> Decimal | None:
    """항목 중앙값 근처의 결정적 측정값. 모두 한계 안이다."""
    _, _, method, lower, upper, _ = item
    if method == "PASS_FAIL":
        return None
    if upper is None:
        return Decimal(250 + 10 * (index % 7))
    low, high = Decimal(lower), Decimal(upper)
    step = (high - low) / 10
    return ((low + high) / 2 + step * ((index % 5) - 2)).quantize(Decimal("0.0001"))


def _qms(writer: SeedWriter, context: dict[str, Any]) -> None:
    seed_date = writer.seed_date
    items = {row["code"]: row for row in codebook()["items"]}
    defects = writer.add(
        "qms.defect_type",
        [
            {"code": code, "name": name, "is_active": True}
            for code, name in (
                ("MOLD_DAMAGE", "금형 손상"),
                ("SHORT_SHOT", "미충전"),
                ("PIN_MISALIGN", "핀 정렬 불량"),
                ("CONTACT_FAIL", "접촉 불량"),
                ("APPEARANCE", "외관 불량"),
                ("DIMENSION", "치수 불량"),
            )
        ],
        "code",
    )
    spec_rows = [
        {
            "item_code": code,
            "item_name": items[code]["name"],
            "version_no": 1,
            "status": "published",
            "published_at": at(seed_date, -60, 10),
            "note": None,
        }
        for code in QMS_SPEC_ITEMS
    ] + [
        {
            "item_code": "FG-C100",
            "item_name": items["FG-C100"]["name"],
            "version_no": 2,
            "status": "draft",
            "published_at": None,
            "note": "핀 피치 공차 축소 검토(2.50~2.58)",
        }
    ]
    specs = writer.add("qms.inspection_spec", spec_rows, ("item_code", "version_no"))
    spec_items: dict[tuple[str, int], list[int]] = {}
    for (code, version), spec_id in specs.items():
        rows = [
            {
                "spec_id": spec_id,
                "seq": seq,
                "name": name,
                "method": method,
                "lower_limit": Decimal("2.50")
                if version == 2 and seq == 2
                else None
                if lower is None
                else Decimal(lower),
                "upper_limit": Decimal("2.58")
                if version == 2 and seq == 2
                else None
                if upper is None
                else Decimal(upper),
                "unit": unit,
                "is_required": True,
            }
            for seq, name, method, lower, upper, unit in QMS_SPEC_ITEMS[code]
        ]
        mapped = writer.add("qms.inspection_spec_item", rows, "seq")
        spec_items[(code, version)] = [mapped[seq] for seq in sorted(mapped)]

    final_good = {code: chain[-1][1] for code, chain in RESULT_CHAIN.items()}
    numbers: dict[date, int] = defaultdict(int)

    def number(day: date) -> str:
        numbers[day] += 1
        return f"QI-{day:%Y%m%d}-{numbers[day]:03d}"

    def inspection(name: str, day: int, **values: Any) -> Row:
        code = ITEM_FOR_LOT[name]
        inspected_on = calendar_date(seed_date, day)
        return {
            "inspection_no": number(inspected_on),
            "source": "MES",
            "lot_no": context["lot_number"][name],
            "item_code": code,
            "item_name": items[code]["name"],
            "lot_qty": Decimal(final_good[code]),
            "unit": "EA",
            "sample_qty": Decimal(min(final_good[code], 32)),
            "spec_id": specs[(code, 1)],
            "reinspection_of_id": None,
            "status": "draft",
            "result": None,
            "inspected_on": inspected_on,
            "inspection_month": f"{inspected_on:%Y-%m}",
            "confirmed_at": None,
            "note": None,
            **values,
        }

    def inspection_day(name: str) -> int:
        return SCHEDULE[name][-1][3] + 1

    rows = [
        inspection(
            name,
            inspection_day(name),
            status="confirmed",
            result="FAIL" if name in QMS_FAILS else "PASS",
            confirmed_at=at(seed_date, inspection_day(name), 15),
            note={"E08": "핀 피치 상한 초과", "W04": "외관 흑점 — 보류"}.get(name),
        )
        for name in QMS_CONFIRMED
    ] + [inspection("W03", inspection_day("W03"))]
    confirmed = writer.add("qms.inspection", rows, "lot_no")
    retest = writer.add(
        "qms.inspection",
        [
            inspection(
                "W04",
                -1,
                reinspection_of_id=confirmed[context["lot_number"]["W04"]],
                note="보류 LOT 재검사",
            )
        ],
        "lot_no",
    )
    value_rows = []
    for index, name in enumerate([*QMS_CONFIRMED, "W03", "W04-retest"]):
        lot_name = name.removesuffix("-retest")
        lot_no = context["lot_number"][lot_name]
        inspection_id = (retest if name.endswith("-retest") else confirmed)[lot_no]
        code = ITEM_FOR_LOT[lot_name]
        for item, spec_item_id in zip(
            QMS_SPEC_ITEMS[code], spec_items[(code, 1)], strict=True
        ):
            seq, method = item[0], item[2]
            filled = name in QMS_CONFIRMED or (name == "W03" and seq <= 2)
            measured = _qms_value(item, index + seq) if filled else None
            passed = (True if method == "PASS_FAIL" else None) if filled else None
            defect = None
            fail = QMS_FAILS.get(name)
            if fail and fail[0] == seq:
                if method == "PASS_FAIL":
                    passed = fail[1]
                else:
                    measured = Decimal(fail[1])
                defect = defects[fail[2]]
            value_rows.append(
                {
                    "inspection_id": inspection_id,
                    "spec_item_id": spec_item_id,
                    "measured_value": measured,
                    "pass_value": passed,
                    "judgement": None if not filled else "FAIL" if defect else "PASS",
                    "defect_type_id": defect,
                }
            )
    writer.add("qms.inspection_value", value_rows)
    holds = []
    for name, released in (("E08", True), ("W04", False)):
        lot_no = context["lot_number"][name]
        held_day = inspection_day(name)
        holds.append(
            {
                "hold_no": f"QH-{calendar_date(seed_date, held_day):%Y%m%d}-001",
                "lot_no": lot_no,
                "item_code": ITEM_FOR_LOT[name],
                "inspection_id": confirmed[lot_no],
                "status": "released" if released else "held",
                "held_at": at(seed_date, held_day, 15),
                "disposition": "CONCESSION" if released else None,
                "release_inspection_id": None,
                "release_reason": "고객 승인 특채 — 핀 피치 0.02mm 초과, 조립 영향 없음"
                if released
                else None,
                "released_at": at(seed_date, held_day + 2, 10) if released else None,
            }
        )
    writer.add("qms.quality_hold", holds)


# FS-024 §10. 원천 반영 전표는 WMS가 "반영"을 눌렀을 때와 같은 모양으로 심는다(원천 키·LOT·단위 환산).
# 시연용 미반영: MES 입고 PL-0006, ERP 매입 PI-0004, ERP 출하 SH-0004, W 계열 LOT의 완료 실행 투입.
WMS_UNSYNCED = {"MES:RECEIPT:PL-0006", "ERP:PURCHASE:PI-0004", "ERP:SHIPMENT:SH-0004"}
WMS_PIN_FACTOR = Decimal("10000")


def _wms_sources(writer: SeedWriter) -> list[dict[str, Any]]:
    """인터페이스(fs.mes/fs.erp interface)와 같은 조건으로 원천을 읽는다. 시간순."""
    c, p = writer.connection, {"w": writer.workspace_id, "g": writer.generation_id}
    sources: list[dict[str, Any]] = []
    receipts: dict[str, dict[str, Any]] = {}
    for r in c.execute(
        text(
            "SELECT p.packing_no, r.received_at, t.lot_no, i.item_code, t.unit, sum(m.packed_qty) qty "
            "FROM mes.finished_goods_receipt r JOIN mes.packing_unit p ON p.workspace_id=r.workspace_id "
            "AND p.generation_id=r.generation_id AND p.id=r.packing_unit_id "
            "JOIN mes.packing_unit b ON b.workspace_id=p.workspace_id AND b.generation_id=p.generation_id AND b.parent_packing_unit_id=p.id "
            "JOIN mes.packing_member m ON m.workspace_id=b.workspace_id AND m.generation_id=b.generation_id AND m.packing_unit_id=b.id "
            "JOIN mes.lot t ON t.workspace_id=m.workspace_id AND t.generation_id=m.generation_id AND t.id=m.lot_id "
            "JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id AND o.id=t.work_order_id "
            "JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.status='confirmed' "
            "GROUP BY p.packing_no, r.received_at, t.lot_no, i.item_code, t.unit ORDER BY p.packing_no, t.lot_no"
        ),
        p,
    ).mappings():
        entry = receipts.setdefault(
            r["packing_no"],
            {
                "kind": "MES_RECEIPT",
                "key": f"MES:RECEIPT:{r['packing_no']}",
                "ref": r["packing_no"],
                "at": r["received_at"],
                "lines": [],
            },
        )
        entry["lines"].append((r["item_code"], r["qty"], r["unit"], r["lot_no"]))
    sources += receipts.values()
    issues: dict[str, dict[str, Any]] = {}
    for r in c.execute(
        text(
            "SELECT t.lot_no, pr.process_code, e.ended_at, i.item_code, mi.unit, sum(mi.issued_qty) qty "
            "FROM mes.operation_execution e JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id "
            "JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id AND s.id=e.route_step_id "
            "JOIN mes.process pr ON pr.workspace_id=s.workspace_id AND pr.generation_id=s.generation_id AND pr.id=s.process_id "
            "JOIN mes.material_issue mi ON mi.workspace_id=e.workspace_id AND mi.generation_id=e.generation_id AND mi.execution_id=e.id "
            "JOIN mes.item i ON i.workspace_id=mi.workspace_id AND i.generation_id=mi.generation_id AND i.id=mi.material_item_id "
            "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.status='completed' "
            "GROUP BY t.lot_no, pr.process_code, e.ended_at, i.item_code, mi.unit"
        ),
        p,
    ).mappings():
        ref = f"{r['lot_no']}:{r['process_code']}"
        entry = issues.setdefault(
            ref,
            {
                "kind": "MES_ISSUE",
                "key": f"MES:ISSUE:{ref}",
                "ref": ref,
                "at": r["ended_at"],
                "lines": [],
            },
        )
        entry["lines"].append((r["item_code"], r["qty"], r["unit"], None))
    sources += issues.values()
    shipments: dict[str, dict[str, Any]] = {}
    for r in c.execute(
        text(
            "SELECT sh.shipment_no, sh.shipped_at, i.item_code, l.shipped_qty qty, l.shipped_uom unit, l.packing_no "
            "FROM erp.shipment sh JOIN erp.shipment_line l ON l.workspace_id=sh.workspace_id AND l.generation_id=sh.generation_id AND l.shipment_id=sh.id "
            "JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id AND i.id=l.item_id "
            "WHERE sh.workspace_id=:w AND sh.generation_id=:g AND sh.status='confirmed' ORDER BY sh.shipment_no, l.id"
        ),
        p,
    ).mappings():
        entry = shipments.setdefault(
            r["shipment_no"],
            {
                "kind": "ERP_SHIPMENT",
                "key": f"ERP:SHIPMENT:{r['shipment_no']}",
                "ref": r["shipment_no"],
                "at": r["shipped_at"],
                "lines": [],
            },
        )
        entry["lines"].append((r["item_code"], r["qty"], r["unit"], r["packing_no"]))
    sources += shipments.values()
    purchases: dict[str, dict[str, Any]] = {}
    for r in c.execute(
        text(
            "SELECT p.invoice_no, p.confirmed_at, p.cancelled_at, i.item_code, l.quantity qty, l.unit "
            "FROM erp.purchase_invoice p JOIN erp.purchase_invoice_line l ON l.workspace_id=p.workspace_id "
            "AND l.generation_id=p.generation_id AND l.purchase_invoice_id=p.id "
            "JOIN erp.item i ON i.workspace_id=l.workspace_id AND i.generation_id=l.generation_id AND i.id=l.item_id "
            "WHERE p.workspace_id=:w AND p.generation_id=:g AND p.confirmed_at IS NOT NULL ORDER BY p.invoice_no, l.line_no"
        ),
        p,
    ).mappings():
        entry = purchases.setdefault(
            r["invoice_no"],
            {
                "kind": "ERP_PURCHASE",
                "key": f"ERP:PURCHASE:{r['invoice_no']}",
                "ref": r["invoice_no"],
                "at": r["confirmed_at"],
                "cancelled": r["cancelled_at"],
                "lines": [],
            },
        )
        entry["lines"].append((r["item_code"], r["qty"], r["unit"], None))
    sources += purchases.values()
    return sorted(sources, key=lambda s: (s["at"], s["key"]))


def _wms(writer: SeedWriter) -> None:
    seed_date = writer.seed_date
    items = {row["code"]: row for row in codebook()["items"]}
    houses = writer.add(
        "wms.warehouse",
        [
            {
                "code": "WH-RAW",
                "name": "원자재 창고",
                "purpose": "RAW",
                "is_active": True,
            },
            {
                "code": "WH-FG",
                "name": "완제품 창고",
                "purpose": "FG",
                "is_active": True,
            },
        ],
        "code",
    )
    locations = writer.add(
        "wms.storage_location",
        [
            {
                "warehouse_id": houses[h],
                "code": code,
                "name": name,
                "is_default": default,
                "is_active": True,
            }
            for h, code, name, default in (
                ("WH-RAW", "R-A01", "원자재 기본 보관", True),
                ("WH-RAW", "R-A02", "원자재 예비", False),
                ("WH-FG", "F-A01", "완제품 기본 보관", True),
                ("WH-FG", "F-A02", "완제품 출하 대기", False),
            )
        ],
        "code",
    )
    codes = ("RM-PBT", "RM-PIN", "FG-C100", "FG-C200", "FG-T300")
    wms_items = writer.add(
        "wms.item",
        [
            {
                "item_code": code,
                "name": items[code]["name"],
                "base_unit": items[code]["unit"],
                "item_class": "FG" if code.startswith("FG") else "RAW",
                "lot_tracked": code.startswith("FG"),
                "is_active": True,
            }
            for code in codes
        ],
        "item_code",
    )
    writer.add(
        "wms.item_unit_conversion",
        [
            {
                "item_id": wms_items["RM-PIN"],
                "from_unit": "BOX",
                "factor": WMS_PIN_FACTOR,
            }
        ],
    )

    numbers: dict[date, int] = defaultdict(int)
    documents: list[tuple[Row, list[Row]]] = []
    receipt_lots: dict[str, list[tuple[str, Decimal]]] = {}

    def base_qty(code: str, qty: Decimal, unit: str) -> Decimal:
        return qty * WMS_PIN_FACTOR if code == "RM-PIN" and unit == "BOX" else qty

    def document(
        kind: str, at_: datetime, status: str = "posted", **values: Any
    ) -> Row:
        on = at_.astimezone(SEOUL).date()
        return {
            "document_type": kind,
            "status": status,
            "source_key": None,
            "source_ref": None,
            "reverses_document_id": None,
            "reason_code": None,
            "document_on": on,
            "document_month": f"{on:%Y-%m}",
            "posted_at": at_ if status == "posted" else None,
            "note": None,
            **values,
        }

    def move(
        code: str,
        location: str,
        qty: Decimal,
        at_: datetime,
        lot: str | None = None,
        source: tuple[Decimal, str] | None = None,
    ) -> Row:
        return {
            "item_id": wms_items[code],
            "location_id": locations[location],
            "lot_no": lot,
            "qty_delta": qty,
            "source_qty": None if source is None else source[0],
            "source_unit": None if source is None else source[1],
            "moved_at": at_,
        }

    opening_at = at(seed_date, -91, 9)
    documents.append(
        (
            document("OPENING", opening_at, note="WMS 도입 기초재고"),
            [
                move("RM-PBT", "R-A01", Decimal("200"), opening_at),
                move("RM-PIN", "R-A01", Decimal("50000"), opening_at),
            ],
        )
    )
    for source in _wms_sources(writer):
        if source["key"] in WMS_UNSYNCED or (
            source["kind"] == "MES_ISSUE"
            and not source["ref"].startswith(
                tuple(f"LT-{i:04d}:" for i in range(1, 13))
            )
        ):
            continue
        at_ = source["at"]
        moves = []
        for code, qty, unit, extra in source["lines"]:
            if source["kind"] == "MES_RECEIPT":
                moves.append(move(code, "F-A01", qty, at_, extra, (qty, unit)))
                receipt_lots.setdefault(source["ref"], []).append((extra, qty))
            elif source["kind"] == "ERP_SHIPMENT":
                lots = receipt_lots.get(extra or "", [])
                assert sum(q for _, q in lots) == qty, f"{source['ref']} LOT 전량 출하"
                moves += [
                    move(code, "F-A01", -q, at_, lot, (q, unit)) for lot, q in lots
                ]
            else:
                sign = -1 if source["kind"] == "MES_ISSUE" else 1
                moves.append(
                    move(
                        code,
                        "R-A01",
                        sign * base_qty(code, qty, unit),
                        at_,
                        None,
                        (qty, unit),
                    )
                )
        documents.append(
            (
                document(
                    source["kind"],
                    at_,
                    source_key=source["key"],
                    source_ref=source["ref"],
                ),
                moves,
            )
        )
        if source.get("cancelled"):
            cancelled = source["cancelled"]
            documents.append(
                (
                    document(
                        "REVERSAL",
                        cancelled,
                        source_key=source["key"],
                        source_ref=source["ref"],
                        note="ERP 매입 취소 반영",
                        reverses=len(documents) - 1,
                    ),
                    [
                        {**m, "qty_delta": -m["qty_delta"], "moved_at": cancelled}
                        for m in moves
                    ],
                )
            )
    scrap_at = at(seed_date, -20, 14)
    documents.append(
        (
            document(
                "ADJUSTMENT",
                scrap_at,
                reason_code="SCRAP",
                note="외관 손상 폐기(QMS 확인)",
            ),
            [move("FG-C100", "F-A01", Decimal("-20"), scrap_at, "LT-0007")],
        )
    )
    draft_at = at(seed_date, -1, 16)
    documents.append(
        (
            document(
                "TRANSFER", draft_at, status="draft", note="출하 대기 위치로 이동 준비"
            ),
            [
                move("FG-C100", "F-A01", Decimal("-500"), draft_at, "LT-0010"),
                move("FG-C100", "F-A02", Decimal("500"), draft_at, "LT-0010"),
            ],
        )
    )
    move_rows: list[Row] = []
    order = sorted(
        range(len(documents)), key=lambda i: (documents[i][0]["document_on"], i)
    )
    doc_ids: dict[int, int] = {}
    for index in order:
        header, moves = documents[index]
        numbers[header["document_on"]] += 1
        row = {k: v for k, v in header.items() if k != "reverses"}
        row["document_no"] = (
            f"WD-{header['document_on']:%Y%m%d}-{numbers[header['document_on']]:03d}"
        )
        if "reverses" in header:
            row["reverses_document_id"] = doc_ids[header["reverses"]]
        doc_id = writer.add("wms.stock_document", [row], "document_no")[
            row["document_no"]
        ]
        doc_ids[index] = doc_id
        move_rows += [
            {**m, "document_id": doc_id, "line_no": n} for n, m in enumerate(moves, 1)
        ]
    writer.add("wms.stock_move", move_rows)
    from seed.wms_extension import append_examples

    append_examples(writer, houses, locations, wms_items)


# ---------- BEMS (FS-025c) ----------
# 과거 관측은 1시간 진행과 같은 모델(fs.bems.simulation)로 만든다. 공용 전력 30일, 환경 14일.
# 합은 FEMS 수전에 숨긴 공용 부하(주간 25·야간 15 kWh/h)보다 작다 → 잔여 음수 없음.
BEMS_SCHEDULE = [("WEEKDAY", 8, 19, "COOL"), ("WEEKEND", 10, 16, "FAN")]
BEMS_RULES = [
    ("Z-OFF", "CO2", "HIGH", "1000", 2, "WARNING"),
    ("Z-OFF", "TEMP", "HIGH", "28", 2, "WARNING"),
    ("Z-PRD", "TEMP", "HIGH", "30", 1, "CRITICAL"),
    ("Z-PRD", "HUMIDITY", "HIGH", "70", 3, "WARNING"),
]


def _bems_weekday(seed_date: date, day: int) -> bool:
    return (seed_date + timedelta(days=day)).weekday() < 5


def _bems_mode(seed_date: date, day: int, hour: int) -> str:
    kind = "WEEKDAY" if _bems_weekday(seed_date, day) else "WEEKEND"
    return next(
        (m for k, s, e, m in BEMS_SCHEDULE if k == kind and s <= hour < e), "OFF"
    )


def _bems(writer: SeedWriter) -> None:
    from fs.bems import simulation as sim

    seed_date = writer.seed_date
    zones = writer.add(
        "bems.zone",
        [
            {
                "code": "Z-OFF",
                "name": "사무동",
                "kind": "OFFICE",
                "floor_area_m2": Decimal("1200"),
            },
            {
                "code": "Z-PRD",
                "name": "생산동 공조 구역",
                "kind": "PRODUCTION",
                "floor_area_m2": Decimal("3000"),
            },
            {
                "code": "Z-UTL",
                "name": "유틸리티",
                "kind": "UTILITY",
                "floor_area_m2": Decimal("400"),
            },
        ],
        "code",
    )
    meters = writer.add(
        "bems.meter",
        [
            {
                "zone_id": zones["Z-UTL"],
                "code": "BM-LGT",
                "name": "건물 조명(전 구역 합)",
                "usage": "LIGHTING",
            },
            {
                "zone_id": zones["Z-OFF"],
                "code": "BM-HVAC",
                "name": "사무동 공조 전력",
                "usage": "HVAC",
            },
            {
                "zone_id": zones["Z-OFF"],
                "code": "BM-OFF",
                "name": "사무동 콘센트",
                "usage": "OFFICE",
            },
        ],
        "code",
    )
    units = {"TEMP": "℃", "HUMIDITY": "%", "CO2": "ppm"}
    sensors = writer.add(
        "bems.sensor",
        [
            {
                "zone_id": zones[z],
                "code": f"S-{z[2:]}-{m[:3]}",
                "metric": m,
                "unit": units[m],
            }
            for z in ("Z-OFF", "Z-PRD")
            for m in ("TEMP", "HUMIDITY", "CO2")
        ],
        ("zone_id", "metric"),
    )
    # 공조기: 사무동은 공조 계측기로 전력을 잰다. 생산동 공조기는 BEMS 계측이 없어 잔여로 남는다.
    hvac = {
        "AHU-OFF": ("Z-OFF", "사무동 공조기", "BM-HVAC", Decimal("12")),
        "AHU-PRD": ("Z-PRD", "생산동 공조기", None, Decimal("18")),
    }

    # 수동 명령(시연 이력): 평일 10시 사무동 공조기 수동 정지 → 재실 CO₂가 올라 경보, 19시 스케줄 경계에서 복귀.
    weekdays = [d for d in range(-14, 0) if _bems_weekday(seed_date, d)]
    off_days = [weekdays[1], weekdays[5], weekdays[7], weekdays[-1]]
    manual: list[Row] = []
    for day in off_days:
        manual.append(
            {
                "unit": "AHU-OFF",
                "day": day,
                "hour": 10,
                "command": "POWER_OFF",
                "note": "사무동 공조 점검(수동 정지)",
            }
        )
    manual += [
        {
            "unit": "AHU-OFF",
            "day": -20,
            "hour": 9,
            "command": "SET_SETPOINT",
            "kind": "COOL_TEMP",
            "value": Decimal("25"),
            "note": "무더위 냉방 강화",
        },
        {
            "unit": "AHU-OFF",
            "day": weekdays[3],
            "hour": 9,
            "command": "SET_SETPOINT",
            "kind": "COOL_TEMP",
            "value": Decimal("26"),
            "note": "기본값 복귀",
        },
        {
            "unit": "AHU-PRD",
            "day": weekdays[4],
            "hour": 11,
            "command": "SET_SETPOINT",
            "kind": "COOL_TEMP",
            "value": Decimal("31"),
            "note": "범위 밖 입력 예시",
        },
        {
            "unit": "AHU-PRD",
            "day": weekdays[4],
            "hour": 11,
            "command": "SET_SETPOINT",
            "kind": "COOL_TEMP",
            "value": Decimal("25"),
            "note": "생산동 냉방 강화",
        },
    ]
    by_hour: dict[tuple[int, int], list[Row]] = defaultdict(list)
    for m in manual:
        by_hour[(m["day"], m["hour"])].append(m)

    setpoints = {z: dict(sim.DEFAULT_SETPOINTS) for z in ("Z-OFF", "Z-PRD")}
    state = {u: ("OFF", "SCHEDULE") for u in hvac}
    changed_at: dict[str, datetime | None] = {u: None for u in hvac}
    env = {
        z: {k: Decimal(v) for k, v in sim.start_values(0).items()} for z in setpoints
    }
    energy_rows: list[Row] = []
    env_rows: list[Row] = []
    commands: list[Row] = []
    series: dict[tuple[str, str], list[tuple[datetime, Decimal]]] = defaultdict(list)
    for day in range(-30, 0):
        weekday = _bems_weekday(seed_date, day)
        for hour in range(24):
            moment = at(seed_date, day, hour)
            prev = (day, hour - 1) if hour else (day - 1, 23)
            for u in hvac:
                planned = _bems_mode(seed_date, day, hour)
                boundary = planned != _bems_mode(seed_date, *prev)
                current, source = state[u]
                if (source == "SCHEDULE" or boundary) and (
                    current != planned or source != "SCHEDULE"
                ):
                    if day >= -2:  # 스케줄 전환 이력은 최근 2일만 남긴다(시드 크기)
                        commands.append(
                            {
                                "zone": hvac[u][0],
                                "unit": u,
                                "at": moment,
                                "source": "SCHEDULE",
                                "result": "APPLIED",
                                "command": "POWER_OFF"
                                if planned == "OFF"
                                else ("POWER_ON" if current == "OFF" else "SET_MODE"),
                                "mode": planned
                                if current != "OFF" and planned != "OFF"
                                else None,
                            }
                        )
                    state[u] = (planned, "SCHEDULE")
                    changed_at[u] = moment
            for m in by_hour.get((day, hour), []):
                zone = hvac[m["unit"]][0]
                row = {
                    "zone": zone,
                    "unit": m["unit"],
                    "at": moment,
                    "source": "MANUAL",
                    "command": m["command"],
                    "note": m["note"],
                    "result": "APPLIED",
                }
                if m["command"] == "SET_SETPOINT":
                    reason = sim.setpoint_error(m["kind"], m["value"], setpoints[zone])
                    row.update(
                        kind=m["kind"],
                        value=m["value"],
                        result="REJECTED" if reason else "APPLIED",
                        reason=reason,
                    )
                    if not reason:
                        setpoints[zone][m["kind"]] = m["value"]
                else:
                    state[m["unit"]] = ("OFF", "MANUAL")
                    changed_at[m["unit"]] = moment
                commands.append(row)
            hvac_kwh = Decimal(0)
            for zone in setpoints:
                unit = next(u for u in hvac if hvac[u][0] == zone)
                mode = state[unit][0]
                env[zone] = {
                    "TEMP": sim.next_temperature(
                        env[zone]["TEMP"], hour, mode, setpoints[zone]
                    ),
                    "HUMIDITY": sim.next_humidity(env[zone]["HUMIDITY"], mode),
                    "CO2": sim.next_co2(
                        env[zone]["CO2"], hour, weekday, zone == "Z-OFF", mode
                    ),
                }
                if hvac[unit][2]:
                    hvac_kwh += sim.hvac_power(
                        mode, hvac[unit][3], env[zone]["TEMP"], setpoints[zone]
                    )
                if day >= -14:
                    for metric, value in env[zone].items():
                        env_rows.append(
                            {
                                "sensor_id": sensors[(zones[zone], metric)],
                                "period_start": moment,
                                "value": value,
                                "source": "SEED",
                            }
                        )
                        series[(zone, metric)].append((moment, value))
            for code, usage in (
                ("BM-LGT", "LIGHTING"),
                ("BM-HVAC", "HVAC"),
                ("BM-OFF", "OFFICE"),
            ):
                value = (
                    hvac_kwh
                    if usage == "HVAC"
                    else sim.fixed_load(usage, hour, weekday)
                )
                energy_rows.append(
                    {
                        "meter_id": meters[code],
                        "period_start": moment,
                        "value": value,
                        "source": "SEED",
                    }
                )

    hvac_ids = writer.add(
        "bems.hvac_unit",
        [
            {
                "zone_id": zones[z],
                "code": code,
                "name": name,
                "meter_id": meters[m] if m else None,
                "rated_kw": rated,
                "state": state[code][0],
                "control_source": state[code][1],
                "state_changed_at": changed_at[code],
            }
            for code, (z, name, m, rated) in hvac.items()
        ],
        "code",
    )
    writer.add(
        "bems.schedule_slot",
        [
            {
                "hvac_unit_id": hvac_ids[u],
                "day_kind": k,
                "start_hour": s,
                "end_hour": e,
                "mode": mode,
            }
            for u in hvac
            for k, s, e, mode in BEMS_SCHEDULE
        ],
    )
    writer.add("bems.energy_reading", energy_rows)
    writer.add("bems.environment_reading", env_rows)
    writer.add(
        "bems.control_command",
        [
            {
                "zone_id": zones[c["zone"]],
                "hvac_unit_id": hvac_ids[c["unit"]],
                "command": c["command"],
                "mode": c.get("mode"),
                "setpoint_kind": c.get("kind"),
                "value": c.get("value"),
                "source": c["source"],
                "requested_at": c["at"],
                "result": c["result"],
                "reject_reason": c.get("reason"),
                "note": c.get("note"),
            }
            for c in commands
        ],
    )
    rules = writer.add(
        "bems.alarm_rule",
        [
            {
                "zone_id": zones[z],
                "metric": m,
                "comparator": cmp,
                "threshold": Decimal(t),
                "duration_hours": n,
                "severity": sev,
            }
            for z, m, cmp, t, n, sev in BEMS_RULES
        ],
        ("zone_id", "metric", "comparator"),
    )
    # 경보: 1시간 진행과 같은 판정(최근 N시간 모두 넘으면 발생, 최신값이 돌아오면 해제)을 14일 관측에 적용.
    alarms: list[Row] = []
    for z, metric, cmp, t, n, _ in BEMS_RULES:
        threshold, high = Decimal(t), cmp == "HIGH"
        values = series[(z, metric)]
        current: Row | None = None
        for i, (moment, value) in enumerate(values):
            window = [v for _, v in values[max(0, i - n + 1) : i + 1]]
            hit = value > threshold if high else value < threshold
            if current is None:
                if len(window) == n and all(
                    (v > threshold) if high else (v < threshold) for v in window
                ):
                    current = {
                        "alarm_rule_id": rules[(zones[z], metric, cmp)],
                        "sensor_id": sensors[(zones[z], metric)],
                        "raised_at": moment,
                        "peak_value": max(window) if high else min(window),
                    }
                    alarms.append(current)
            elif not hit:
                current.update(status="cleared", cleared_at=moment)
                current = None
            else:
                current["peak_value"] = (
                    max(current["peak_value"], value)
                    if high
                    else min(current["peak_value"], value)
                )
    for a in alarms:
        a.setdefault("status", "raised")
        a.setdefault("cleared_at", None)
        a.update(acknowledged_at=None, ack_note=None)
        # 지난 경보는 다음 날 09시에 확인한 것으로 둔다. 마지막 발생 중 경보는 확인 대기(시연용).
        if a["status"] == "cleared":
            a["acknowledged_at"] = min(
                a["cleared_at"], a["raised_at"] + timedelta(hours=1)
            )
            a["ack_note"] = "확인 — 공조 재가동"
    writer.add("bems.alarm", alarms)


# ---------- SPC (FS-028c) ----------
# 특성: 코드, 품목, 공정, 특성명, 단위, LSL, USL, 목표, 자릿수, σ̂(목표 공정능력에서 정함).
# 공정능력: 충분 4 · 주의 1(FG-C200 사출, 추세) · 부족 1(FG-T300 조립 토크, 분산 큼) — validate V13이 확인한다.
SPC_CHARACTERISTICS: list[tuple[str, str, str, str, str, str, str, str, int, str]] = [
    (
        "CH-C100-INJ-H",
        "FG-C100",
        "INJ",
        "하우징 높이",
        "mm",
        "8.90",
        "9.10",
        "9.00",
        3,
        "0.019",
    ),
    (
        "CH-C100-ASM-P",
        "FG-C100",
        "ASM",
        "핀 피치",
        "mm",
        "2.49",
        "2.59",
        "2.54",
        3,
        "0.010",
    ),
    (
        "CH-C200-INJ-H",
        "FG-C200",
        "INJ",
        "하우징 높이",
        "mm",
        "11.90",
        "12.10",
        "12.00",
        3,
        "0.026",
    ),
    (
        "CH-C200-ASM-P",
        "FG-C200",
        "ASM",
        "핀 피치",
        "mm",
        "2.49",
        "2.59",
        "2.54",
        3,
        "0.009",
    ),
    (
        "CH-T300-INJ-G",
        "FG-T300",
        "INJ",
        "단자 간격",
        "mm",
        "4.95",
        "5.05",
        "5.00",
        3,
        "0.010",
    ),
    (
        "CH-T300-ASM-T",
        "FG-T300",
        "ASM",
        "조임 토크",
        "N·m",
        "0.40",
        "0.60",
        "0.50",
        3,
        "0.040",
    ),
]
SPC_INTERVAL_HOURS = 6  # D39: 공정 실행 안에서 6시간마다 n=5
SPC_TREND_LOT = "LT-0017"  # FG-C200 사출(INJ-02): 연속 상승(규칙 3) 뒤 한계 초과(규칙 1), 미조치 — QMS 검사 대기 LOT
SPC_JIG_RUN = (
    3  # FG-C100 조립: 4번째 공정 실행에서 지그 마모로 규칙 1 → 조치 완료 → v2 재게시
)
_SPC_SHAPE = (
    Decimal("-0.5"),
    Decimal("-0.15"),
    Decimal("0.05"),
    Decimal("0.1"),
    Decimal("0.5"),
)
_SPC_Q = Decimal("0.0001")


def _spc_runs(writer: SeedWriter) -> list[dict[str, Any]]:
    """MES 시드의 시작된 공정 실행(시드는 제품 코드가 아니므로 MES 테이블을 직접 읽는다)."""
    rows = writer.connection.execute(
        text(
            "SELECT t.lot_no, i.item_code, pr.process_code, eq.equipment_code, e.started_at, e.ended_at "
            "FROM mes.operation_execution e "
            "JOIN mes.lot t ON t.workspace_id=e.workspace_id AND t.generation_id=e.generation_id AND t.id=e.lot_id "
            "JOIN mes.work_order o ON o.workspace_id=t.workspace_id AND o.generation_id=t.generation_id AND o.id=t.work_order_id "
            "JOIN mes.item i ON i.workspace_id=o.workspace_id AND i.generation_id=o.generation_id AND i.id=o.item_id "
            "JOIN mes.route_step s ON s.workspace_id=e.workspace_id AND s.generation_id=e.generation_id AND s.id=e.route_step_id "
            "JOIN mes.process pr ON pr.workspace_id=s.workspace_id AND pr.generation_id=s.generation_id AND pr.id=s.process_id "
            "JOIN mes.equipment eq ON eq.workspace_id=e.workspace_id AND eq.generation_id=e.generation_id AND eq.id=e.equipment_id "
            "WHERE e.workspace_id=:w AND e.generation_id=:g AND e.started_at IS NOT NULL "
            "ORDER BY e.started_at, t.lot_no"
        ),
        {"w": writer.workspace_id, "g": writer.generation_id},
    ).mappings()
    return [dict(r) for r in rows]


def _spc_values(mean: Decimal, spread: Decimal, rng: Any) -> list[Decimal]:
    """평균 mean·범위 spread인 측정값 5개(순서는 섞는다)."""
    shape = list(_SPC_SHAPE)
    rng.shuffle(shape)
    return [(mean + spread * s).quantize(_SPC_Q) for s in shape]


def _spc(writer: SeedWriter) -> None:
    import math
    import random

    from fs.spc import stats

    seed_date = writer.seed_date
    limit_at_most = at(seed_date, 0)
    runs = _spc_runs(writer)
    items = {
        r["item_code"]: r["name"]
        for r in writer.connection.execute(
            text(
                "SELECT item_code, name FROM mes.item WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": writer.workspace_id, "g": writer.generation_id},
        ).mappings()
    }
    chars = writer.add(
        "spc.characteristic",
        [
            {
                "code": code,
                "item_code": item,
                "item_name": items[item],
                "process_code": process,
                "name": name,
                "unit": unit,
                "lsl": Decimal(lsl),
                "usl": Decimal(usl),
                "target": Decimal(target),
                "decimals": decimals,
            }
            for code, item, process, name, unit, lsl, usl, target, decimals, _ in SPC_CHARACTERISTICS
        ],
        "code",
    )
    d2 = stats.CONSTANTS[5]["d2"]
    for index, (
        code,
        item,
        process,
        _n,
        _u,
        _l,
        _h,
        target,
        _d,
        sigma_text,
    ) in enumerate(SPC_CHARACTERISTICS):
        rng = random.Random(28_000 + index)
        sigma = Decimal(sigma_text)
        sigma_x = sigma / Decimal(math.sqrt(5))
        r_bar = sigma * d2
        center = Decimal(target)
        mine = [
            r for r in runs if r["item_code"] == item and r["process_code"] == process
        ]
        plan: list[dict[str, Any]] = []
        for run_no, run in enumerate(mine):
            end = run["ended_at"] or limit_at_most
            slot = run["started_at"] + timedelta(hours=1)
            while slot <= end:
                plan.append({"run": run, "run_no": run_no, "at": slot})
                slot += timedelta(hours=SPC_INTERVAL_HOURS)
        # 평소: 중심선 위·아래를 번갈아(규칙 2·3이 우연히 생기지 않게), 거리는 0.35~1.3 σx.
        for k, p in enumerate(plan):
            side = 1 if k % 2 else -1
            p["mean"] = center + side * sigma_x * Decimal(
                str(round(rng.uniform(0.35, 1.3), 3))
            )
            p["spread"] = r_bar * Decimal(str(round(rng.uniform(0.75, 1.25), 3)))
        if code == "CH-C200-INJ-H":
            trend = [
                k for k, p in enumerate(plan) if p["run"]["lot_no"] == SPC_TREND_LOT
            ][-6:]
            assert len(trend) == 6, "LT-0017 사출 부분군 6개 이상"
            plan[trend[0] - 1]["mean"] = center + sigma_x * Decimal("0.8")
            for step, k in zip(
                trend, ("-0.9", "-0.3", "0.4", "1.3", "2.4", "3.8"), strict=True
            ):
                plan[step]["mean"] = center + sigma_x * Decimal(k)
            if trend[-1] + 1 < len(plan):
                plan[trend[-1] + 1]["mean"] = center - sigma_x * Decimal("0.8")
        jig = None
        if code == "CH-C100-ASM-P":
            in_run = [k for k, p in enumerate(plan) if p["run_no"] == SPC_JIG_RUN]
            jig = in_run[3]
            plan[jig]["mean"] = center + sigma_x * Decimal("3.8")
        subgroup_rows = []
        values_by_at: dict[datetime, list[Decimal]] = {}
        for p in plan:
            values = _spc_values(p["mean"], p["spread"], rng)
            xbar, r = stats.subgroup(values)
            p.update(values=values, xbar=xbar, r=r)
            values_by_at[p["at"]] = values
            subgroup_rows.append(
                {
                    "characteristic_id": chars[code],
                    "lot_no": p["run"]["lot_no"],
                    "item_code": item,
                    "process_code": process,
                    "equipment_code": p["run"]["equipment_code"],
                    "run_started_at": p["run"]["started_at"],
                    "run_ended_at": p["run"]["ended_at"],
                    "measured_at": p["at"],
                    "xbar": xbar,
                    "r": r,
                    "source": "SEED",
                }
            )
        ids = writer.add("spc.subgroup", subgroup_rows, "measured_at")
        writer.add(
            "spc.measurement",
            [
                {"subgroup_id": ids[at_], "seq": seq, "value": v}
                for at_, values in values_by_at.items()
                for seq, v in enumerate(values, 1)
            ],
        )
        # 한계: v1 = 처음 20 부분군, FG-C100 조립은 지그 교체 뒤 20 부분군으로 v2. 적용 시작 = 기준 마지막 부분군 측정 시각.
        bases = [(plan[:20], "초기 한계(처음 20 부분군)")]
        if jig is not None:
            bases.append((plan[jig + 1 : jig + 21], "지그 교체 후 재산정"))
        limits = []
        for version, (basis, reason) in enumerate(bases, 1):
            computed = stats.limits([p["xbar"] for p in basis], [p["r"] for p in basis])
            limits.append(
                {
                    "characteristic_id": chars[code],
                    "version": version,
                    "effective_at": basis[-1]["at"],
                    "basis_from": basis[0]["at"],
                    "basis_to": basis[-1]["at"],
                    "basis_count": len(basis),
                    "reason": reason,
                    **computed,
                }
            )
        limit_ids = writer.add("spc.control_limit", limits, "version")
        # 판정(제품 TX-S1과 같은 규칙): 측정 시각에 유효한 버전, 연속 규칙은 같은 버전 안에서만.
        signals = []
        for k, p in enumerate(plan):
            applicable = [lim for lim in limits if lim["effective_at"] < p["at"]]
            if not applicable:
                continue
            lim = applicable[-1]
            previous = [q["xbar"] for q in plan[:k] if q["at"] > lim["effective_at"]]
            for chart, rule, value in stats.signals(previous, p["xbar"], p["r"], lim):
                row = {
                    "subgroup_id": ids[p["at"]],
                    "characteristic_id": chars[code],
                    "control_limit_id": limit_ids[lim["version"]],
                    "lot_no": p["run"]["lot_no"],
                    "chart": chart,
                    "rule": rule,
                    "value": value,
                    "detected_at": p["at"],
                }
                if k == jig:
                    row.update(
                        status="resolved",
                        cause_category="MACHINE",
                        action="조립 지그 마모 확인 — 지그 교체 후 첫 부분군 정상 확인",
                        resolved_at=p["at"] + timedelta(hours=3),
                    )
                signals.append(row)
        writer.add("spc.signal", signals)
