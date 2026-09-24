"""FEMS 질의. 모든 질의는 S=(workspace_id, generation_id)를 조건에 포함한다."""

from __future__ import annotations

from typing import Any

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext

SOURCE_COLUMNS = (
    "id,source_code,name,source_kind,measure_unit,is_billable,is_active,created_at"
)
SOURCE_SORT = {
    "sourceCode": "source_code",
    "name": "name",
    "createdAt": "created_at",
}
# energy_source를 참조하는 테이블 (schema.json FK r99·r101·r103·r107·r110)
SOURCE_REFERENCES = (
    ("fems.meter_channel", "계측 채널"),
    ("fems.energy_factor", "환산·배출계수"),
    ("fems.tariff", "요금제"),
    ("fems.energy_target", "에너지 목표"),
    ("fems.energy_baseline", "기준선"),
)


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


def source_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "sourceCode": row["source_code"],
        "name": row["name"],
        "sourceKind": row["source_kind"],
        "measureUnit": row["measure_unit"],
        "isBillable": row["is_billable"],
        "isActive": row["is_active"],
        "createdAt": row["created_at"].isoformat(),
    }


def list_sources(
    connection: Connection,
    context: AuthContext,
    active: bool | None,
    order: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "workspace_id=:w AND generation_id=:g"
    params: dict[str, Any] = {**_s(context), "offset": offset, "limit": limit}
    if active is not None:
        where += " AND is_active=:active"
        params["active"] = active
    total = connection.execute(
        text(f"SELECT count(*) FROM fems.energy_source WHERE {where}"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {SOURCE_COLUMNS} FROM fems.energy_source WHERE {where} "
            f"ORDER BY {order}, id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [source_dict(r) for r in rows], total


def get_source(
    connection: Connection, context: AuthContext, source_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {SOURCE_COLUMNS} FROM fems.energy_source "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": source_id},
        )
        .mappings()
        .one_or_none()
    )
    return source_dict(row) if row else None


def code_taken(
    connection: Connection, context: AuthContext, code: str, except_id: int | None
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.energy_source WHERE workspace_id=:w AND generation_id=:g "
                "AND source_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "code": code, "except": except_id},
        ).first()
        is not None
    )


def insert_source(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                f"""
            INSERT INTO fems.energy_source
              (workspace_id,generation_id,source_code,name,source_kind,measure_unit,is_billable,is_active)
            VALUES (:w,:g,:source_code,:name,:source_kind,:measure_unit,:is_billable,:is_active)
            RETURNING {SOURCE_COLUMNS}
            """
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return source_dict(row)


def update_source(
    connection: Connection, context: AuthContext, source_id: int, values: dict[str, Any]
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.energy_source SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {SOURCE_COLUMNS}"
            ),
            {**_s(context), **values, "id": source_id},
        )
        .mappings()
        .one()
    )
    return source_dict(row)


def delete_source(connection: Connection, context: AuthContext, source_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.energy_source WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": source_id},
    )


def source_references(
    connection: Connection, context: AuthContext, source_id: int
) -> list[dict[str, Any]]:
    references = []
    for table, label in SOURCE_REFERENCES:
        count = connection.execute(
            text(
                f"SELECT count(*) FROM {table} "
                "WHERE workspace_id=:w AND generation_id=:g AND energy_source_id=:id"
            ),
            {**_s(context), "id": source_id},
        ).scalar_one()
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


EQUIPMENT_COLUMNS = (
    "id,location_id,equipment_code,name,equipment_type,is_active,created_at"
)
EQUIPMENT_SORT = {
    "equipmentCode": "equipment_code",
    "name": "name",
    "equipmentType": "equipment_type",
    "createdAt": "created_at",
}
# equipment를 참조하는 테이블 (schema.json FK r97·r105·r108·r122·r135)
EQUIPMENT_REFERENCES = (
    ("fems.meter", "계측기"),
    ("fems.energy_target", "에너지 목표"),
    ("fems.energy_baseline", "기준선"),
    ("fems.energy_allocation", "에너지 배분"),
    ("fems.production_record", "생산 실적"),
)
LOCATION_COLUMNS = "id,location_code,name,kind"


def equipment_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "locationId": row["location_id"],
        "equipmentCode": row["equipment_code"],
        "name": row["name"],
        "equipmentType": row["equipment_type"],
        "isActive": row["is_active"],
        "createdAt": row["created_at"].isoformat(),
    }


def location_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "locationCode": row["location_code"],
        "name": row["name"],
        "kind": row["kind"],
    }


def list_equipments(
    connection: Connection,
    context: AuthContext,
    active: bool | None,
    location_id: int | None,
    order: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "workspace_id=:w AND generation_id=:g"
    params: dict[str, Any] = {**_s(context), "offset": offset, "limit": limit}
    if active is not None:
        where += " AND is_active=:active"
        params["active"] = active
    if location_id is not None:
        where += " AND location_id=:location_id"
        params["location_id"] = location_id
    total = connection.execute(
        text(f"SELECT count(*) FROM fems.equipment WHERE {where}"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {EQUIPMENT_COLUMNS} FROM fems.equipment WHERE {where} "
            f"ORDER BY {order}, id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [equipment_dict(r) for r in rows], total


def get_equipment(
    connection: Connection, context: AuthContext, equipment_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {EQUIPMENT_COLUMNS} FROM fems.equipment "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": equipment_id},
        )
        .mappings()
        .one_or_none()
    )
    return equipment_dict(row) if row else None


def equipment_code_taken(
    connection: Connection, context: AuthContext, code: str, except_id: int | None
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.equipment WHERE workspace_id=:w AND generation_id=:g "
                "AND equipment_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "code": code, "except": except_id},
        ).first()
        is not None
    )


def location_exists(
    connection: Connection, context: AuthContext, location_id: int
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.location WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": location_id},
        ).first()
        is not None
    )


def insert_equipment(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                f"""
            INSERT INTO fems.equipment
              (workspace_id,generation_id,equipment_code,name,equipment_type,location_id,is_active)
            VALUES (:w,:g,:equipment_code,:name,:equipment_type,:location_id,:is_active)
            RETURNING {EQUIPMENT_COLUMNS}
            """
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return equipment_dict(row)


def update_equipment(
    connection: Connection,
    context: AuthContext,
    equipment_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.equipment SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {EQUIPMENT_COLUMNS}"
            ),
            {**_s(context), **values, "id": equipment_id},
        )
        .mappings()
        .one()
    )
    return equipment_dict(row)


def delete_equipment(
    connection: Connection, context: AuthContext, equipment_id: int
) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.equipment WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": equipment_id},
    )


def equipment_references(
    connection: Connection, context: AuthContext, equipment_id: int
) -> list[dict[str, Any]]:
    references = []
    for table, label in EQUIPMENT_REFERENCES:
        count = connection.execute(
            text(
                f"SELECT count(*) FROM {table} "
                "WHERE workspace_id=:w AND generation_id=:g AND equipment_id=:id"
            ),
            {**_s(context), "id": equipment_id},
        ).scalar_one()
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


def equipment_meter_references(
    connection: Connection, context: AuthContext, equipment_id: int
) -> list[dict[str, Any]]:
    count = connection.execute(
        text(
            "SELECT count(*) FROM fems.meter "
            "WHERE workspace_id=:w AND generation_id=:g AND equipment_id=:id"
        ),
        {**_s(context), "id": equipment_id},
    ).scalar_one()
    if count:
        return [{"table": "fems.meter", "label": "계측기", "count": count}]
    return []


def list_locations(
    connection: Connection, context: AuthContext
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {LOCATION_COLUMNS} FROM fems.location "
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY location_code ASC"
        ),
        _s(context),
    ).mappings()
    return [location_dict(r) for r in rows]


# ---- F-02 계측 조회 (FS-018b) ----
# 계측값은 구간 끝 시각(observed_at)에 기록된다. 00:00 관측값은 전날 23~24시 구간이다.
# 조회 기간 [from, to]는 계측기 사업장 시간대의 날짜이며 (from 00:00, to+1 00:00]로 변환한다.
READING_FROM = """
FROM fems.energy_reading r
JOIN fems.meter_channel c
  ON c.workspace_id=r.workspace_id AND c.generation_id=r.generation_id AND c.id=r.meter_channel_id
JOIN fems.meter m
  ON m.workspace_id=c.workspace_id AND m.generation_id=c.generation_id AND m.id=c.meter_id
JOIN fems.site s
  ON s.workspace_id=m.workspace_id AND s.generation_id=m.generation_id AND s.id=m.site_id
JOIN fems.energy_source e
  ON e.workspace_id=c.workspace_id AND e.generation_id=c.generation_id AND e.id=c.energy_source_id
WHERE r.workspace_id=:w AND r.generation_id=:g
"""
READING_FILTERS = {
    "site_id": "s.id=:site_id",
    "meter_id": "m.id=:meter_id",
    "channel_id": "c.id=:channel_id",
    "energy_source_id": "e.id=:energy_source_id",
    "quality": "r.quality=:quality",
}
READING_SORT = {"observedAt": "r.observed_at"}


def reading_dict(row: Any) -> dict[str, Any]:
    # 결측(invalid)은 value=0으로 저장돼 있다(FS-005g 5.2). 0이 소비량으로 합산되지 않게 null로 낸다.
    missing = row["quality"] == "invalid"
    return {
        "id": row["id"],
        "observedAt": row["observed_at"].isoformat(),
        "periodStart": row["period_start"].isoformat() if row["period_start"] else None,
        "timezone": row["timezone"],
        "meterCode": row["meter_code"],
        "channelId": row["channel_id"],
        "channelCode": row["channel_code"],
        "channelName": row["channel_name"],
        "energySourceCode": row["source_code"],
        "value": None if missing else str(row["value"]),
        "unit": row["unit"],
        "quality": row["quality"],
        "inputRevision": row["input_revision"],
    }


def latest_reading_date(connection: Connection, context: AuthContext) -> Any:
    return connection.execute(
        text(
            "SELECT max(((r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone)::date) "
            + READING_FROM
        ),
        _s(context),
    ).scalar_one()


def list_readings(
    connection: Connection,
    context: AuthContext,
    filters: dict[str, Any],
    date_from: Any,
    date_to: Any,
    order: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = (
        READING_FROM
        + " AND r.observed_at > (CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)"
        + " AND r.observed_at <= (CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)"
    )
    for key in filters:
        where += f" AND {READING_FILTERS[key]}"
    params = {
        **_s(context),
        **filters,
        "date_from": date_from,
        "date_to": date_to,
        "offset": offset,
        "limit": limit,
    }
    total = connection.execute(text("SELECT count(*) " + where), params).scalar_one()
    rows = connection.execute(
        text(
            "SELECT r.id,r.observed_at,r.period_start,r.value,r.unit,r.quality,r.input_revision,"
            "s.timezone,m.meter_code,c.id channel_id,c.channel_code,c.name channel_name,e.source_code "
            + where
            + f" ORDER BY {order}, c.channel_code, r.id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [reading_dict(r) for r in rows], total


def list_sites(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT id,site_code,name,timezone FROM fems.site "
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY site_code"
        ),
        _s(context),
    ).mappings()
    return [
        {
            "id": r["id"],
            "siteCode": r["site_code"],
            "name": r["name"],
            "timezone": r["timezone"],
        }
        for r in rows
    ]


def list_meters(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            """
            SELECT m.id,m.meter_code,m.name,m.site_id,
                   c.id channel_id,c.channel_code,c.name channel_name,c.unit,
                   c.energy_source_id,c.multiplier
            FROM fems.meter m
            LEFT JOIN fems.meter_channel c
              ON c.workspace_id=m.workspace_id AND c.generation_id=m.generation_id AND c.meter_id=m.id
            WHERE m.workspace_id=:w AND m.generation_id=:g
            ORDER BY m.meter_code, c.channel_code
            """
        ),
        _s(context),
    ).mappings()
    meters: dict[int, dict[str, Any]] = {}
    for r in rows:
        meter = meters.setdefault(
            r["id"],
            {
                "id": r["id"],
                "meterCode": r["meter_code"],
                "name": r["name"],
                "siteId": r["site_id"],
                "channels": [],
            },
        )
        if r["channel_id"] is not None:
            meter["channels"].append(
                {
                    "id": r["channel_id"],
                    "channelCode": r["channel_code"],
                    "name": r["channel_name"],
                    "unit": r["unit"],
                    "energySourceId": r["energy_source_id"],
                    "multiplier": str(r["multiplier"]),
                }
            )
    return list(meters.values())
