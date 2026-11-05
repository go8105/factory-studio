"""FEMS 질의. 모든 질의는 S=(workspace_id, generation_id)를 조건에 포함한다.

에너지원(energy_source)은 공통 엔진으로 옮겼다 — `fs.common.master`와 service.py의 `SOURCE` 선언.
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import Connection, text

from fs.common.auth import AuthContext


def _s(context: AuthContext) -> dict[str, int]:
    return {"w": context.workspace_id, "g": context.generation_id}


EQUIPMENT_COLUMNS = "id,location_id,equipment_code,name,equipment_type,department_code,is_active,created_at"
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
LOCATION_COLUMNS = "id,site_id,parent_location_id,location_code,name,kind"
TARIFF_COLUMNS = "id,energy_source_id,tariff_code,name,contract_type,basic_charge,usage_rate,currency,effective_from,effective_to,tariff_kind,contract_kw,created_at"
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
        # HR 부서 코드 스냅샷(F06). 비용 배분이 부서별로 묶는 기준이다.
        "departmentCode": row["department_code"],
        "isActive": row["is_active"],
        "createdAt": row["created_at"].isoformat(),
    }


def location_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "siteId": row["site_id"],
        "parentLocationId": row["parent_location_id"],
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
              (workspace_id,generation_id,equipment_code,name,equipment_type,location_id,
               department_code,is_active)
            VALUES (:w,:g,:equipment_code,:name,:equipment_type,:location_id,
                    :department_code,:is_active)
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
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY site_id, location_code, id"
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
        "tariffKind": row["tariff_kind"],
        "contractKw": None if row["contract_kw"] is None else str(row["contract_kw"]),
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


# ---- F-13 환산·배출계수 (FS-018k) ----
FACTOR_COLUMNS = "id,energy_source_id,factor_kind,effective_year,factor_value,factor_unit,source_note,created_at"


def factor_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "energySourceId": row["energy_source_id"],
        "factorKind": row["factor_kind"],
        "effectiveYear": row["effective_year"],
        "factorValue": str(row["factor_value"]),
        "factorUnit": row["factor_unit"],
        "sourceNote": row["source_note"],
        "createdAt": row["created_at"].isoformat(),
    }


def list_factors(
    connection: Connection,
    context: AuthContext,
    factor_kind: str | None,
    energy_source_id: int | None,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "workspace_id=:w AND generation_id=:g"
    params: dict[str, Any] = {**_s(context), "offset": offset, "limit": limit}
    if factor_kind is not None:
        where += " AND factor_kind=:kind"
        params["kind"] = factor_kind
    if energy_source_id is not None:
        where += " AND energy_source_id=:source"
        params["source"] = energy_source_id
    total = connection.execute(
        text(f"SELECT count(*) FROM fems.energy_factor WHERE {where}"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            f"SELECT {FACTOR_COLUMNS} FROM fems.energy_factor WHERE {where} "
            "ORDER BY effective_year DESC, energy_source_id, id OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [factor_dict(r) for r in rows], total


def get_factor(
    connection: Connection, context: AuthContext, factor_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {FACTOR_COLUMNS} FROM fems.energy_factor "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": factor_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else factor_dict(row)


def factor_taken(
    connection: Connection,
    context: AuthContext,
    energy_source_id: int,
    factor_kind: str,
    effective_year: str,
    exclude_id: int | None,
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT count(*) FROM fems.energy_factor "
                "WHERE workspace_id=:w AND generation_id=:g AND energy_source_id=:source "
                "AND factor_kind=:kind AND effective_year=:year AND id IS DISTINCT FROM :id"
            ),
            {
                **_s(context),
                "source": energy_source_id,
                "kind": factor_kind,
                "year": effective_year,
                "id": exclude_id,
            },
        ).scalar_one()
        > 0
    )


def insert_factor(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.energy_factor (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) RETURNING {FACTOR_COLUMNS}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return factor_dict(row)


def update_factor(
    connection: Connection,
    context: AuthContext,
    factor_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.energy_factor SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {FACTOR_COLUMNS}"
            ),
            {**_s(context), **values, "id": factor_id},
        )
        .mappings()
        .one()
    )
    return factor_dict(row)


def delete_factor(connection: Connection, context: AuthContext, factor_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.energy_factor "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": factor_id},
    )


# ---- F-12 계측기·채널 (FS-018l) ----
# 채널에 계측값이나 배분 결과가 있으면 "사용 중"이다(소유·단위 변경과 삭제를 막는다).
CHANNEL_USAGE = (
    ("fems.energy_reading", "계측값"),
    ("fems.energy_allocation", "에너지 배분"),
)
_USED = " OR ".join(
    f"EXISTS (SELECT 1 FROM {table} t WHERE t.workspace_id=c.workspace_id "
    "AND t.generation_id=c.generation_id AND t.meter_channel_id=c.id)"
    for table, _ in CHANNEL_USAGE
)
METER_SELECT = (
    "SELECT m.id,m.site_id,m.location_id,m.parent_meter_id,m.equipment_id,m.meter_code,"
    "m.name,m.scope_kind,m.created_at,"
    "(SELECT count(*) FROM fems.meter_channel c WHERE c.workspace_id=m.workspace_id "
    "AND c.generation_id=m.generation_id AND c.meter_id=m.id) channel_count,"
    "EXISTS (SELECT 1 FROM fems.meter_channel c WHERE c.workspace_id=m.workspace_id "
    f"AND c.generation_id=m.generation_id AND c.meter_id=m.id AND ({_USED})) observed "
    "FROM fems.meter m WHERE m.workspace_id=:w AND m.generation_id=:g"
)
CHANNEL_SELECT = (
    "SELECT c.id,c.meter_id,c.energy_source_id,c.channel_code,c.name,c.measurement_kind,"
    f"c.unit,c.multiplier,c.is_active,c.created_at,({_USED}) observed "
    "FROM fems.meter_channel c WHERE c.workspace_id=:w AND c.generation_id=:g"
)


def meter_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "siteId": row["site_id"],
        "locationId": row["location_id"],
        "parentMeterId": row["parent_meter_id"],
        "equipmentId": row["equipment_id"],
        "meterCode": row["meter_code"],
        "name": row["name"],
        "scopeKind": row["scope_kind"],
        "channelCount": row["channel_count"],
        "observed": row["observed"],
        "createdAt": row["created_at"].isoformat(),
    }


def channel_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "meterId": row["meter_id"],
        "energySourceId": row["energy_source_id"],
        "channelCode": row["channel_code"],
        "name": row["name"],
        "measurementKind": row["measurement_kind"],
        "unit": row["unit"],
        "multiplier": str(row["multiplier"]),
        "isActive": row["is_active"],
        "observed": row["observed"],
        "createdAt": row["created_at"].isoformat(),
    }


def get_meter(
    connection: Connection, context: AuthContext, meter_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"{METER_SELECT} AND m.id=:id"), {**_s(context), "id": meter_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else meter_dict(row)


def meter_code_taken(
    connection: Connection, context: AuthContext, code: str, except_id: int | None
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.meter WHERE workspace_id=:w AND generation_id=:g "
                "AND meter_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "code": code, "except": except_id},
        ).first()
        is not None
    )


def location_site(
    connection: Connection, context: AuthContext, location_id: int
) -> int | None:
    return connection.execute(
        text(
            "SELECT site_id FROM fems.location "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": location_id},
    ).scalar_one_or_none()


def meter_ancestors(
    connection: Connection, context: AuthContext, meter_id: int
) -> set[int]:
    """meter_id 자신과 그 위 부모들. 부모로 지정하려는 계측기에 자신이 있으면 순환이다."""
    rows = connection.execute(
        text(
            "WITH RECURSIVE up(id, parent) AS ("
            " SELECT id, parent_meter_id FROM fems.meter"
            " WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            " UNION"
            " SELECT m.id, m.parent_meter_id FROM fems.meter m JOIN up ON m.id=up.parent"
            " WHERE m.workspace_id=:w AND m.generation_id=:g"
            ") SELECT id FROM up"
        ),
        {**_s(context), "id": meter_id},
    ).scalars()
    return set(rows)


def insert_meter(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> int:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    return connection.execute(
        text(
            f"INSERT INTO fems.meter (workspace_id, generation_id, {columns}) "
            f"VALUES (:w, :g, {placeholders}) RETURNING id"
        ),
        {**_s(context), **values},
    ).scalar_one()


def update_meter(
    connection: Connection, context: AuthContext, meter_id: int, values: dict[str, Any]
) -> None:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    connection.execute(
        text(
            f"UPDATE fems.meter SET {assignments} "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), **values, "id": meter_id},
    )


def delete_meter(connection: Connection, context: AuthContext, meter_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.meter WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": meter_id},
    )


def meter_references(
    connection: Connection, context: AuthContext, meter_id: int
) -> list[dict[str, Any]]:
    references = []
    for table, column, label in (
        ("fems.meter", "parent_meter_id", "하위 계측기"),
        ("fems.meter_channel", "meter_id", "계측 채널"),
    ):
        count = connection.execute(
            text(
                f"SELECT count(*) FROM {table} "
                f"WHERE workspace_id=:w AND generation_id=:g AND {column}=:id"
            ),
            {**_s(context), "id": meter_id},
        ).scalar_one()
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


def channel_usage(
    connection: Connection,
    context: AuthContext,
    *,
    meter_id: int | None = None,
    channel_id: int | None = None,
) -> list[dict[str, Any]]:
    """계측기 전체(meter_id) 또는 채널 하나(channel_id)의 계측값·배분 건수."""
    condition = "c.meter_id=:id" if meter_id is not None else "c.id=:id"
    references = []
    for table, label in CHANNEL_USAGE:
        count = connection.execute(
            text(
                f"SELECT count(*) FROM {table} t JOIN fems.meter_channel c "
                "ON c.workspace_id=t.workspace_id AND c.generation_id=t.generation_id "
                "AND c.id=t.meter_channel_id "
                f"WHERE t.workspace_id=:w AND t.generation_id=:g AND {condition}"
            ),
            {**_s(context), "id": meter_id if meter_id is not None else channel_id},
        ).scalar_one()
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


def get_channel(
    connection: Connection, context: AuthContext, meter_id: int, channel_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(f"{CHANNEL_SELECT} AND c.meter_id=:meter AND c.id=:id"),
            {**_s(context), "meter": meter_id, "id": channel_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else channel_dict(row)


def channel_code_taken(
    connection: Connection,
    context: AuthContext,
    meter_id: int,
    code: str,
    except_id: int | None,
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.meter_channel WHERE workspace_id=:w AND generation_id=:g "
                "AND meter_id=:meter AND channel_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "meter": meter_id, "code": code, "except": except_id},
        ).first()
        is not None
    )


def insert_channel(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> int:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    return connection.execute(
        text(
            f"INSERT INTO fems.meter_channel (workspace_id, generation_id, {columns}) "
            f"VALUES (:w, :g, {placeholders}) RETURNING id"
        ),
        {**_s(context), **values},
    ).scalar_one()


def update_channel(
    connection: Connection,
    context: AuthContext,
    channel_id: int,
    values: dict[str, Any],
) -> None:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    connection.execute(
        text(
            f"UPDATE fems.meter_channel SET {assignments} "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), **values, "id": channel_id},
    )


def delete_channel(
    connection: Connection, context: AuthContext, channel_id: int
) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.meter_channel "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": channel_id},
    )


# ---- F-09 사업장·공간 (FS-018m) ----
SITE_COLUMNS = "id,site_code,name,timezone"


def site_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "siteCode": row["site_code"],
        "name": row["name"],
        "timezone": row["timezone"],
    }


def _count(connection: Connection, context: AuthContext, sql: str, key: int) -> int:
    return connection.execute(text(sql), {**_s(context), "id": key}).scalar_one()


def _references(
    connection: Connection,
    context: AuthContext,
    checks: tuple[tuple[str, str, str], ...],
    key: int,
) -> list[dict[str, Any]]:
    """(테이블, 조건 SQL, 표시명) 목록을 세어 0이 아닌 것만 돌려준다."""
    references = []
    for table, sql, label in checks:
        count = _count(connection, context, sql, key)
        if count:
            references.append({"table": table, "label": label, "count": count})
    return references


def get_site(
    connection: Connection, context: AuthContext, site_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {SITE_COLUMNS} FROM fems.site "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": site_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else site_dict(row)


def site_code_taken(
    connection: Connection, context: AuthContext, code: str, except_id: int | None
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.site WHERE workspace_id=:w AND generation_id=:g "
                "AND site_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "code": code, "except": except_id},
        ).first()
        is not None
    )


def insert_site(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.site (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) RETURNING {SITE_COLUMNS}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return site_dict(row)


def update_site(
    connection: Connection, context: AuthContext, site_id: int, values: dict[str, Any]
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.site SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {SITE_COLUMNS}"
            ),
            {**_s(context), **values, "id": site_id},
        )
        .mappings()
        .one()
    )
    return site_dict(row)


def delete_site(connection: Connection, context: AuthContext, site_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.site WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": site_id},
    )


_S = "workspace_id=:w AND generation_id=:g"


def site_references(
    connection: Connection, context: AuthContext, site_id: int
) -> list[dict[str, Any]]:
    return _references(
        connection,
        context,
        tuple(
            (table, f"SELECT count(*) FROM {table} WHERE {_S} AND site_id=:id", label)
            for table, label in (
                ("fems.location", "공간"),
                ("fems.meter", "계측기"),
                ("fems.energy_target", "에너지 목표"),
            )
        ),
        site_id,
    )


def site_time_usage(
    connection: Connection, context: AuthContext, site_id: int
) -> list[dict[str, Any]]:
    """사업장 시간대로 날짜 경계를 정하는 기록 건수(계측값·배분·생산량)."""
    by_equipment = (
        "JOIN fems.equipment e ON e.workspace_id=t.workspace_id "
        "AND e.generation_id=t.generation_id AND e.id=t.equipment_id "
        "JOIN fems.location l ON l.workspace_id=e.workspace_id "
        "AND l.generation_id=e.generation_id AND l.id=e.location_id "
        "WHERE t.workspace_id=:w AND t.generation_id=:g AND l.site_id=:id"
    )
    return _references(
        connection,
        context,
        (
            (
                "fems.energy_reading",
                (
                    "SELECT count(*) FROM fems.energy_reading t "
                    "JOIN fems.meter_channel c ON c.workspace_id=t.workspace_id "
                    "AND c.generation_id=t.generation_id AND c.id=t.meter_channel_id "
                    "JOIN fems.meter m ON m.workspace_id=c.workspace_id "
                    "AND m.generation_id=c.generation_id AND m.id=c.meter_id "
                    "WHERE t.workspace_id=:w AND t.generation_id=:g AND m.site_id=:id"
                ),
                "계측값",
            ),
            (
                "fems.energy_allocation",
                f"SELECT count(*) FROM fems.energy_allocation t {by_equipment}",
                "에너지 배분",
            ),
            (
                "fems.production_record",
                f"SELECT count(*) FROM fems.production_record t {by_equipment}",
                "생산 실적",
            ),
        ),
        site_id,
    )


def get_location(
    connection: Connection, context: AuthContext, location_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {LOCATION_COLUMNS} FROM fems.location "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": location_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else location_dict(row)


def location_code_taken(
    connection: Connection,
    context: AuthContext,
    site_id: int,
    code: str,
    except_id: int | None,
) -> bool:
    return (
        connection.execute(
            text(
                "SELECT 1 FROM fems.location WHERE workspace_id=:w AND generation_id=:g "
                "AND site_id=:site AND location_code=:code AND id IS DISTINCT FROM :except"
            ),
            {**_s(context), "site": site_id, "code": code, "except": except_id},
        ).first()
        is not None
    )


def location_ancestors(
    connection: Connection, context: AuthContext, location_id: int
) -> set[int]:
    """location_id 자신과 그 위 상위 공간들. 상위로 지정하려는 공간에 자신이 있으면 순환이다."""
    rows = connection.execute(
        text(
            "WITH RECURSIVE up(id, parent) AS ("
            " SELECT id, parent_location_id FROM fems.location"
            " WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            " UNION"
            " SELECT l.id, l.parent_location_id FROM fems.location l"
            " JOIN up ON l.id=up.parent"
            " WHERE l.workspace_id=:w AND l.generation_id=:g"
            ") SELECT id FROM up"
        ),
        {**_s(context), "id": location_id},
    ).scalars()
    return set(rows)


def insert_location(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values)
    placeholders = ",".join(f":{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.location (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) RETURNING {LOCATION_COLUMNS}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return location_dict(row)


def update_location(
    connection: Connection,
    context: AuthContext,
    location_id: int,
    values: dict[str, Any],
) -> dict[str, Any]:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.location SET {assignments} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id RETURNING {LOCATION_COLUMNS}"
            ),
            {**_s(context), **values, "id": location_id},
        )
        .mappings()
        .one()
    )
    return location_dict(row)


def delete_location(
    connection: Connection, context: AuthContext, location_id: int
) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.location "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": location_id},
    )


def location_references(
    connection: Connection, context: AuthContext, location_id: int
) -> list[dict[str, Any]]:
    return _references(
        connection,
        context,
        tuple(
            (table, f"SELECT count(*) FROM {table} WHERE {_S} AND {column}=:id", label)
            for table, column, label in (
                ("fems.location", "parent_location_id", "하위 공간"),
                ("fems.equipment", "location_id", "설비"),
                ("fems.meter", "location_id", "계측기"),
            )
        ),
        location_id,
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
# 소비 집계의 공통 조건. 하위 계측기는 수전에 이미 포함돼 이중 합산이 되고, **발전(GENERATION)은
# 만든 양이라 소비가 아니다** — 거르지 않으면 발전량이 소비량·피크·요금에 섞인다.
CONSUMPTION_ONLY = " AND m.parent_meter_id IS NULL AND e.source_kind <> 'GENERATION'"
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
            f"SELECT {SITE_COLUMNS} FROM fems.site "
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY site_code"
        ),
        _s(context),
    ).mappings()
    return [site_dict(r) for r in rows]


def list_meters(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    """모든 계측기와 채널. F-02 채널 선택과 F-12 관리 화면이 함께 쓴다(한 사업장 수십 대 규모)."""
    meters = {
        r["id"]: {**meter_dict(r), "channels": []}
        for r in connection.execute(
            text(f"{METER_SELECT} ORDER BY m.meter_code, m.id"), _s(context)
        ).mappings()
    }
    for r in connection.execute(
        text(f"{CHANNEL_SELECT} ORDER BY c.channel_code, c.id"), _s(context)
    ).mappings():
        meters[r["meter_id"]]["channels"].append(channel_dict(r))
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


def production_by_equipment(
    connection: Connection,
    context: AuthContext,
    date_from: Any,
    date_to: Any,
    prorate: bool = False,
) -> dict[int, dict[str, Any]]:
    """기간과 겹치는 **유효 확정본**의 설비별 생산량. 원단위의 분모다.

    같은 원천 키의 최신 확정 버전만 센다 — 정정본이 있으면 옛 버전은 빠진다.

    `prorate`면 기간에 걸친 만큼만 일할 계산한다. 기록이 월 단위인데 비교 기간이 월
    경계와 어긋나면 겹친 기록 전체를 세게 되어 원단위가 틀린다(절감 검증이 쓴다).
    """
    # 기록이 사업장 시간대 기준이라 기간도 그 시간대로 자른다. 세션 시간대(UTC)로 자르면
    # 한국 자정이 UTC 15:00이라 9시간이 어긋나 일할 계산이 틀어진다.
    start = "(CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)"
    end = "(CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)"
    share = (
        f"greatest(0, extract(epoch FROM (least(p.period_end, {end}) "
        f"- greatest(p.period_start, {start})))) "
        "/ extract(epoch FROM (p.period_end - p.period_start))"
        if prorate
        else "1"
    )
    rows = connection.execute(
        text(
            f"""
            SELECT equipment_id, unit, sum(production_qty * share) qty
            FROM (
              SELECT p.equipment_id, p.unit, p.production_qty, {share} share,
                     p.status='confirmed' AND p.version_no = max(p.version_no)
                       FILTER (WHERE p.status='confirmed')
                       OVER (PARTITION BY p.source_key) is_effective
              FROM fems.production_record p
              JOIN fems.equipment q ON q.workspace_id=p.workspace_id
               AND q.generation_id=p.generation_id AND q.id=p.equipment_id
              JOIN fems.location l ON l.workspace_id=q.workspace_id
               AND l.generation_id=q.generation_id AND l.id=q.location_id
              JOIN fems.site s ON s.workspace_id=l.workspace_id
               AND s.generation_id=l.generation_id AND s.id=l.site_id
              WHERE p.workspace_id=:w AND p.generation_id=:g
                AND p.period_start < {end}
                AND p.period_end > {start}
            ) z
            WHERE z.is_effective
            GROUP BY equipment_id, unit
            """
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return {r["equipment_id"]: {"qty": r["qty"], "unit": r["unit"]} for r in rows}


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
            + CONSUMPTION_ONLY
            + " GROUP BY e.id,e.source_code,e.name,e.source_kind,c.unit,reading_year"
            " ORDER BY e.source_code,c.unit,reading_year"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def factors(
    connection: Connection, context: AuthContext, kind: str
) -> dict[tuple[int, str], dict[str, Any]]:
    """(에너지원, 연도) → 계수. kind는 'EMISSION' 또는 'PRIMARY' 하나만 받는다(섞지 않는다)."""
    rows = connection.execute(
        text(
            "SELECT energy_source_id,effective_year,factor_value,factor_unit,source_note "
            "FROM fems.energy_factor "
            "WHERE workspace_id=:w AND generation_id=:g AND factor_kind=:kind"
        ),
        {**_s(context), "kind": kind},
    ).mappings()
    return {(r["energy_source_id"], r["effective_year"]): dict(r) for r in rows}


# ---- F-01 대시보드 (FS-018f) ----
def daily_consumption(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> list[dict[str, Any]]:
    """최상위 계측기 기준 에너지원 × 단위 × 날짜별 소비량(invalid 제외, 배수 적용)."""
    rows = connection.execute(
        text(
            "SELECT e.id source_id,e.source_kind,c.unit,"
            "to_char((r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone,'YYYY-MM-DD') reading_date,"
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) quantity "
            + READING_FROM
            + READING_PERIOD
            + CONSUMPTION_ONLY
            + " GROUP BY e.id,e.source_kind,c.unit,reading_date ORDER BY reading_date"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def site_toe_target(connection: Connection, context: AuthContext, month: str) -> Any:
    # 사업장 전체 목표는 에너지원 NULL + TOE 단위다(FS-005g 5.5). 용수는 포함하지 않는다.
    return connection.execute(
        text(
            "SELECT sum(target_value) FROM fems.energy_target "
            "WHERE workspace_id=:w AND generation_id=:g AND target_scope='SITE' "
            "AND energy_source_id IS NULL AND unit='TOE' AND target_month=:m"
        ),
        {**_s(context), "m": month},
    ).scalar_one()


def monthly_consumption(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> list[dict[str, Any]]:
    """최상위 계측기 기준 에너지원 × 단위 × 월별 사용량(invalid 제외, 배수 적용)."""
    rows = connection.execute(
        text(
            "SELECT e.id source_id,e.source_code,e.name,e.is_billable,c.unit,"
            "to_char((r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone,'YYYY-MM') reading_month,"
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) quantity "
            + READING_FROM
            + READING_PERIOD
            + CONSUMPTION_ONLY
            + " GROUP BY e.id,e.source_code,e.name,e.is_billable,c.unit,reading_month"
            " ORDER BY e.source_code,reading_month"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def tariff_bands(
    connection: Connection, context: AuthContext, tariff_ids: list[int]
) -> dict[int, list[dict[str, Any]]]:
    """요금제별 시간대 구간. TOU 요금제가 아니면 빈 목록이다."""
    if not tariff_ids:
        return {}
    rows = connection.execute(
        text(
            "SELECT id,tariff_id,season,day_kind,hour_from,hour_to,load_band,rate "
            "FROM fems.tariff_band WHERE workspace_id=:w AND generation_id=:g "
            " AND tariff_id = ANY(:ids) ORDER BY season,day_kind,hour_from"
        ),
        {**_s(context), "ids": tariff_ids},
    ).mappings()
    grouped: dict[int, list[dict[str, Any]]] = {i: [] for i in tariff_ids}
    for row in rows:
        grouped[row["tariff_id"]].append(dict(row))
    return grouped


ALARM_RULE_COLUMNS = "id,code,name,alarm_kind,meter_channel_id,equipment_id,threshold,unit,is_active,created_at"


def alarm_rule_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "name": row["name"],
        "alarmKind": row["alarm_kind"],
        "meterChannelId": row["meter_channel_id"],
        "equipmentId": row["equipment_id"],
        "threshold": str(row["threshold"]),
        "unit": row["unit"],
        "isActive": row["is_active"],
        "createdAt": row["created_at"].isoformat(),
    }


def list_alarm_rules(
    connection: Connection, context: AuthContext, active_only: bool = False
) -> list[dict[str, Any]]:
    where = " AND is_active" if active_only else ""
    rows = connection.execute(
        text(
            f"SELECT {ALARM_RULE_COLUMNS} FROM fems.alarm_rule "
            f"WHERE workspace_id=:w AND generation_id=:g{where} ORDER BY code"
        ),
        _s(context),
    ).mappings()
    return [dict(r) for r in rows]


def insert_alarm_rule(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values.keys())
    placeholders = ",".join(f":{c}" for c in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.alarm_rule (workspace_id,generation_id,{columns}) "
                f"VALUES (:w,:g,{placeholders}) RETURNING {ALARM_RULE_COLUMNS}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return alarm_rule_dict(row)


def alarm_rule_code_taken(
    connection: Connection, context: AuthContext, code: str
) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM fems.alarm_rule "
                "WHERE workspace_id=:w AND generation_id=:g AND code=:code"
            ),
            {**_s(context), "code": code},
        ).first()
    )


ALARM_SQL = """
SELECT a.id,a.alarm_rule_id,r.code rule_code,r.name rule_name,r.alarm_kind,r.threshold,
       r.unit,a.raised_at,a.peak_value,a.status,a.acknowledged_at,a.cleared_at,
       c.channel_code,e.equipment_code
FROM fems.alarm a
JOIN fems.alarm_rule r ON r.workspace_id=a.workspace_id
 AND r.generation_id=a.generation_id AND r.id=a.alarm_rule_id
LEFT JOIN fems.meter_channel c ON c.workspace_id=r.workspace_id
 AND c.generation_id=r.generation_id AND c.id=r.meter_channel_id
LEFT JOIN fems.equipment e ON e.workspace_id=r.workspace_id
 AND e.generation_id=r.generation_id AND e.id=r.equipment_id
WHERE a.workspace_id=:w AND a.generation_id=:g
"""


def alarm_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "alarmRuleId": row["alarm_rule_id"],
        "ruleCode": row["rule_code"],
        "ruleName": row["rule_name"],
        "alarmKind": row["alarm_kind"],
        "threshold": str(row["threshold"]),
        "unit": row["unit"],
        "channelCode": row["channel_code"],
        "equipmentCode": row["equipment_code"],
        "raisedAt": row["raised_at"].isoformat(),
        "peakValue": str(row["peak_value"]),
        "status": row["status"],
        "acknowledgedAt": None
        if row["acknowledged_at"] is None
        else row["acknowledged_at"].isoformat(),
        "clearedAt": None
        if row["cleared_at"] is None
        else row["cleared_at"].isoformat(),
    }


def list_alarms(
    connection: Connection, context: AuthContext, open_only: bool = False
) -> list[dict[str, Any]]:
    where = " AND a.status <> 'CLEARED'" if open_only else ""
    rows = connection.execute(
        text(ALARM_SQL + where + " ORDER BY a.raised_at DESC, a.id DESC LIMIT 100"),
        _s(context),
    ).mappings()
    return [alarm_dict(r) for r in rows]


def get_alarm(
    connection: Connection, context: AuthContext, alarm_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(ALARM_SQL + " AND a.id=:id"), {**_s(context), "id": alarm_id}
        )
        .mappings()
        .first()
    )
    return None if row is None else alarm_dict(row)


def open_alarm_rule_ids(connection: Connection, context: AuthContext) -> set[int]:
    """진행 중(OPEN·ACK) 경보가 있는 규칙. 규칙당 한 건만 열어 둔다(UK_PARTIAL)."""
    return set(
        connection.execute(
            text(
                "SELECT alarm_rule_id FROM fems.alarm "
                "WHERE workspace_id=:w AND generation_id=:g AND status <> 'CLEARED'"
            ),
            _s(context),
        ).scalars()
    )


def raise_alarm(
    connection: Connection, context: AuthContext, rule_id: int, peak_value: str
) -> int:
    return connection.execute(
        text(
            "INSERT INTO fems.alarm (workspace_id,generation_id,alarm_rule_id,"
            "raised_at,peak_value,status) VALUES (:w,:g,:rule,now(),:peak,'OPEN') "
            "RETURNING id"
        ),
        {**_s(context), "rule": rule_id, "peak": peak_value},
    ).scalar_one()


def update_alarm_status(
    connection: Connection, context: AuthContext, alarm_id: int, status: str
) -> None:
    column = "acknowledged_at" if status == "ACK" else "cleared_at"
    connection.execute(
        text(
            f"UPDATE fems.alarm SET status=:status, {column}=now() "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": alarm_id, "status": status},
    )


def channel_ids_by_code(connection: Connection, context: AuthContext) -> dict[str, int]:
    """채널 코드 → id. CSV가 코드로 오므로 한 번에 읽어 둔다."""
    rows = connection.execute(
        text(
            "SELECT channel_code,id FROM fems.meter_channel "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active"
        ),
        _s(context),
    ).mappings()
    return {r["channel_code"]: r["id"] for r in rows}


def equipment_ids_by_code(
    connection: Connection, context: AuthContext
) -> dict[str, int]:
    """설비 코드 → id. MES 생산량을 FEMS 설비에 붙일 때 쓴다(FK 없음, 코드로만 맞춘다)."""
    rows = connection.execute(
        text(
            "SELECT equipment_code,id FROM fems.equipment "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active"
        ),
        _s(context),
    ).mappings()
    return {r["equipment_code"]: r["id"] for r in rows}


def insert_upload(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                "INSERT INTO fems.reading_upload (workspace_id,generation_id,upload_no,"
                "file_name,row_count,accepted_count,rejected_count,uploaded_at,error_summary) "
                "VALUES (:w,:g,:upload_no,:file_name,:row_count,:accepted,:rejected,now(),:errors) "
                "RETURNING id,upload_no,file_name,row_count,accepted_count,rejected_count,"
                "uploaded_at,error_summary"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return dict(row)


def next_upload_no(connection: Connection, context: AuthContext, day: str) -> str:
    taken = connection.execute(
        text(
            "SELECT count(*) FROM fems.reading_upload "
            "WHERE workspace_id=:w AND generation_id=:g AND upload_no LIKE :prefix"
        ),
        {**_s(context), "prefix": f"UP-{day}-%"},
    ).scalar_one()
    return f"UP-{day}-{taken + 1:03d}"


def list_uploads(
    connection: Connection, context: AuthContext, limit: int = 20
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT id,upload_no,file_name,row_count,accepted_count,rejected_count,"
            "uploaded_at,error_summary FROM fems.reading_upload "
            "WHERE workspace_id=:w AND generation_id=:g "
            "ORDER BY uploaded_at DESC, id DESC LIMIT :limit"
        ),
        {**_s(context), "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def production_keys(connection: Connection, context: AuthContext) -> set[str]:
    return set(
        connection.execute(
            text(
                "SELECT DISTINCT source_key FROM fems.production_record "
                "WHERE workspace_id=:w AND generation_id=:g"
            ),
            _s(context),
        ).scalars()
    )


def channel_for_reading(
    connection: Connection, context: AuthContext, channel_id: int
) -> dict[str, Any] | None:
    """계측 채널 하나. 수동 검침·보정이 단위와 채널 코드를 여기서 가져온다."""
    row = (
        connection.execute(
            text(
                "SELECT c.id,c.channel_code,c.name,c.unit,c.measurement_kind,c.is_active,"
                "m.meter_code,s.timezone "
                "FROM fems.meter_channel c "
                "JOIN fems.meter m ON m.workspace_id=c.workspace_id "
                " AND m.generation_id=c.generation_id AND m.id=c.meter_id "
                "JOIN fems.site s ON s.workspace_id=m.workspace_id "
                " AND s.generation_id=m.generation_id AND s.id=m.site_id "
                "WHERE c.workspace_id=:w AND c.generation_id=:g AND c.id=:id"
            ),
            {**_s(context), "id": channel_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else dict(row)


def channel_readings(
    connection: Connection,
    context: AuthContext,
    channel_id: int,
    date_from: Any,
    date_to: Any,
) -> list[dict[str, Any]]:
    """한 채널의 구간별 계측. 결측·이상값 탐지는 이 목록을 파이썬에서 훑는다.

    버려진 값(invalid)은 빼고 **구간마다 최신 input_revision 하나만** 돌려준다 —
    보정이 쌓여도 한 구간은 한 값이다.
    """
    rows = connection.execute(
        text(
            "SELECT DISTINCT ON (r.period_start) r.id,r.period_start,r.observed_at,"
            "r.value,r.quality,r.source_key,r.input_revision,r.entry_method "
            "FROM fems.energy_reading r "
            "JOIN fems.meter_channel c ON c.workspace_id=r.workspace_id "
            " AND c.generation_id=r.generation_id AND c.id=r.meter_channel_id "
            "JOIN fems.meter m ON m.workspace_id=c.workspace_id "
            " AND m.generation_id=c.generation_id AND m.id=c.meter_id "
            "JOIN fems.site s ON s.workspace_id=m.workspace_id "
            " AND s.generation_id=m.generation_id AND s.id=m.site_id "
            "WHERE r.workspace_id=:w AND r.generation_id=:g AND r.meter_channel_id=:id "
            " AND r.quality <> 'invalid'"
            " AND r.observed_at > (CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)"
            " AND r.observed_at <= (CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)"
            " ORDER BY r.period_start, r.input_revision DESC, r.id DESC"
        ),
        {**_s(context), "id": channel_id, "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def insert_reading(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values.keys())
    placeholders = ",".join(f":{c}" for c in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.energy_reading (workspace_id, generation_id, {columns}) "
                f"VALUES (:w, :g, {placeholders}) "
                "RETURNING id,meter_channel_id,observed_at,period_start,value,unit,"
                "quality,source_key,input_revision,entry_method,created_at"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return dict(row)


def supersede_reading(
    connection: Connection, context: AuthContext, reading_id: int
) -> None:
    """보정으로 대체된 원 계측을 **지우지 않고** 집계에서만 뺀다(quality=invalid).

    값은 행에 그대로 남고, 보정 이력(`reading_correction.original_value`)에도 남는다.
    집계 질의가 이미 invalid를 거르므로 읽는 쪽을 모두 고치지 않아도 된다.
    """
    connection.execute(
        text(
            "UPDATE fems.energy_reading SET quality='invalid' "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": reading_id},
    )


def insert_correction(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    row = (
        connection.execute(
            text(
                "INSERT INTO fems.reading_correction (workspace_id,generation_id,"
                "meter_channel_id,period_start,original_value,corrected_value,method,"
                "reason,corrected_at) VALUES (:w,:g,:channel,:period_start,:original,"
                ":corrected,:method,:reason,now()) "
                "RETURNING id,meter_channel_id,period_start,original_value,"
                "corrected_value,method,reason,corrected_at"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return dict(row)


def list_corrections(
    connection: Connection, context: AuthContext, limit: int = 50
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT k.id,k.meter_channel_id,c.channel_code,k.period_start,"
            "k.original_value,k.corrected_value,k.method,k.reason,k.corrected_at "
            "FROM fems.reading_correction k "
            "JOIN fems.meter_channel c ON c.workspace_id=k.workspace_id "
            " AND c.generation_id=k.generation_id AND c.id=k.meter_channel_id "
            "WHERE k.workspace_id=:w AND k.generation_id=:g "
            "ORDER BY k.corrected_at DESC, k.id DESC LIMIT :limit"
        ),
        {**_s(context), "limit": limit},
    ).mappings()
    return [dict(r) for r in rows]


def replace_tariff_bands(
    connection: Connection,
    context: AuthContext,
    tariff_id: int,
    rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """구간을 통째로 바꾼다. 한 줄씩 고치면 하루를 못 덮는 중간 상태가 생긴다."""
    connection.execute(
        text(
            "DELETE FROM fems.tariff_band "
            "WHERE workspace_id=:w AND generation_id=:g AND tariff_id=:t"
        ),
        {**_s(context), "t": tariff_id},
    )
    for row in rows:
        connection.execute(
            text(
                "INSERT INTO fems.tariff_band(workspace_id,generation_id,tariff_id,"
                "season,day_kind,hour_from,hour_to,load_band,rate) "
                "VALUES (:w,:g,:t,:season,:day_kind,:hour_from,:hour_to,:load_band,:rate)"
            ),
            {**_s(context), "t": tariff_id, **row},
        )
    return tariff_bands(connection, context, [tariff_id])[tariff_id]


def holidays(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> set[Any]:
    """그 기간의 휴일. core가 가진 공통 달력이고 FK 없이 날짜로만 읽는다(DSN-16 Q1)."""
    return set(
        connection.execute(
            text(
                "SELECT holiday_on FROM core.holiday "
                "WHERE workspace_id=:w AND generation_id=:g "
                " AND holiday_on BETWEEN CAST(:date_from AS date) AND CAST(:date_to AS date)"
            ),
            {**_s(context), "date_from": date_from, "date_to": date_to},
        ).scalars()
    )


def hourly_consumption(
    connection: Connection,
    context: AuthContext,
    date_from: Any,
    date_to: Any,
    energy_source_id: int | None = None,
) -> list[dict[str, Any]]:
    """최상위 계측기 기준 **사업장 시각별** 사용량. TOU 요금과 부하 패턴·피크가 함께 쓴다.

    계측이 1시간 단위라 시간 사용량(kWh)이 곧 그 시간의 평균 kW다 — 수요전력을 이렇게
    근사한다(DSN-15 Q2). 구간 끝이 정시라 1마이크로초를 빼고 그 시각이 속한 시간으로 센다.
    """
    local = "(r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone"
    where = " AND e.id=:energy_source_id" if energy_source_id is not None else ""
    rows = connection.execute(
        text(
            f"SELECT e.id source_id,e.source_code,e.name,e.is_billable,c.unit,"
            f"CAST({local} AS date) reading_date,"
            f'CAST(extract(hour FROM {local}) AS integer) AS "hour",'
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) quantity "
            + READING_FROM
            + READING_PERIOD
            + CONSUMPTION_ONLY
            + where
            + ' GROUP BY e.id,e.source_code,e.name,e.is_billable,c.unit,reading_date,"hour"'
            ' ORDER BY e.source_code,reading_date,"hour"'
        ),
        {
            **_s(context),
            "date_from": date_from,
            "date_to": date_to,
            **(
                {"energy_source_id": energy_source_id}
                if energy_source_id is not None
                else {}
            ),
        },
    ).mappings()
    return [dict(r) for r in rows]


def billing_tariffs(
    connection: Connection, context: AuthContext
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT id,energy_source_id,tariff_code,name,basic_charge,usage_rate,"
            "effective_from,effective_to,tariff_kind,contract_kw FROM fems.tariff "
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY effective_from DESC"
        ),
        _s(context),
    ).mappings()
    return [dict(r) for r in rows]


def quality_issues(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> tuple[int, list[dict[str, Any]]]:
    """정상(valid)이 아닌 계측값. 하위 계측기를 포함한 모든 채널이 대상이다."""
    # 보정으로 대체된 원본(invalid)은 보정본(estimated)과 같은 구간이라 이중으로 세지 않는다.
    where = (
        READING_FROM
        + READING_PERIOD
        + " AND r.quality<>'valid' AND NOT (r.quality='invalid' AND EXISTS ("
        "SELECT 1 FROM fems.reading_correction rc WHERE rc.workspace_id=r.workspace_id"
        " AND rc.generation_id=r.generation_id AND rc.meter_channel_id=r.meter_channel_id"
        " AND rc.period_start=r.period_start))"
    )
    params = {**_s(context), "date_from": date_from, "date_to": date_to}
    count = connection.execute(text("SELECT count(*) " + where), params).scalar_one()
    rows = connection.execute(
        text(
            "SELECT r.observed_at,r.quality,s.timezone,c.name channel_name "
            + where
            + " ORDER BY r.observed_at DESC, c.channel_code LIMIT 5"
        ),
        params,
    ).mappings()
    return count, [
        {
            "observedAt": r["observed_at"].isoformat(),
            "timezone": r["timezone"],
            "channelName": r["channel_name"],
            "quality": r["quality"],
        }
        for r in rows
    ]


# ---- F-07 목표 대비 실적 (FS-018g) ----
def targets_for_month(
    connection: Connection, context: AuthContext, month: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            """
            SELECT t.id,t.target_scope,t.equipment_id,t.energy_source_id,t.target_value,t.unit,
                   e.source_code,e.name source_name,q.equipment_code,q.name equipment_name
            FROM fems.energy_target t
            LEFT JOIN fems.energy_source e
              ON e.workspace_id=t.workspace_id AND e.generation_id=t.generation_id AND e.id=t.energy_source_id
            LEFT JOIN fems.equipment q
              ON q.workspace_id=t.workspace_id AND q.generation_id=t.generation_id AND q.id=t.equipment_id
            WHERE t.workspace_id=:w AND t.generation_id=:g AND t.target_month=:m
            ORDER BY t.target_scope, e.source_code NULLS LAST, q.equipment_code
            """
        ),
        {**_s(context), "m": month},
    ).mappings()
    return [dict(r) for r in rows]


def active_sources(
    connection: Connection, context: AuthContext
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT id,source_code,name,measure_unit FROM fems.energy_source "
            "WHERE workspace_id=:w AND generation_id=:g AND is_active ORDER BY source_code"
        ),
        _s(context),
    ).mappings()
    return [dict(r) for r in rows]


# ---- F-05 생산량 등록 (FS-018i) ----
# 버전 규칙: 같은 source_key의 새 version_no가 개정이다. 확정 행은 바꾸지 않는다.
PRODUCTION_BASE = """
SELECT p.id,p.source_key,p.version_no,p.equipment_id,q.equipment_code,q.name equipment_name,
       q.equipment_type,
       p.item_code,p.period_start,p.period_end,p.production_qty,p.unit,p.status,p.confirmed_at,
       s.timezone,
       p.version_no = max(p.version_no) OVER (PARTITION BY p.source_key) is_latest,
       p.status='confirmed' AND p.version_no = max(p.version_no)
         FILTER (WHERE p.status='confirmed') OVER (PARTITION BY p.source_key) is_effective
FROM fems.production_record p
JOIN fems.equipment q
  ON q.workspace_id=p.workspace_id AND q.generation_id=p.generation_id AND q.id=p.equipment_id
JOIN fems.location l
  ON l.workspace_id=q.workspace_id AND l.generation_id=q.generation_id AND l.id=q.location_id
JOIN fems.site s
  ON s.workspace_id=l.workspace_id AND s.generation_id=l.generation_id AND s.id=l.site_id
WHERE p.workspace_id=:w AND p.generation_id=:g
"""


def production_dict(row: Any) -> dict[str, Any]:
    zone = ZoneInfo(row["timezone"])
    return {
        "id": row["id"],
        "sourceKey": row["source_key"],
        "versionNo": row["version_no"],
        "equipmentId": row["equipment_id"],
        "equipmentCode": row["equipment_code"],
        "equipmentName": row["equipment_name"],
        "itemCode": row["item_code"],
        "startDate": row["period_start"].astimezone(zone).date().isoformat(),
        # 종료는 반개구간 끝이므로 하루를 빼 포함 날짜로 보여 준다.
        "endDate": (row["period_end"] - timedelta(microseconds=1))
        .astimezone(zone)
        .date()
        .isoformat(),
        "periodStart": row["period_start"].isoformat(),
        "periodEnd": row["period_end"].isoformat(),
        "productionQty": str(row["production_qty"]),
        "unit": row["unit"],
        "status": row["status"],
        "confirmedAt": row["confirmed_at"].isoformat() if row["confirmed_at"] else None,
        "isLatest": row["is_latest"],
        "isEffective": bool(row["is_effective"]),
    }


def list_production(
    connection: Connection,
    context: AuthContext,
    filters: dict[str, Any],
    include_history: bool,
    offset: int,
    limit: int,
) -> tuple[list[dict[str, Any]], int]:
    where = "WHERE TRUE" if include_history else "WHERE x.is_latest"
    params: dict[str, Any] = {**_s(context), "offset": offset, "limit": limit}
    if "equipment_id" in filters:
        where += " AND x.equipment_id=:equipment_id"
    if "status" in filters:
        where += " AND x.status=:status"
    if "item_code" in filters:
        where += " AND x.item_code=:item_code"
    params.update(filters)
    scope = f"SELECT * FROM ({PRODUCTION_BASE}) x {where}"
    total = connection.execute(
        text(f"SELECT count(*) FROM ({scope}) y"), params
    ).scalar_one()
    rows = connection.execute(
        text(
            scope + " ORDER BY x.period_start DESC, x.source_key, x.version_no DESC"
            " OFFSET :offset LIMIT :limit"
        ),
        params,
    ).mappings()
    return [production_dict(r) for r in rows], total


def get_production(
    connection: Connection, context: AuthContext, record_id: int, lock: bool = False
) -> dict[str, Any] | None:
    if lock:
        # 같은 행을 바꾸려는 요청을 직렬화한다(공간 잠금 안에서도 명시한다).
        connection.execute(
            text(
                "SELECT 1 FROM fems.production_record "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id FOR UPDATE"
            ),
            {**_s(context), "id": record_id},
        )
    row = (
        connection.execute(
            text(f"SELECT * FROM ({PRODUCTION_BASE}) x WHERE x.id=:id"),
            {**_s(context), "id": record_id},
        )
        .mappings()
        .one_or_none()
    )
    return production_dict(row) if row else None


def site_timezone_of_equipment(
    connection: Connection, context: AuthContext, equipment_id: int
) -> str | None:
    return connection.execute(
        text(
            """
            SELECT s.timezone FROM fems.equipment q
            JOIN fems.location l
              ON l.workspace_id=q.workspace_id AND l.generation_id=q.generation_id AND l.id=q.location_id
            JOIN fems.site s
              ON s.workspace_id=l.workspace_id AND s.generation_id=l.generation_id AND s.id=l.site_id
            WHERE q.workspace_id=:w AND q.generation_id=:g AND q.id=:id
            """
        ),
        {**_s(context), "id": equipment_id},
    ).scalar_one_or_none()


def next_manual_source_key(
    connection: Connection, context: AuthContext, day: str
) -> str:
    """직접 입력 원천 키 MAN-YYYYMMDD-NNN. 공간 잠금 안에서 부르므로 순번이 겹치지 않는다."""
    prefix = f"MAN-{day}-"
    count = connection.execute(
        text(
            "SELECT count(DISTINCT source_key) FROM fems.production_record "
            "WHERE workspace_id=:w AND generation_id=:g AND source_key LIKE :p"
        ),
        {**_s(context), "p": prefix + "%"},
    ).scalar_one()
    return f"{prefix}{count + 1:03d}"


def insert_production(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> int:
    return connection.execute(
        text(
            """
            INSERT INTO fems.production_record
              (workspace_id,generation_id,source_key,version_no,equipment_id,item_code,
               period_start,period_end,production_qty,unit,status)
            VALUES (:w,:g,:source_key,:version_no,:equipment_id,:item_code,
                    :period_start,:period_end,:production_qty,:unit,'draft')
            RETURNING id
            """
        ),
        {**_s(context), **values},
    ).scalar_one()


def update_production(
    connection: Connection, context: AuthContext, record_id: int, values: dict[str, Any]
) -> None:
    assignments = ",".join(f"{column}=:{column}" for column in values)
    connection.execute(
        text(
            f"UPDATE fems.production_record SET {assignments} "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id AND status='draft'"
        ),
        {**_s(context), **values, "id": record_id},
    )


def delete_production(
    connection: Connection, context: AuthContext, record_id: int
) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.production_record "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id AND status='draft'"
        ),
        {**_s(context), "id": record_id},
    )


def confirm_production(
    connection: Connection, context: AuthContext, record_id: int
) -> None:
    connection.execute(
        text(
            "UPDATE fems.production_record SET status='confirmed', confirmed_at=now() "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id AND status='draft'"
        ),
        {**_s(context), "id": record_id},
    )


def overlapping_production(
    connection: Connection, context: AuthContext, record: dict[str, Any]
) -> list[dict[str, Any]]:
    """다른 원천 키의 현재 확정 기록 중 같은 설비·품목·단위이고 구간이 겹치는 것."""
    rows = connection.execute(
        text(
            f"""
            SELECT * FROM ({PRODUCTION_BASE}) x
            WHERE x.is_effective AND x.source_key<>:key
              AND x.equipment_id=:equipment AND x.item_code=:item AND x.unit=:unit
              AND x.period_start < CAST(:end AS timestamptz)
              AND CAST(:start AS timestamptz) < x.period_end
            ORDER BY x.period_start
            """
        ),
        {
            **_s(context),
            "key": record["sourceKey"],
            "equipment": record["equipmentId"],
            "item": record["itemCode"],
            "unit": record["unit"],
            "start": record["periodStart"],
            "end": record["periodEnd"],
        },
    ).mappings()
    return [production_dict(r) for r in rows]


def source_versions(
    connection: Connection, context: AuthContext, source_key: str
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT version_no,status FROM fems.production_record "
            "WHERE workspace_id=:w AND generation_id=:g AND source_key=:k ORDER BY version_no"
        ),
        {**_s(context), "k": source_key},
    ).mappings()
    return [dict(r) for r in rows]


# ---- F-06 원단위 분석 (FS-018j) ----
def effective_production(
    connection: Connection, context: AuthContext
) -> list[dict[str, Any]]:
    """원천 키별 최신 확정 버전(원단위 분모 후보). 초안·이전 버전은 제외한다."""
    rows = connection.execute(
        text(f"SELECT * FROM ({PRODUCTION_BASE}) x WHERE x.is_effective"),
        _s(context),
    ).mappings()
    return [{**production_dict(r), "equipmentType": r["equipment_type"]} for r in rows]


def current_allocations(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> list[dict[str, Any]]:
    """기간 안의 현재 배분 결과(invalid 제외). 원단위 분자 후보."""
    rows = connection.execute(
        text(
            f"SELECT * FROM ({_allocation_scope({})}) z "
            "WHERE z.is_latest AND z.quality<>'invalid'"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]


def item_baselines(
    connection: Connection, context: AuthContext
) -> dict[str, dict[str, Any]]:
    """품목별 확정 기준선 중 가장 최근 기간. 초안은 비교에 쓰지 않는다."""
    rows = connection.execute(
        text(
            """
            SELECT DISTINCT ON (b.item_code)
                   b.item_code,b.baseline_code,b.baseline_value,b.unit,b.period_from,b.period_to,
                   e.source_code
            FROM fems.energy_baseline b
            LEFT JOIN fems.energy_source e
              ON e.workspace_id=b.workspace_id AND e.generation_id=b.generation_id AND e.id=b.energy_source_id
            WHERE b.workspace_id=:w AND b.generation_id=:g
              AND b.baseline_scope='ITEM' AND b.status='confirmed'
            ORDER BY b.item_code, b.period_to DESC, b.baseline_code DESC
            """
        ),
        _s(context),
    ).mappings()
    return {r["item_code"]: dict(r) for r in rows}


# ---- F-19·F-20·F-21 에너지 경영 (DSN-15 F32·F33·F35) ----

SAVING_COLUMNS = (
    "id,code,title,equipment_id,energy_source_id,expected_saving,investment,currency,"
    "start_on,baseline_start_on,baseline_end_on,review_end_on,measured_saving,status,"
    "verified_at,created_at"
)


def saving_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "code": row["code"],
        "title": row["title"],
        "equipmentId": row["equipment_id"],
        "energySourceId": row["energy_source_id"],
        "expectedSaving": str(row["expected_saving"]),
        "investment": str(row["investment"]),
        "currency": row["currency"],
        "startOn": row["start_on"].isoformat(),
        "baselineStartOn": row["baseline_start_on"].isoformat(),
        "baselineEndOn": row["baseline_end_on"].isoformat(),
        "reviewEndOn": None
        if row["review_end_on"] is None
        else row["review_end_on"].isoformat(),
        "measuredSaving": None
        if row["measured_saving"] is None
        else str(row["measured_saving"]),
        "status": row["status"],
        "verifiedAt": None
        if row["verified_at"] is None
        else row["verified_at"].isoformat(),
    }


def list_savings(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {SAVING_COLUMNS} FROM fems.saving_project "
            "WHERE workspace_id=:w AND generation_id=:g ORDER BY start_on DESC, code"
        ),
        _s(context),
    ).mappings()
    return [saving_dict(r) for r in rows]


def get_saving(
    connection: Connection, context: AuthContext, saving_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {SAVING_COLUMNS} FROM fems.saving_project "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": saving_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else saving_dict(row)


def insert_saving(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> dict[str, Any]:
    columns = ",".join(values.keys())
    placeholders = ",".join(f":{c}" for c in values)
    row = (
        connection.execute(
            text(
                f"INSERT INTO fems.saving_project (workspace_id,generation_id,{columns}) "
                f"VALUES (:w,:g,{placeholders}) RETURNING {SAVING_COLUMNS}"
            ),
            {**_s(context), **values},
        )
        .mappings()
        .one()
    )
    return saving_dict(row)


def update_saving(
    connection: Connection, context: AuthContext, saving_id: int, values: dict[str, Any]
) -> dict[str, Any]:
    sets = ",".join(f"{k}=:{k}" for k in values)
    row = (
        connection.execute(
            text(
                f"UPDATE fems.saving_project SET {sets} "
                f"WHERE workspace_id=:w AND generation_id=:g AND id=:id "
                f"RETURNING {SAVING_COLUMNS}"
            ),
            {**_s(context), "id": saving_id, **values},
        )
        .mappings()
        .one()
    )
    return saving_dict(row)


def next_version(
    connection: Connection, context: AuthContext, table: str, column: str, value: str
) -> int:
    """같은 기간의 다음 버전 번호. 확정본이 있어도 새 버전은 초안으로 시작한다."""
    taken = connection.execute(
        text(
            f"SELECT coalesce(max(version),0) FROM fems.{table} "
            f"WHERE workspace_id=:w AND generation_id=:g AND {column}=:value"
        ),
        {**_s(context), "value": value},
    ).scalar_one()
    return taken + 1


def drop_drafts(
    connection: Connection,
    context: AuthContext,
    table: str,
    column: str,
    value: str,
    child: tuple[str, str] | None = None,
) -> None:
    """같은 기간의 옛 **초안**을 지운다. 확정본은 건드리지 않는다(불변).

    초안을 `superseded`로 돌릴 수 없다 — CHECK가 `(status='draft') = (confirmed_at IS NULL)`
    이라 확정한 적 없는 행은 draft여야 한다. 확정 전 초안은 기록이 아니라 작업 중인 계산이다.
    `child`는 (자식 표, 부모 id 칼럼)이다 — 부모를 지우기 전에 자식부터 지운다(RESTRICT).
    """
    scope = "workspace_id=:w AND generation_id=:g"
    ids = f"SELECT id FROM fems.{table} WHERE {scope} AND {column}=:value AND status='draft'"
    if child:
        connection.execute(
            text(
                f"DELETE FROM fems.{child[0]} WHERE {scope} AND {child[1]} IN ({ids})"
            ),
            {**_s(context), "value": value},
        )
    connection.execute(
        text(
            f"DELETE FROM fems.{table} WHERE {scope} AND {column}=:value AND status='draft'"
        ),
        {**_s(context), "value": value},
    )


def confirm_snapshot(
    connection: Connection,
    context: AuthContext,
    table: str,
    column: str,
    row_id: int,
) -> None:
    """초안을 확정한다. 같은 기간의 기존 확정본은 `superseded`로 넘긴다(새 버전이 이긴다)."""
    scope = "workspace_id=:w AND generation_id=:g"
    params = {**_s(context), "id": row_id}
    connection.execute(
        text(
            f"UPDATE fems.{table} SET status='superseded' WHERE {scope} AND status='confirmed' "
            f"AND {column}=(SELECT {column} FROM fems.{table} WHERE {scope} AND id=:id)"
        ),
        params,
    )
    connection.execute(
        text(
            f"UPDATE fems.{table} SET status='confirmed', confirmed_at=now() "
            f"WHERE {scope} AND id=:id"
        ),
        params,
    )


def reading_coverage(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> dict[str, Any]:
    """기간에 계측이 **있는 날**이 며칠인지. 최상위 계측기 기준이다.

    확정 명세서·검토가 연·월 전체를 덮는지 알려면 필요하다 — 시드처럼 한 달치뿐이면
    '연간 명세서'라는 이름이 거짓이 된다.
    """
    local = "(r.observed_at - interval '1 microsecond') AT TIME ZONE s.timezone"
    row = (
        connection.execute(
            text(
                f"SELECT count(DISTINCT CAST({local} AS date)) days, "
                f"min(CAST({local} AS date)) first_day, max(CAST({local} AS date)) last_day "
                + READING_FROM
                + READING_PERIOD
                + CONSUMPTION_ONLY
            ),
            {**_s(context), "date_from": date_from, "date_to": date_to},
        )
        .mappings()
        .one()
    )
    return {
        "days": row["days"],
        "from": None if row["first_day"] is None else row["first_day"].isoformat(),
        "to": None if row["last_day"] is None else row["last_day"].isoformat(),
    }


REVIEW_COLUMNS = (
    "id,review_month,version,status,primary_energy_toe,energy_cost,currency,"
    "emission_tco2e,target_achievement,issues,confirmed_at,created_at"
)


def review_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "reviewMonth": row["review_month"],
        "version": row["version"],
        "status": row["status"],
        "primaryEnergyToe": str(row["primary_energy_toe"]),
        "energyCost": str(row["energy_cost"]),
        "currency": row["currency"],
        "emissionTco2e": str(row["emission_tco2e"]),
        # 목표가 없으면 0%가 아니라 모름이다.
        "targetAchievement": None
        if row["target_achievement"] is None
        else str(row["target_achievement"]),
        "issues": row["issues"],
        "confirmedAt": None
        if row["confirmed_at"] is None
        else row["confirmed_at"].isoformat(),
        "createdAt": row["created_at"].isoformat(),
    }


def list_reviews(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {REVIEW_COLUMNS} FROM fems.energy_review "
            "WHERE workspace_id=:w AND generation_id=:g "
            "ORDER BY review_month DESC, version DESC LIMIT 60"
        ),
        _s(context),
    ).mappings()
    return [review_dict(r) for r in rows]


def get_review(
    connection: Connection, context: AuthContext, review_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {REVIEW_COLUMNS} FROM fems.energy_review "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": review_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else review_dict(row)


def insert_review(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> int:
    columns = ",".join(values.keys())
    placeholders = ",".join(f":{c}" for c in values)
    return connection.execute(
        text(
            f"INSERT INTO fems.energy_review (workspace_id,generation_id,{columns}) "
            f"VALUES (:w,:g,{placeholders}) RETURNING id"
        ),
        {**_s(context), **values},
    ).scalar_one()


GHG_COLUMNS = (
    "id,inventory_year,version,status,scope1_tco2e,scope2_tco2e,confirmed_at,created_at"
)


def ghg_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "inventoryYear": row["inventory_year"],
        "version": row["version"],
        "status": row["status"],
        "scope1Tco2e": str(row["scope1_tco2e"]),
        "scope2Tco2e": str(row["scope2_tco2e"]),
        "confirmedAt": None
        if row["confirmed_at"] is None
        else row["confirmed_at"].isoformat(),
        "createdAt": row["created_at"].isoformat(),
    }


def list_ghg(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {GHG_COLUMNS} FROM fems.ghg_inventory "
            "WHERE workspace_id=:w AND generation_id=:g "
            "ORDER BY inventory_year DESC, version DESC LIMIT 30"
        ),
        _s(context),
    ).mappings()
    return [ghg_dict(r) for r in rows]


def get_ghg(
    connection: Connection, context: AuthContext, ghg_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {GHG_COLUMNS} FROM fems.ghg_inventory "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": ghg_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    lines = connection.execute(
        text(
            "SELECT l.scope,l.activity_qty,l.unit,l.factor_value,l.emission_tco2e,"
            "q.equipment_code,q.name equipment_name,s.source_code,s.name source_name "
            "FROM fems.ghg_inventory_line l "
            "JOIN fems.energy_source s ON s.workspace_id=l.workspace_id "
            " AND s.generation_id=l.generation_id AND s.id=l.energy_source_id "
            "LEFT JOIN fems.equipment q ON q.workspace_id=l.workspace_id "
            " AND q.generation_id=l.generation_id AND q.id=l.equipment_id "
            "WHERE l.workspace_id=:w AND l.generation_id=:g AND l.ghg_inventory_id=:id "
            "ORDER BY l.scope, s.source_code, q.equipment_code NULLS LAST"
        ),
        {**_s(context), "id": ghg_id},
    ).mappings()
    return {
        **ghg_dict(row),
        "lines": [
            {
                "scope": ln["scope"],
                "equipmentCode": ln["equipment_code"],
                "equipmentName": ln["equipment_name"],
                "sourceCode": ln["source_code"],
                "sourceName": ln["source_name"],
                "activityQty": str(ln["activity_qty"]),
                "unit": ln["unit"],
                "factorValue": str(ln["factor_value"]),
                "emissionTco2e": str(ln["emission_tco2e"]),
            }
            for ln in lines
        ],
    }


def insert_ghg(
    connection: Connection,
    context: AuthContext,
    values: dict[str, Any],
    lines: list[dict[str, Any]],
) -> int:
    ghg_id = connection.execute(
        text(
            "INSERT INTO fems.ghg_inventory (workspace_id,generation_id,inventory_year,"
            "version,status,scope1_tco2e,scope2_tco2e) "
            "VALUES (:w,:g,:year,:version,'draft',:scope1,:scope2) RETURNING id"
        ),
        {**_s(context), **values},
    ).scalar_one()
    for line in lines:
        connection.execute(
            text(
                "INSERT INTO fems.ghg_inventory_line (workspace_id,generation_id,"
                "ghg_inventory_id,equipment_id,energy_source_id,scope,activity_qty,unit,"
                "factor_value,emission_tco2e) VALUES (:w,:g,:inv,:equipment,:source,:scope,"
                ":qty,:unit,:factor,:emission)"
            ),
            {**_s(context), "inv": ghg_id, **line},
        )
    return ghg_id


def saving_code_taken(connection: Connection, context: AuthContext, code: str) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM fems.saving_project "
                "WHERE workspace_id=:w AND generation_id=:g AND code=:code"
            ),
            {**_s(context), "code": code},
        ).first()
    )


# ---- F-22 비용 배분·F-23 고지서 대조 (DSN-15 F43·F42) ----


def equipment_departments(
    connection: Connection, context: AuthContext
) -> dict[int, str | None]:
    rows = connection.execute(
        text(
            "SELECT id,department_code FROM fems.equipment "
            "WHERE workspace_id=:w AND generation_id=:g"
        ),
        _s(context),
    ).mappings()
    return {r["id"]: r["department_code"] for r in rows}


def main_items(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> dict[int, str]:
    """설비별로 그 기간 **생산량이 가장 많은 품목**. 유효 확정본만 센다."""
    rows = connection.execute(
        text(
            """
            SELECT equipment_id, item_code, sum(production_qty) qty
            FROM (
              SELECT p.equipment_id, p.item_code, p.production_qty,
                     p.status='confirmed' AND p.version_no = max(p.version_no)
                       FILTER (WHERE p.status='confirmed')
                       OVER (PARTITION BY p.source_key) is_effective
              FROM fems.production_record p
              JOIN fems.equipment q ON q.workspace_id=p.workspace_id
               AND q.generation_id=p.generation_id AND q.id=p.equipment_id
              JOIN fems.location l ON l.workspace_id=q.workspace_id
               AND l.generation_id=q.generation_id AND l.id=q.location_id
              JOIN fems.site s ON s.workspace_id=l.workspace_id
               AND s.generation_id=l.generation_id AND s.id=l.site_id
              WHERE p.workspace_id=:w AND p.generation_id=:g
                AND p.period_start < (CAST(CAST(:date_to AS date) + 1 AS timestamp) AT TIME ZONE s.timezone)
                AND p.period_end > (CAST(CAST(:date_from AS date) AS timestamp) AT TIME ZONE s.timezone)
            ) z
            WHERE z.is_effective
            GROUP BY equipment_id, item_code
            """
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    best: dict[int, tuple[Any, str]] = {}
    for r in rows:
        if r["equipment_id"] not in best or r["qty"] > best[r["equipment_id"]][0]:
            best[r["equipment_id"]] = (r["qty"], r["item_code"])
    return {k: v[1] for k, v in best.items()}


COST_COLUMNS = "id,cost_month,version,status,confirmed_at,created_at"


def cost_run_dict(row: Any) -> dict[str, Any]:
    return {
        "id": row["id"],
        "costMonth": row["cost_month"],
        "version": row["version"],
        "status": row["status"],
        "confirmedAt": None
        if row["confirmed_at"] is None
        else row["confirmed_at"].isoformat(),
        "createdAt": row["created_at"].isoformat(),
    }


def list_cost_runs(
    connection: Connection, context: AuthContext
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {COST_COLUMNS} FROM fems.cost_run "
            "WHERE workspace_id=:w AND generation_id=:g "
            "ORDER BY cost_month DESC, version DESC LIMIT 60"
        ),
        _s(context),
    ).mappings()
    return [cost_run_dict(r) for r in rows]


def cost_lines(
    connection: Connection, context: AuthContext, run_id: int
) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            "SELECT l.department_code,l.item_code,l.quantity,l.unit,l.cost,"
            "q.equipment_code,q.name equipment_name,s.source_code,s.name source_name "
            "FROM fems.cost_allocation_line l "
            "JOIN fems.equipment q ON q.workspace_id=l.workspace_id "
            " AND q.generation_id=l.generation_id AND q.id=l.equipment_id "
            "JOIN fems.energy_source s ON s.workspace_id=l.workspace_id "
            " AND s.generation_id=l.generation_id AND s.id=l.energy_source_id "
            "WHERE l.workspace_id=:w AND l.generation_id=:g AND l.cost_run_id=:id "
            "ORDER BY l.cost DESC, q.equipment_code, s.source_code"
        ),
        {**_s(context), "id": run_id},
    ).mappings()
    return [
        {
            "equipmentCode": r["equipment_code"],
            "equipmentName": r["equipment_name"],
            "sourceCode": r["source_code"],
            "sourceName": r["source_name"],
            "departmentCode": r["department_code"],
            "itemCode": r["item_code"],
            "quantity": str(r["quantity"]),
            "unit": r["unit"],
            "cost": str(r["cost"]),
        }
        for r in rows
    ]


def get_cost_run(
    connection: Connection, context: AuthContext, run_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {COST_COLUMNS} FROM fems.cost_run "
                "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
            ),
            {**_s(context), "id": run_id},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return {**cost_run_dict(row), "lines": cost_lines(connection, context, run_id)}


def insert_cost_run(
    connection: Connection,
    context: AuthContext,
    month: str,
    version: int,
    lines: list[dict[str, Any]],
) -> int:
    run_id = connection.execute(
        text(
            "INSERT INTO fems.cost_run (workspace_id,generation_id,cost_month,version,status) "
            "VALUES (:w,:g,:month,:version,'draft') RETURNING id"
        ),
        {**_s(context), "month": month, "version": version},
    ).scalar_one()
    for line in lines:
        connection.execute(
            text(
                "INSERT INTO fems.cost_allocation_line (workspace_id,generation_id,"
                "cost_run_id,equipment_id,energy_source_id,department_code,item_code,"
                "quantity,unit,cost,currency) VALUES (:w,:g,:run,:equipment,:source,"
                ":department,:item,:qty,:unit,:cost,'KRW')"
            ),
            {**_s(context), "run": run_id, **line},
        )
    return run_id


BILL_COLUMNS = (
    "b.id,b.energy_source_id,s.source_code,s.name source_name,b.bill_month,"
    "b.billed_qty,b.billed_amount,b.calculated_amount,b.currency,b.note"
)


def bill_dict(row: Any) -> dict[str, Any]:
    billed, calculated = row["billed_amount"], row["calculated_amount"]
    diff = billed - calculated
    return {
        "id": row["id"],
        "energySourceId": row["energy_source_id"],
        "sourceCode": row["source_code"],
        "sourceName": row["source_name"],
        "billMonth": row["bill_month"],
        "billedQty": str(row["billed_qty"]),
        "billedAmount": str(billed),
        "calculatedAmount": str(calculated),
        "difference": str(diff),
        # 산정이 0이면 비율을 낼 수 없다. 0%가 아니라 모름이다.
        "differenceRate": None
        if calculated == 0
        else str((diff * 100 / calculated).quantize(Decimal("0.1"))),
        "currency": row["currency"],
        "note": row["note"],
    }


def list_bills(connection: Connection, context: AuthContext) -> list[dict[str, Any]]:
    rows = connection.execute(
        text(
            f"SELECT {BILL_COLUMNS} FROM fems.utility_bill b "
            "JOIN fems.energy_source s ON s.workspace_id=b.workspace_id "
            " AND s.generation_id=b.generation_id AND s.id=b.energy_source_id "
            "WHERE b.workspace_id=:w AND b.generation_id=:g "
            "ORDER BY b.bill_month DESC, s.source_code LIMIT 120"
        ),
        _s(context),
    ).mappings()
    return [bill_dict(r) for r in rows]


def get_bill(
    connection: Connection, context: AuthContext, bill_id: int
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            text(
                f"SELECT {BILL_COLUMNS} FROM fems.utility_bill b "
                "JOIN fems.energy_source s ON s.workspace_id=b.workspace_id "
                " AND s.generation_id=b.generation_id AND s.id=b.energy_source_id "
                "WHERE b.workspace_id=:w AND b.generation_id=:g AND b.id=:id"
            ),
            {**_s(context), "id": bill_id},
        )
        .mappings()
        .first()
    )
    return None if row is None else bill_dict(row)


def bill_taken(
    connection: Connection, context: AuthContext, source_id: int, month: str
) -> bool:
    return bool(
        connection.execute(
            text(
                "SELECT 1 FROM fems.utility_bill WHERE workspace_id=:w AND generation_id=:g "
                "AND energy_source_id=:s AND bill_month=:m"
            ),
            {**_s(context), "s": source_id, "m": month},
        ).first()
    )


def insert_bill(
    connection: Connection, context: AuthContext, values: dict[str, Any]
) -> int:
    return connection.execute(
        text(
            "INSERT INTO fems.utility_bill (workspace_id,generation_id,energy_source_id,"
            "bill_month,billed_qty,billed_amount,calculated_amount,currency,note) "
            "VALUES (:w,:g,:source,:month,:qty,:billed,:calculated,'KRW',:note) RETURNING id"
        ),
        {**_s(context), **values},
    ).scalar_one()


def delete_bill(connection: Connection, context: AuthContext, bill_id: int) -> None:
    connection.execute(
        text(
            "DELETE FROM fems.utility_bill "
            "WHERE workspace_id=:w AND generation_id=:g AND id=:id"
        ),
        {**_s(context), "id": bill_id},
    )


def generation_quantity(
    connection: Connection, context: AuthContext, date_from: Any, date_to: Any
) -> list[dict[str, Any]]:
    """발전 에너지원의 기간 발전량. 소비 집계는 이것을 일부러 뺀다(`CONSUMPTION_ONLY`)."""
    rows = connection.execute(
        text(
            "SELECT e.source_code,e.name,c.unit,"
            "coalesce(sum(r.value*c.multiplier) FILTER (WHERE r.quality<>'invalid'),0) quantity "
            + READING_FROM
            + READING_PERIOD
            + " AND e.source_kind='GENERATION' GROUP BY e.source_code,e.name,c.unit "
            "ORDER BY e.source_code"
        ),
        {**_s(context), "date_from": date_from, "date_to": date_to},
    ).mappings()
    return [dict(r) for r in rows]
