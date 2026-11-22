from __future__ import annotations
# ruff: noqa: I001

from collections import defaultdict
import json
from datetime import UTC, date, datetime
from time import perf_counter
from typing import Any
from uuid import NAMESPACE_URL, uuid5

from sqlalchemy import MetaData, inspect, text, update
from sqlalchemy.engine import Connection

from fs.common.modules import BUSINESS_SCHEMAS
from seed.common import SEED_VERSION, at


SCHEMAS = BUSINESS_SCHEMAS  # 업무 스키마 목록은 fs.common.modules 한 곳
COMPANY_GW_TABLES = frozenset(
    {
        "gw.collaboration_settings",
        "gw.person_identity_binding",
        "gw.role_grant",
        "gw.document_reader",
        "gw.step_assignment",
    }
)


def _reject_company_copy(connection, *workspace_ids):
    for workspace_id in workspace_ids:
        if connection.execute(
            text("SELECT workspace_kind='COMPANY' FROM core.workspace WHERE id=:w"),
            {"w": workspace_id},
        ).scalar():
            raise RuntimeError("회사 공간은 체험 시드 복사/초기화 대상이 아닙니다.")


MONTH_COLUMNS = {
    ("erp.partner_item_price", "effective_from"),
    ("erp.partner_item_price", "effective_to"),
    ("fems.tariff", "effective_from"),
    ("fems.tariff", "effective_to"),
    ("fems.energy_target", "target_month"),
    ("fems.energy_baseline", "period_from"),
    ("fems.energy_baseline", "period_to"),
    ("hr.attendance_close", "close_month"),
    ("hr.payroll_run", "pay_month"),
    ("hr.pay_base", "effective_from"),
    ("gw.authority_rule", "effective_from"),
    ("gw.authority_rule", "effective_to"),
}


def copy_template(
    connection: Connection,
    source_workspace_id: int,
    source_generation_id: int,
    target_date: date,
    guest_session_key: str,
    schemas: tuple[str, ...] = SCHEMAS,
) -> tuple[int, int, dict[str, int], float]:
    """템플릿을 guest 세대로 복사한다. 업무 행은 INSERT ... SELECT로 이동한다.

    W0-1 지연 복사: 서비스는 schemas=()로 core만 만들고, 솔루션 시드는 처음 열 때
    copy_module_seed가 복사한다(DSN-01 S2). 기본값(전체)은 도구·기존 호출용.
    """
    _reject_company_copy(connection, source_workspace_id)
    metadata = _reflected(connection, ("core", *schemas))
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
            template_generation_id=source_generation_id,
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
        schemas=schemas,
    )
    return target_workspace_id, target_generation_id, counts, perf_counter() - started


def copy_template_generation(
    connection: Connection,
    source_workspace_id: int,
    source_generation_id: int,
    target_workspace_id: int,
    target_date: date,
    schemas: tuple[str, ...] = SCHEMAS,
) -> tuple[int, dict[str, int], float]:
    """기존 공간에 새 세대를 복사한다. 공간 설정은 유지한다. schemas=()이면 지연 복사(W0-1)."""
    _reject_company_copy(connection, source_workspace_id, target_workspace_id)
    metadata = _reflected(connection, ("core", *schemas))
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
            template_generation_id=source_generation_id,
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
        schemas=schemas,
    )
    _mark_seeded(connection, target_workspace_id, target_generation_id, schemas)
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
    schemas: tuple[str, ...] = SCHEMAS,
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
    if copy_modules:
        # 공통 휴일 달력은 core지만 공간·세대마다 있어야 한다(HR 근태·FEMS TOU가 읽는다).
        # 공휴일은 실제 달력 날짜라 다른 업무 날짜처럼 밀지 않는다 — 개천절은 늘 10-03이다.
        counts_holiday = connection.execute(
            text(
                """
                INSERT INTO core.holiday (workspace_id,generation_id,holiday_on,name,kind,created_at)
                SELECT :target_workspace,:target_generation,holiday_on,name,kind,
                       created_at + (:target_date - :source_date) * interval '1 day'
                FROM core.holiday
                WHERE workspace_id=:source_workspace AND generation_id=:source_generation
                """
            ),
            params,
        ).rowcount
    seeded = _seeded_tables(
        connection, source_workspace_id, source_generation_id, schemas
    )
    foreign_keys = _foreign_keys(connection, seeded)
    parents = {
        target
        for fks in foreign_keys.values()
        for _, target in fks.values()
        if target in seeded
    }
    # GW JSON 사건·다형 알림 참조도 같은 ID 지도가 필요하다.
    parents |= {name for name in seeded if name.startswith("gw.")}
    # ERP 전표·조정의 원천(`source_kind` + `source_id`)은 FK가 아니라 다형 참조다.
    # 복사하면서 새 id로 바꿔 주지 않으면 복사본이 템플릿의 id를 가리킨 채 남는다.
    parents |= {name for name in seeded if name in ERP_SOURCE_TABLES}
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
        {"core.workspace_module": module_rows, "core.holiday": counts_holiday}
        if copy_modules
        else {}
    )
    for table_name in _table_order(
        seeded, foreign_keys, _nullable_targets(connection, seeded)
    ):
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
    if "gw" in schemas:
        _remap_gw_references(connection, seeded, params)
    if "erp" in schemas:
        _remap_erp_sources(connection, seeded, params)
    # 같은 트랜잭션에서 여러 공간·세대를 복사해도 ID 지도를 재사용하지 않는다.
    for table_name in sorted(parents):
        connection.execute(text(f'DROP TABLE "{_map_name(table_name)}"'))
    if copy_modules:
        _mark_seeded(connection, target_workspace_id, target_generation_id, schemas)
    return counts


# 다형 원천을 가진 ERP 표와, 그 `source_kind`가 가리킬 수 있는 표들.
ERP_SOURCE_HOLDERS = {
    "erp.journal_entry": "source_kind",
    "erp.receivable_adjust": None,  # 반품 1종뿐이라 종류 칸이 없다
    "erp.payable_adjust": None,
}
ERP_SOURCE_TABLES = {
    "erp.sales_record",
    "erp.purchase_invoice",
    "erp.sales_return",
    "erp.purchase_return",
    "erp.receipt_apply",
    "erp.payment_apply",
    "erp.expense_claim",
}
# 종류 칸이 없는 표는 원천이 고정이다.
ERP_FIXED_SOURCE = {
    "erp.receivable_adjust": "sales_return",
    "erp.payable_adjust": "purchase_return",
}


def _remap_erp_sources(connection, seeded, params):
    """FK가 아닌 ERP 다형 참조(`source_id`)를 새 세대의 id로 옮긴다.

    전표는 `source_kind`가 어느 표인지 말해 주고, 채권·채무 조정은 반품 하나뿐이라 고정이다.
    지도에 없는 id는 **건드리지 않는다** — 조용히 0이나 NULL로 만들면 더 나쁘다.
    """
    maps = {
        name: dict(
            connection.execute(
                text(f'SELECT old_id,new_id FROM "{_map_name(name)}"')
            ).all()
        )
        for name in seeded
        if name in ERP_SOURCE_TABLES
    }
    for table, kind_column in ERP_SOURCE_HOLDERS.items():
        if table not in seeded:
            continue
        columns = "id,source_id" + (f",{kind_column}" if kind_column else "")
        rows = (
            connection.execute(
                text(
                    f"SELECT {columns} FROM {table} WHERE workspace_id=:target_workspace "
                    "AND generation_id=:target_generation AND source_id IS NOT NULL"
                ),
                params,
            )
            .mappings()
            .all()
        )
        for row in rows:
            kind = row[kind_column] if kind_column else ERP_FIXED_SOURCE[table]
            new_id = maps.get(f"erp.{kind}", {}).get(row["source_id"])
            if new_id is None:
                continue
            connection.execute(
                text(
                    f"UPDATE {table} SET source_id=:new WHERE id=:id "
                    "AND workspace_id=:target_workspace AND generation_id=:target_generation"
                ),
                dict(params, id=row["id"], new=new_id),
            )


def _remap_gw_references(connection, seeded, params):
    """관계 FK 밖의 GW 참조만 이동한다. 코드·이름·금액 스냅샷은 보존한다."""
    maps = {
        name: dict(
            connection.execute(
                text(f'SELECT old_id,new_id FROM "{_map_name(name)}"')
            ).all()
        )
        for name in seeded
        if name.startswith("gw.")
    }

    def mapped(name, value):
        if value is None:
            return None
        new = maps.get("gw." + name, {}).get(int(value))
        if new is None:
            raise RuntimeError(f"GW seed reference missing: {name}")
        return str(new) if isinstance(value, str) else new

    if "gw.approval_event" in seeded:
        rows = (
            connection.execute(
                text(
                    "SELECT id,details FROM gw.approval_event WHERE workspace_id=:target_workspace AND generation_id=:target_generation AND details IS NOT NULL"
                ),
                params,
            )
            .mappings()
            .all()
        )
        for row in rows:
            details = dict(row["details"])
            for key, table in (
                ("stepId", "approval_step"),
                ("delegationId", "delegation"),
            ):
                if key in details:
                    details[key] = mapped(table, details[key])
            rule = details.get("authorityRule")
            if rule:
                rule = dict(rule)
                for key, param in (
                    ("workspaceId", "target_workspace"),
                    ("generationId", "target_generation"),
                ):
                    if key in rule:
                        rule[key] = (
                            str(params[param])
                            if isinstance(rule[key], str)
                            else params[param]
                        )
                rule["id"] = mapped("authority_rule", rule["id"])
                for key in ("effectiveFrom", "effectiveTo"):
                    if rule.get(key):
                        rule[key] = connection.execute(
                            text("SELECT " + _month_expression(":month")),
                            dict(params, month=rule[key]),
                        ).scalar_one()
                if rule.get("createdAt"):
                    rule["createdAt"] = (
                        connection.execute(
                            text(
                                "SELECT CAST(:stamp AS timestamptz) + (:target_date - :source_date) * interval '1 day'"
                            ),
                            dict(params, stamp=rule["createdAt"]),
                        )
                        .scalar_one()
                        .isoformat()
                    )
                details["authorityRule"] = rule
            if details.get("appliedMonth"):
                details["appliedMonth"] = connection.execute(
                    text(
                        "SELECT to_char(submitted_at AT TIME ZONE 'Asia/Seoul','YYYY-MM') FROM gw.approval_document WHERE id=(SELECT document_id FROM gw.approval_event WHERE id=:id)"
                    ),
                    {"id": row["id"]},
                ).scalar_one()
            connection.execute(
                text(
                    "UPDATE gw.approval_event SET details=CAST(:details AS jsonb) WHERE id=:id AND workspace_id=:target_workspace AND generation_id=:target_generation"
                ),
                dict(params, id=row["id"], details=json.dumps(details)),
            )
    if "gw.notification" in seeded:
        targets = {
            "DOCUMENT": "approval_document",
            "POST": "board_post",
            "EVENT": "calendar_event",
            "CHANNEL": "chat_channel",
        }
        keys = {
            "D": "approval_document",
            "P": "board_post",
            "E": "calendar_event",
            "C": "comment",
        }
        rows = (
            connection.execute(
                text(
                    "SELECT id,ref_kind,ref_id,event_key FROM gw.notification WHERE workspace_id=:target_workspace AND generation_id=:target_generation"
                ),
                params,
            )
            .mappings()
            .all()
        )
        for row in rows:
            ref = mapped(targets[row["ref_kind"]], row["ref_id"])
            parts = row["event_key"].split(":")
            if len(parts) >= 3 and parts[0] in keys and parts[1].isdigit():
                parts[1] = str(mapped(keys[parts[0]], parts[1]))
            connection.execute(
                text(
                    "UPDATE gw.notification SET ref_id=:ref,event_key=:key WHERE id=:id AND workspace_id=:target_workspace AND generation_id=:target_generation"
                ),
                dict(params, id=row["id"], ref=ref, key=":".join(parts)),
            )


def _mark_seeded(
    connection: Connection,
    workspace_id: int,
    generation_id: int,
    schemas: tuple[str, ...],
) -> None:
    """복사한 솔루션 시드를 표시한다. 세대가 바뀌면 표시는 자동으로 무효(지연 복사 다시)."""
    if schemas:
        connection.execute(
            text(
                "UPDATE core.workspace_module SET seeded_generation_id=:g "
                "WHERE workspace_id=:w AND module_key=ANY(:keys)"
            ),
            {"w": workspace_id, "g": generation_id, "keys": list(schemas)},
        )


def copy_module_seed(
    connection: Connection, workspace_id: int, module_key: str
) -> dict[str, int] | None:
    """활성 세대에 한 솔루션의 템플릿 시드를 복사한다(W0-1, DSN-01 S2 지연 복사).

    호출자는 공간 잠금(WORKSPACE_LOCK_NAMESPACE)을 잡은 쓰기 트랜잭션에서 부른다.
    이미 복사됐으면 None. 세대의 원천 템플릿이 정리됐으면 같은 seed_version의 최신 템플릿을 쓴다.
    """
    _reject_company_copy(connection, workspace_id)
    row = (
        connection.execute(
            text(
                """
            SELECT w.active_generation_id generation_id, g.seed_date, g.seed_version,
                   g.template_generation_id, m.seeded_generation_id
            FROM core.workspace w
            JOIN core.data_generation g ON g.workspace_id=w.id AND g.id=w.active_generation_id
            JOIN core.workspace_module m ON m.workspace_id=w.id AND m.module_key=:module
            WHERE w.id=:w
            """
            ),
            {"w": workspace_id, "module": module_key},
        )
        .mappings()
        .one_or_none()
    )
    if row is None or row["seeded_generation_id"] == row["generation_id"]:
        return None
    if module_key not in SCHEMAS:  # 시드가 없는 모듈(core 등)
        _mark_seeded(connection, workspace_id, row["generation_id"], (module_key,))
        return {}
    source = (
        connection.execute(
            text(
                """
            SELECT g.workspace_id, g.id, g.seed_date FROM core.data_generation g
            JOIN core.workspace w ON w.id=g.workspace_id AND w.workspace_kind='TEMPLATE'
            WHERE g.purged_at IS NULL AND (g.id=:template OR g.seed_version=:version)
            ORDER BY (g.id=:template) DESC, g.created_at DESC, g.id DESC LIMIT 1
            """
            ),
            {"template": row["template_generation_id"], "version": row["seed_version"]},
        )
        .mappings()
        .one_or_none()
    )
    counts: dict[str, int] = {}
    if source is not None:
        metadata = _reflected(connection, (module_key,))
        counts = _copy_business_rows(
            connection,
            metadata,
            source["workspace_id"],
            source["id"],
            workspace_id,
            row["generation_id"],
            source["seed_date"],
            row["seed_date"],
            copy_modules=False,
            schemas=(module_key,),
        )
    _mark_seeded(connection, workspace_id, row["generation_id"], (module_key,))
    return counts


# W0-2: 스키마 반영(reflection)이 게스트 복사 시간의 90%였다. 실행 중 스키마는 바뀌지 않으므로
# DB·스키마별로 한 번만 반영한다. 마이그레이션 뒤에는 프로세스를 다시 시작한다(배포 절차와 같음).
_CATALOG: dict[tuple[str, str], MetaData] = {}
_RAW_FKS: dict[tuple[str, str], list[tuple[str, str, str]]] = {}


def _reflected(connection: Connection, schemas: tuple[str, ...]) -> MetaData:
    metadata = MetaData()
    database = connection.engine.url.render_as_string(hide_password=True)
    for schema in schemas:
        key = (database, schema)
        if key not in _CATALOG:
            cached = MetaData()
            cached.reflect(connection, schema=schema)
            _CATALOG[key] = cached
        for table in _CATALOG[key].tables.values():
            table.to_metadata(metadata)
    return metadata


def _raw_foreign_keys(
    connection: Connection, table_name: str
) -> list[tuple[str, str, str]]:
    """(로컬 칸, 원격 칸, 대상 표) — FK와, FK 없이 '<표>_id'로 같은 스키마 표를 가리키는 칸."""
    key = (connection.engine.url.render_as_string(hide_password=True), table_name)
    if key not in _RAW_FKS:
        inspector = inspect(connection)
        schema, table = table_name.split(".")
        raw: list[tuple[str, str, str]] = []
        for fk in inspector.get_foreign_keys(table, schema=schema):
            target = f"{fk['referred_schema']}.{fk['referred_table']}"
            for local, remote in zip(
                fk["constrained_columns"], fk["referred_columns"], strict=True
            ):
                raw.append((local, remote, target))
        for column in inspector.get_columns(table, schema=schema):
            if column["name"].endswith("_id"):
                raw.append((column["name"], "", f"{schema}.{column['name'][:-3]}"))
        _RAW_FKS[key] = raw
    return _RAW_FKS[key]


def _seeded_tables(
    connection: Connection,
    workspace_id: int,
    generation_id: int,
    schemas: tuple[str, ...] = SCHEMAS,
) -> set[str]:
    tables: set[str] = set()
    catalog = _reflected(connection, schemas)
    for table_name in catalog.tables:
        if table_name in COMPANY_GW_TABLES:
            continue
        schema, table = table_name.split(".")
        if schema not in schemas:  # FK로 함께 반영된 core 표
            continue
        if connection.execute(
            text(
                f'SELECT EXISTS (SELECT 1 FROM "{schema}"."{table}" WHERE workspace_id=:w AND generation_id=:g)'
            ),
            {"w": workspace_id, "g": generation_id},
        ).scalar_one():
            tables.add(table_name)
    return tables


def _foreign_keys(
    connection: Connection, seeded: set[str]
) -> dict[str, dict[str, tuple[str, str]]]:
    result: dict[str, dict[str, tuple[str, str]]] = defaultdict(dict)
    for table_name in seeded:
        raw = _raw_foreign_keys(connection, table_name)
        for local, remote, target in raw:  # 실제 FK 먼저
            if (
                remote
                and local not in {"workspace_id", "generation_id"}
                and remote == "id"
                and target in seeded
            ):
                result[table_name][local] = (remote, target)
        for local, remote, target in raw:  # FK 없는 '<표>_id' 칸
            if not remote and local not in result[table_name] and target in seeded:
                result[table_name][local] = ("id", target)
    return result


def _nullable_targets(connection: Connection, seeded: set[str]) -> dict[str, set[str]]:
    """표마다 '비울 수 있는 칼럼으로 가리키는' 다른 시드 표. 고리를 끊을 때만 쓴다."""
    inspector = inspect(connection)
    result: dict[str, set[str]] = {}
    for table_name in seeded:
        schema, table = table_name.split(".")
        nullable = {
            column["name"]
            for column in inspector.get_columns(table, schema=schema)
            if column["nullable"]
        }
        result[table_name] = {
            f"{fk['referred_schema']}.{fk['referred_table']}"
            for fk in inspector.get_foreign_keys(table, schema=schema)
            if set(fk["constrained_columns"]) & nullable
        } & seeded
    return result


def _table_order(
    seeded: set[str],
    foreign_keys: dict[str, dict[str, tuple[str, str]]],
    nullable_targets: dict[str, set[str]] | None = None,
) -> list[str]:
    nullable_targets = nullable_targets or {}
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
            # 고리(MES 재작업 지시 ↔ LOT). 남은 의존이 모두 비울 수 있는 칼럼인 표부터 넣는다.
            # ponytail: 시드가 그 칼럼을 채우면 복사 뒤 UPDATE 한 번이 더 필요하다(지금은 모두 NULL).
            ready = sorted(
                table
                for table in remaining
                if (dependencies[table] & remaining)
                <= nullable_targets.get(table, set())
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
    if table_name == "gw.approval_document" and column == "source_snapshot":
        # Only display dates move; the code/amount snapshot and digest stay unchanged.
        fields = []
        for key, cast in (
            ("invoiceDate", "date"),
            ("dueDate", "date"),
            ("confirmedAt", "timestamptz"),
            ("cancelledAt", "timestamptz"),
        ):
            shift = "(:target_date - :source_date)"
            if cast == "timestamptz":
                shift += " * interval '1 day'"
            fields.append(
                f"'{key}', (src.source_snapshot #>> '{{display,{key}}}')::{cast} + {shift}"
            )
        return (
            "CASE WHEN src.source_snapshot IS NULL OR src.source_snapshot->'display' IS NULL "
            "THEN src.source_snapshot ELSE jsonb_set(src.source_snapshot, '{display}', "
            "(src.source_snapshot->'display') || jsonb_build_object("
            + ",".join(fields)
            + ")) END"
        )
    if table_name == "wms.stock_reservation" and column == "reservation_no":
        return "left(src.reservation_no,4) || to_char(to_date(substr(src.reservation_no,5,8), 'YYYYMMDD') + (:target_date - :source_date), 'YYYYMMDD') || substr(src.reservation_no,13)"
    if table_name == "wms.source_claim" and column == "source_snapshot":
        # Only the display timestamp moves. Semantic digest stays byte-for-byte intact.
        return "CASE WHEN src.source_snapshot->>'confirmedAt' IS NULL THEN src.source_snapshot ELSE jsonb_set(src.source_snapshot, '{confirmedAt}', to_jsonb((src.source_snapshot->>'confirmedAt')::timestamptz + (:target_date - :source_date) * interval '1 day')) END"
    if table_name == "wms.stock_document" and column in {"source_key", "source_ref"}:
        prefix = "'WMS:INSPECTION:' || " if column == "source_key" else ""
        return f"CASE WHEN src.document_type='WMS_INSPECTION' THEN {prefix}left(src.source_ref, 3) || to_char(to_date(substr(src.source_ref, 4, 8), 'YYYYMMDD') + (:target_date - :source_date), 'YYYYMMDD') || substr(src.source_ref, 12) ELSE src.\"{column}\" END"
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
    derived_month = {
        ("qms.inspection", "inspection_month"): "inspected_on",
        ("wms.stock_document", "document_month"): "document_on",
    }
    if (table_name, column) in derived_month:
        # 업무일(검사일·전표일)을 옮긴 뒤 월을 다시 구한다.
        day = derived_month[(table_name, column)]
        return f"to_char(src.{day} + (:target_date - :source_date), 'YYYY-MM')"
    if (table_name, column) in {
        ("qms.inspection", "inspection_no"),
        ("qms.quality_hold", "hold_no"),
        ("wms.stock_document", "document_no"),
        ("wms.inbound_notice", "notice_no"),
        ("hr.appointment", "appointment_no"),
        ("hr.leave_request", "request_no"),
    }:
        # QI-/QH-/WD-/AP-/LV-YYYYMMDD-NNN: 번호 속 날짜도 같은 일수만큼 옮긴다.
        return (
            f'left(src."{column}", 3) || to_char(to_date(substr(src."{column}", 4, 8), \'YYYYMMDD\') '
            f"+ (:target_date - :source_date), 'YYYYMMDD') || substr(src.\"{column}\", 12)"
        )
    if (table_name, column) == ("hr.leave_balance", "leave_year"):
        return "extract(year from CAST(:target_date AS date))::int::text"
    if (table_name, column) == ("hr.bonus_rule", "payable_mm"):
        # 상여는 늘 '지난달'에 지급한다 — 옮긴 기준일의 지난달로 다시 맞춘다.
        return "to_char(date_trunc('month', CAST(:target_date AS date)) - interval '1 month', 'MM')"
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
