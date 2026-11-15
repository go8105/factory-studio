# 주의: `from __future__ import annotations`를 쓰지 않는다. FastAPI가 본문 타입을 실제 클래스로 읽어야 한다.
"""BEMS API (/api/v1/bems, FS-025 모듈 설계 8장). 변경 요청은 CSRF와 Idempotency-Key가 필요하다."""

from datetime import date
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, Header, Query
from pydantic import BaseModel

from fs.bems import service
from fs.bems.schema import (
    Acknowledge,
    ActiveUpdate,
    Advance,
    BuildingCreate,
    BuildingUpdate,
    ComfortCreate,
    ComfortUpdate,
    CommandCreate,
    EquipmentRuleCreate,
    EquipmentRuleUpdate,
    HvacCreate,
    HvacUpdate,
    LightingCreate,
    LightingUpdate,
    MeterCreate,
    MonthRequest,
    NameUpdate,
    PlanCreate,
    PlanDecision,
    ReviewCreate,
    RuleCreate,
    RuleUpdate,
    ScheduleReplace,
    SensorCreate,
    TargetCreate,
    TargetUpdate,
    ZoneCreate,
    ZoneUpdate,
)
from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
IdempotencyKey = Annotated[str | None, Header(alias="Idempotency-Key")]
CsrfToken = Annotated[str | None, Header(alias="X-CSRF-Token")]
From = Annotated[date | None, Query(alias="from")]
To = Annotated[date | None, Query(alias="to")]


# 공통 엔진: CSRF·멱등 키 확인
_mutation = mutation_key


def _values(
    payload: BaseModel, nullable: frozenset[str] = frozenset()
) -> dict[str, Any]:
    values = payload.model_dump(exclude_unset=True)
    if any(v is None for k, v in values.items() if k not in nullable):
        raise ApiError(400, "VALIDATION_FAILED", "필수 항목은 null로 비울 수 없습니다.")
    return values


def _data(value: Any) -> dict[str, Any]:
    return {"data": value}


@router.get("/dashboard")
def get_dashboard(context: Auth):
    return _data(service.dashboard(context))


@router.get("/breakdown")
def get_breakdown(
    context: Auth,
    date_from: From = None,
    date_to: To = None,
    granularity: Literal["day", "month"] = "day",
):
    return _data(service.breakdown(context, granularity, date_from, date_to))


@router.get("/environment")
def get_environment(
    context: Auth,
    zone_id: Annotated[int, Query(alias="zoneId")],
    date_from: From = None,
    date_to: To = None,
):
    return _data(service.environment(context, zone_id, date_from, date_to))


@router.get("/energy")
def get_energy(
    context: Auth,
    meter_id: Annotated[int | None, Query(alias="meterId")] = None,
    date_from: From = None,
    date_to: To = None,
):
    return _data(service.energy(context, meter_id, date_from, date_to))


# ---- 기준정보 (B-07) ----
MASTERS: list[tuple[str, str, type[BaseModel], type[BaseModel], frozenset[str]]] = [
    ("buildings", "building", BuildingCreate, BuildingUpdate, frozenset()),
    (
        "zones",
        "zone",
        ZoneCreate,
        ZoneUpdate,
        frozenset({"floor_area_m2", "building_id", "floor_label", "department_code"}),
    ),
    ("meters", "meter", MeterCreate, NameUpdate, frozenset()),
    ("sensors", "sensor", SensorCreate, ActiveUpdate, frozenset()),
    ("hvac-units", "hvac_unit", HvacCreate, HvacUpdate, frozenset({"meter_id"})),
    (
        "lighting-circuits",
        "lighting_circuit",
        LightingCreate,
        LightingUpdate,
        frozenset({"meter_id"}),
    ),
    (
        "comfort-standards",
        "comfort_standard",
        ComfortCreate,
        ComfortUpdate,
        frozenset({"low", "high"}),
    ),
    (
        "equipment-alarm-rules",
        "equipment_alarm_rule",
        EquipmentRuleCreate,
        EquipmentRuleUpdate,
        frozenset({"hvac_unit_id"}),
    ),
    (
        "energy-targets",
        "energy_target",
        TargetCreate,
        TargetUpdate,
        frozenset({"zone_id"}),
    ),
]


def _register(
    path: str,
    table: str,
    create_model: type[BaseModel],
    update_model: type[BaseModel],
    nullable: frozenset[str],
) -> None:
    def list_rows(
        context: Auth, zone_id: Annotated[int | None, Query(alias="zoneId")] = None
    ):
        return _data(service.list_master(context, table, zone_id))

    def create(
        payload: create_model,
        context: Auth,
        csrf: CsrfToken = None,
        key: IdempotencyKey = None,
    ):  # type: ignore[valid-type]
        return _data(
            service.create_master(
                context, table, payload.model_dump(), _mutation(context, csrf, key)
            )
        )

    def update(
        row_id: int,
        payload: update_model,
        context: Auth,
        csrf: CsrfToken = None,
        key: IdempotencyKey = None,
    ):  # type: ignore[valid-type]
        return _data(
            service.update_master(
                context,
                table,
                row_id,
                _values(payload, nullable),
                _mutation(context, csrf, key),
            )
        )

    router.add_api_route(f"/{path}", list_rows, methods=["GET"])
    router.add_api_route(f"/{path}", create, methods=["POST"], status_code=201)
    router.add_api_route(f"/{path}/{{row_id}}", update, methods=["PATCH"])


for _path, _table, _create, _update, _nullable in MASTERS:
    _register(_path, _table, _create, _update, _nullable)


@router.get("/lookups/departments")
def lookup_departments(context: Auth):
    return _data(service.list_departments(context))


# ---- 공조 운전 (B-04·B-05) ----
@router.get("/hvac-overview")
def hvac_overview(context: Auth):
    return _data(service.hvac_units(context))


@router.get("/hvac-units/{unit_id}/detail")
def hvac_detail(unit_id: int, context: Auth):
    return _data(service.hvac_unit(context, unit_id))


@router.put("/hvac-units/{unit_id}/schedule")
def put_schedule(
    unit_id: int,
    payload: ScheduleReplace,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    slots = [s.model_dump() for s in payload.slots]
    return _data(
        service.replace_schedule(context, unit_id, slots, _mutation(context, csrf, key))
    )


@router.get("/lighting-circuits/{circuit_id}/detail")
def lighting_detail(circuit_id: int, context: Auth):
    return _data(service.lighting_circuit(context, circuit_id))


@router.put("/lighting-circuits/{circuit_id}/schedule")
def put_lighting_schedule(
    circuit_id: int,
    payload: ScheduleReplace,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    slots = [s.model_dump() for s in payload.slots]
    return _data(
        service.replace_lighting_schedule(
            context, circuit_id, slots, _mutation(context, csrf, key)
        )
    )


@router.get("/commands")
def list_commands(
    context: Auth,
    zone_id: Annotated[int | None, Query(alias="zoneId")] = None,
    unit_id: Annotated[int | None, Query(alias="hvacUnitId")] = None,
    circuit_id: Annotated[int | None, Query(alias="lightingCircuitId")] = None,
):
    return _data(service.commands(context, zone_id, unit_id, circuit_id))


@router.post("/commands", status_code=201)
def post_command(
    payload: CommandCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.send_command(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.get("/simulation/clock")
def get_clock(context: Auth):
    return _data(service.simulation_clock(context))


@router.post("/simulation/advance")
def post_advance(
    payload: Advance, context: Auth, csrf: CsrfToken = None, key: IdempotencyKey = None
):
    return _data(service.advance(context, payload.hours, _mutation(context, csrf, key)))


# ---- 경보 (B-06) ----
@router.get("/alarms")
def list_alarms(
    context: Auth,
    status: Annotated[
        str | None, Query(pattern="^(raised|acknowledged|cleared)$")
    ] = None,
):
    return _data(service.alarms(context, status))


@router.post("/alarms/{alarm_id}/acknowledge")
def post_acknowledge(
    alarm_id: int,
    payload: Acknowledge,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.acknowledge(
            context, alarm_id, payload.note, _mutation(context, csrf, key)
        )
    )


# ---- 건물 에너지·비용·보고서 (B-11~B-13) ----

Month = Annotated[str | None, Query(pattern=r"^[0-9]{4}-(0[1-9]|1[0-2])$")]


@router.get("/building-energy")
def get_building_energy(context: Auth, month: Month = None):
    return _data(service.building_energy(context, month))


@router.get("/cost-runs")
def list_cost_runs(context: Auth):
    return _data(service.cost_runs(context))


@router.get("/cost-runs/{run_id}")
def get_cost_run(run_id: int, context: Auth):
    return _data(service.cost_run(context, run_id))


@router.post("/cost-runs", status_code=201)
def post_cost_run(
    payload: MonthRequest,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.calculate_cost(context, payload.month, _mutation(context, csrf, key))
    )


@router.post("/cost-runs/{run_id}/confirm")
def post_cost_confirm(
    run_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(service.confirm_cost(context, run_id, _mutation(context, csrf, key)))


@router.get("/reviews")
def list_reviews(context: Auth):
    return _data(service.reviews(context))


@router.get("/reviews/{review_id}")
def get_review(review_id: int, context: Auth):
    return _data(service.review(context, review_id))


@router.post("/reviews", status_code=201)
def post_review(
    payload: ReviewCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.draft_review(
            context, payload.month, payload.issues, _mutation(context, csrf, key)
        )
    )


@router.post("/reviews/{review_id}/confirm")
def post_review_confirm(
    review_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.confirm_review(context, review_id, _mutation(context, csrf, key))
    )


# ---- 피크 감축 (B-09) ----


@router.get("/peak-alarms")
def list_peak_alarms(context: Auth):
    return _data(service.peak_alarms(context))


@router.get("/demand-plans")
def list_demand_plans(
    context: Auth,
    status: Literal["PROPOSED", "EXECUTED", "RESTORED", "REJECTED"] | None = None,
):
    return _data(service.demand_plans(context, status))


@router.get("/demand-plans/{plan_id}")
def get_demand_plan(plan_id: int, context: Auth):
    return _data(service.demand_plan(context, plan_id))


@router.post("/demand-plans", status_code=201)
def post_demand_plan(
    payload: PlanCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.propose_plan(context, payload.alarm_ref, _mutation(context, csrf, key))
    )


def _register_decision(path: str, call) -> None:
    def decide(
        plan_id: int,
        payload: PlanDecision | None = None,
        context: Auth = None,  # type: ignore[assignment]
        csrf: CsrfToken = None,
        key: IdempotencyKey = None,
    ):
        note = payload.note if payload else None
        return _data(call(context, plan_id, note, _mutation(context, csrf, key)))

    router.add_api_route(f"/demand-plans/{{plan_id}}/{path}", decide, methods=["POST"])


for _path, _call in (
    ("approve", service.approve_plan),
    ("reject", service.reject_plan),
    ("restore", service.restore_plan),
):
    _register_decision(_path, _call)


@router.get("/comfort")
def get_comfort(context: Auth, date_from: From = None, date_to: To = None):
    return _data(service.comfort(context, date_from, date_to))


@router.get("/equipment-alarms")
def list_equipment_alarms(
    context: Auth,
    status: Literal["raised", "acknowledged", "cleared"] | None = None,
):
    return _data(service.equipment_alarms(context, status))


@router.post("/equipment-alarms/{alarm_id}/acknowledge")
def post_equipment_acknowledge(
    alarm_id: int,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.acknowledge_equipment_alarm(
            context, alarm_id, _mutation(context, csrf, key)
        )
    )


@router.get("/alarm-rules")
def list_rules(context: Auth):
    return _data(service.alarm_rules(context))


@router.post("/alarm-rules", status_code=201)
def post_rule(
    payload: RuleCreate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.create_rule(
            context, payload.model_dump(), _mutation(context, csrf, key)
        )
    )


@router.patch("/alarm-rules/{rule_id}")
def patch_rule(
    rule_id: int,
    payload: RuleUpdate,
    context: Auth,
    csrf: CsrfToken = None,
    key: IdempotencyKey = None,
):
    return _data(
        service.update_rule(
            context, rule_id, _values(payload), _mutation(context, csrf, key)
        )
    )
