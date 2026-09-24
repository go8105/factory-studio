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
TARIFF_COLUMNS = "id,energy_source_id,tariff_code,name,contract_type,basic_charge,usage_rate,currency,effective_from,effective_to,created_at"
TARIFF_SORT = {
    "tariffCode": "tariff_code",
    "name": "name",
    "effectiveFrom": "effective_from",
    "createdAt": "created_at",
}


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


def source_exists(connection: Connection, context: AuthContext, source_id: int) -> bool:
    count = connection.execute(
        text(
            "SELECT count(*) FROM fems.energy_source "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": source_id},
    ).scalar_one()
    return count > 0


def tariff_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "energySourceId": row["energy_source_id"],
        "tariffCode": row["tariff_code"],
        "name": row["name"],
        "contractType": row["contract_type"],
        "basicCharge": str(row["basic_charge"]),
        "usageRate": str(row["usage_rate"]),
        "currency": row["currency"],
        "effectiveFrom": row["effective_from"],
        "effectiveTo": row["effective_to"],
        "createdAt": row["created_at"].isoformat(),
    }


def list_tariffs(
    connection: Connection,
    context: AuthContext,
    energy_source_id: int | None,
    order: str,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "workspace_id=:w AND generation_id=:g"
    params: dict[str, Any] = {**_s(context), "offset": offset, "limit": limit}
    if energy_source_id is not None:
        where += " AND energy_source_id=:energy_source_id"
        params["energy_source_id"] = energy_source_id
    total = connection.execute(
        text(f"SELECT count(*) FROM fems.tariff WHERE {where}"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {TARIFF_COLUMNS} FROM fems.tariff WHERE {where} "
            f"ORDER BY {order}, id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [tariff_dict(r) for r in rows], total


def get_tariff(
    connection: Connection, context: AuthContext, tariff_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {TARIFF_COLUMNS} FROM fems.tariff "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": tariff_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else tariff_dict(row)


def tariff_code_taken(
    connection: Connection,
    context: AuthContext,
    tariff_code: str,
    tariff_id: int | None,
) -> bool:
    where = "workspace_id=:w AND generation_id=:g AND tariff_code=:code"
    params: dict[str, Any] = {**_s(context), "code": tariff_code}
    if tariff_id is not None:
        where += " AND id!=:id"
        params["id"] = tariff_id
    count = connection.execute(
        text(f"SELECT count(*) FROM fems.tariff WHERE {where}"), params
    ).scalar_one()
    return count > 0


def insert_tariff(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    payload = {"currency": "KRW", **values}
    columns = ",".join(payload.keys())
    placeholders = ",".join(f":{column}" for column in payload)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.tariff (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) RETURNING {TARIFF_COLUMNS}"
            ),
            {**_s(context), **payload},
        )
        .mappings()
        .one()
    )
    return tariff_dict(row)


def update_tariff(
    connection: Connection,
    context: AuthContext,
    tariff_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.tariff SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {TARIFF_COLUMNS}"
            ),
            {**_s(context), **values, "id": tariff_id},
        )
        .mappings()
        .one()
    )
    return tariff_dict(row)


def delete_tariff(connection: Connection, context: AuthContext, tariff_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.tariff WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": tariff_id},
    )


def find_overlapping_tariffs(
    connection: Connection,
    context: AuthContext,
    energy_source_id: int,
    effective_from: str,
    effective_to: str | None,
    exclude_tariff_id: int | None = None,
) -> list[dict[str, Any]]:
    where = (
        "workspace_id=:w AND generation_id=:g AND energy_source_id=:energy_source_id"
    )
    params: dict[str, Any] = {**_s(context), "energy_source_id": energy_source_id}
    if exclude_tariff_id is not None:
        where += " AND id!=:exclude_id"
        params["exclude_id"] = exclude_tariff_id
    rows = connection.execute(
        text(
            f"SELECT {TARIFF_COLUMNS} FROM fems.tariff WHERE {where} "
            "ORDER BY effective_from ASC, id ASC"
        ),
        params,
    ).mappings()
    conflicts = []
    for r in rows:
        r_from = r["effective_from"]
        r_to = r["effective_to"]
        if (effective_to is not None and effective_to < r_from) or (
            r_to is not None and r_to < effective_from
        ):
            continue
        conflicts.append(
            {
                "id": r["id"],
                "tariffCode": r["tariff_code"],
                "effectiveFrom": r_from,
                "effectiveTo": r_to,
            }
        )
    return conflicts


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
READING_PERIOD = (
    " AND r.observed_at > (CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)"
    " AND r.observed_at <= (CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)"
)
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
    where = READING_FROM + READING_PERIOD
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


# ---- F-03 설비별 배분 (FS-018c) ----
# 배분 구간은 [D 00:00, D+1 00:00) (설비 → 공간 → 사업장 시간대, FS-005g 5.3).
# 같은 설비·채널·구간에 결과가 여러 개면 input_revision, method_version이 가장 큰 것이 현재 결과다.
ALLOCATION_BASE = """
SELECT a.id,a.period_start,a.period_end,a.quantity,a.unit,a.method_key,a.method_version,
       a.input_revision,a.quality,a.basis,
       eq.id equipment_id,eq.equipment_code,eq.name equipment_name,
       c.channel_code,c.name channel_name,e.id energy_source_id,e.source_code,s.timezone,
       row_number() OVER (
         PARTITION BY a.equipment_id,a.meter_channel_id,a.period_start,a.period_end
         ORDER BY a.input_revision DESC,a.method_version DESC,a.id DESC
       ) = 1 is_latest
FROM fems.energy_allocation a
JOIN fems.equipment eq
  ON eq.workspace_id=a.workspace_id AND eq.generation_id=a.generation_id AND eq.id=a.equipment_id
JOIN fems.location l
  ON l.workspace_id=eq.workspace_id AND l.generation_id=eq.generation_id AND l.id=eq.location_id
JOIN fems.site s
  ON s.workspace_id=l.workspace_id AND s.generation_id=l.generation_id AND s.id=l.site_id
JOIN fems.meter_channel c
  ON c.workspace_id=a.workspace_id AND c.generation_id=a.generation_id AND c.id=a.meter_channel_id
JOIN fems.energy_source e
  ON e.workspace_id=c.workspace_id AND e.generation_id=c.generation_id AND e.id=c.energy_source_id
WHERE a.workspace_id=:w AND a.generation_id=:g
  AND a.period_start >= (CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)
  AND a.period_end <= (CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)
"""
# 필터는 현재 결과 판정(row_number) 밖에서 건다. 안에서 걸면 걸러진 행끼리 최신을 고른다.
ALLOCATION_FILTERS = {
    "equipment_id": "x.equipment_id=:equipment_id",
    "energy_source_id": "x.energy_source_id=:energy_source_id",
    "method_key": "x.method_key=:method_key",
}


def allocation_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "periodStart": row["period_start"].isoformat(),
        "periodEnd": row["period_end"].isoformat(),
        "timezone": row["timezone"],
        "equipmentId": row["equipment_id"],
        "equipmentCode": row["equipment_code"],
        "equipmentName": row["equipment_name"],
        "channelCode": row["channel_code"],
        "channelName": row["channel_name"],
        "energySourceCode": row["source_code"],
        "quantity": str(row["quantity"]),
        "unit": row["unit"],
        "methodKey": row["method_key"],
        "methodVersion": row["method_version"],
        "inputRevision": row["input_revision"],
        "quality": row["quality"],
        "basis": row["basis"],
        "isLatest": row["is_latest"],
    }


def latest_allocation_date(connection: Connection, context: AuthContext) -> Any:
    return connection.execute(
        text(
            """
            SELECT max(((a.period_end - interval '1 microsecond') AT TIME ZONE s.timezone)::date)
            FROM fems.energy_allocation a
            JOIN fems.equipment eq
              ON eq.workspace_id=a.workspace_id AND eq.generation_id=a.generation_id AND eq.id=a.equipment_id
            JOIN fems.location l
              ON l.workspace_id=eq.workspace_id AND l.generation_id=eq.generation_id AND l.id=eq.location_id
            JOIN fems.site s
              ON s.workspace_id=l.workspace_id AND s.generation_id=l.generation_id AND s.id=l.site_id
            WHERE a.workspace_id=:w AND a.generation_id=:g
            """
        ),
        _s(context),
    ).scalar_one()


def _allocation_scope(filters: dict[str, Any]) -> str:
    """현재 결과 판정 후 필터를 적용한 행 집합. 별칭 x로 감싼다."""
    where = "".join(f" AND {ALLOCATION_FILTERS[key]}" for key in filters)
    return f"SELECT x.* FROM ({ALLOCATION_BASE}) x WHERE TRUE{where}"


def list_allocations(
    connection: Connection,
    context: AuthContext,
    filters: dict[str, Any],
    date_from: Any,
    date_to: Any,
    include_superseded: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    scope = f"SELECT * FROM ({_allocation_scope(filters)}) z" + (
        "" if include_superseded else " WHERE z.is_latest"
    )
    params = {
        **_s(context),
        **filters,
        "date_from": date_from,
        "date_to": date_to,
        "offset": offset,
        "limit": limit,
    }
    total = connection.execute(
        text(f"SELECT count(*) FROM ({scope}) y"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            scope
            + " ORDER BY period_start, equipment_code, channel_code, input_revision DESC, id"
            + " OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [allocation_dict(r) for r in rows], total


def allocation_summary(
    connection: Connection,
    context: AuthContext,
    filters: dict[str, Any],
    date_from: Any,
    date_to: Any,
) -> list[dict[str, Any]]:
    # 현재 결과만, invalid 제외, 단위별로 따로 합한다(단위가 다른 에너지원을 더하지 않는다).
    rows = connection.execute(
        text(
            f"""
            SELECT equipment_id,equipment_code,equipment_name,source_code,unit,
                   sum(quantity) quantity,count(*) days,
                   count(*) FILTER (WHERE quality='estimated') estimated_days
            FROM ({_allocation_scope(filters)}) z
            WHERE z.is_latest AND z.quality<>'invalid'
            GROUP BY equipment_id,equipment_code,equipment_name,source_code,unit
            ORDER BY unit, sum(quantity) DESC, equipment_code
            """
        ),
        {**_s(context), **filters, "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [
        {
            "equipmentId": r["equipment_id"],
            "equipmentCode": r["equipment_code"],
            "equipmentName": r["equipment_name"],
            "energySourceCode": r["source_code"],
            "unit": r["unit"],
            "quantity": str(r["quantity"]),
            "days": r["days"],
            "estimatedDays": r["estimated_days"],
        }
        for r in rows
    ]


# ---- F-04 배출량 (FS-018d) ----
def emission_consumption(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> list[dict[str, Any]]:
    """에너지원 × 계측 단위 × 연도별 소비량.

    최상위 계측기(parent_meter_id IS NULL)만 합한다. 하위 계측기는 수전에 이미 포함돼 있어
    더하면 이중 합산이다. 결측(invalid)은 빼고 건수를 센다. 계기 배수를 곱한다.
    """
    rows = connection.execute(
        text(
            "SELECT e.id source_id,e.source_code,e.name,e.source_kind,c.unit,"
            "to_char((r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone,'YYYY') reading_year,"
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) quantity,"
            "count(*) FILTER (WHERE r.quality='invalid') excluded "
            + READING_FROM
            + READING_PERIOD
            + " AND m.parent_meter_id IS NULL"
            " GROUP BY e.id,e.source_code,e.name,e.source_kind,c.unit,reading_year"
            " ORDER BY e.source_code,c.unit,reading_year"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def emission_factors(
    connection: Connection, context: AuthContext
) -> dict[tuple[int, str], dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT energy_source_id,effective_year,factor_value,factor_unit,source_note "
            "FROM fems.energy_factor "
            "WHERE workspace_id=:w AND generation_id=:g AND factor_kind='EMISSION'"
        ),
        _s(context),
    ).mappings()
    return {(r["energy_source_id"], r["effective_year"]): dict(r) for r in rows}
