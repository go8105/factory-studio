"""GW-c HR 읽기 인터페이스 → 명시적 스냅샷 가져오기. HR에 쓰지 않는다."""

import hashlib
import json
import re

from fs.common.engine import action, read
from fs.common.errors import ApiError
from fs.common.scope import read_scope
from fs.gw import service as gw
from fs.hr import interface as hr


def local(c, ctx):
    return (
        gw.rows(
            c,
            f"SELECT * FROM gw.organization_unit WHERE {gw.S} ORDER BY code",
            gw.params(ctx),
        ),
        gw.rows(
            c, f"SELECT * FROM gw.person WHERE {gw.S} ORDER BY code", gw.params(ctx)
        ),
    )


def validate(departments, employees):
    units = {d["code"]: d for d in departments}
    if len(units) != len(departments):
        raise gw.invalid("departments", "HR 부서 코드가 중복됩니다.")
    for d in departments:
        if (
            not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{0,29}", d["code"])
            or not 1 <= len(d["name"]) <= 100
        ):
            raise gw.invalid("departments", "부서 코드·이름을 확인하세요.")
        path, node = set(), d
        while node is not None:
            if node["code"] in path:
                raise gw.invalid("departments", "HR 조직에 순환 참조가 있습니다.")
            path.add(node["code"])
            parent = node["parentCode"]
            if parent and parent not in units:
                raise gw.invalid("departments", "HR 상위 부서를 찾을 수 없습니다.")
            if node["isActive"] and parent and not units[parent]["isActive"]:
                raise gw.invalid("departments", "활성 부서의 상위 부서가 비활성입니다.")
            node = units.get(parent)
    codes = set()
    for e in employees:
        if (
            e["employeeCode"] in codes
            or not 1 <= len(e["employeeCode"]) <= 30
            or not 1 <= len(e["name"]) <= 80
        ):
            raise gw.invalid(
                "employees", "HR 사원 코드·이름이 중복되거나 길이 제한을 넘습니다."
            )
        codes.add(e["employeeCode"])
        if e["departmentCode"] not in units:
            raise gw.invalid("employees", "HR 사원의 부서를 찾을 수 없습니다.")
        if e["status"] == "ACTIVE" and not units[e["departmentCode"]]["isActive"]:
            raise gw.invalid("employees", "재직 사원의 부서가 비활성입니다.")


def state(c, ctx):
    units, people = local(c, ctx)
    departments, employees = hr.departments(c, ctx), hr.employees(c, ctx, status=None)
    available = departments is not None and employees is not None
    result = {
        "available": available,
        "departments": departments,
        "employees": employees,
        "organizations": gw.wire(units),
        "people": gw.wire(people),
    }
    if available:
        validate(departments, employees)
        linked = [p["hr_employee_code"] for p in people if p["hr_employee_code"]]
        if len(linked) != len(set(linked)):
            raise gw.invalid(
                "employees", "같은 HR 사원에 여러 담당자가 연결되어 있습니다."
            )
        result["digest"] = hashlib.sha256(
            json.dumps(result, sort_keys=True, ensure_ascii=False).encode()
        ).hexdigest()
    else:
        result["digest"] = None
    return result


def preview(context):
    with read() as c:
        return state(c, read_scope(c, context, "gw"))


def import_hr(context, values, key):
    def run(c, ctx):
        source = state(c, ctx)
        if not source["available"]:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "HR이 꺼져 있거나 아직 열지 않아 가져올 수 없습니다.",
                {"reason": "HR_UNAVAILABLE"},
            )
        if source["digest"] != values["preview_digest"]:
            raise ApiError(
                409,
                "PRECONDITION_NOT_MET",
                "HR 또는 GW 정보가 바뀌었습니다. 미리보기를 다시 확인하세요.",
                {"reason": "HR_IMPORT_CHANGED"},
            )
        selected = values["employee_codes"]
        active = {
            e["employeeCode"]: e for e in source["employees"] if e["status"] == "ACTIVE"
        }
        if len(selected) != len(set(selected)) or any(
            code not in active for code in selected
        ):
            raise gw.invalid("employeeCodes", "중복 없이 재직 사원을 선택하세요.")
        units, people = local(c, ctx)
        org = {d["code"]: d["id"] for d in units}
        ids = {u["id"]: u["code"] for u in units}
        current_codes = {d["code"] for d in source["departments"]}
        combined = source["departments"] + [
            {
                "code": u["code"],
                "name": u["name"],
                "parentCode": ids.get(u["parent_id"]),
                "isActive": u["is_active"],
            }
            for u in units
            if u["code"] not in current_codes
        ]
        validate(combined, [])
        stamp = gw.now(c)
        # 먼저 모든 부서 id를 확보한 뒤 부모를 연결한다. HR에서 없어진 부서는 참조를 보존한다.
        for d in source["departments"]:
            if d["code"] not in org:
                org[d["code"]] = gw.insert(
                    c,
                    ctx,
                    "organization_unit",
                    {"code": d["code"], "name": d["name"], "is_active": d["isActive"]},
                )
        for d in source["departments"]:
            gw.update(
                c,
                ctx,
                "organization_unit",
                org[d["code"]],
                {
                    "name": d["name"],
                    "is_active": d["isActive"],
                    "parent_id": org.get(d["parentCode"]),
                    "hr_synced_at": stamp,
                },
            )
        by_hr = {p["hr_employee_code"]: p for p in people if p["hr_employee_code"]}
        used_codes = {p["code"] for p in people}
        created, updated = 0, 0
        for code in selected:
            e = active[code]
            data = {"name": e["name"], "organization_unit_id": org[e["departmentCode"]]}
            if code in by_hr:
                # GW 직무·활성 상태는 로컬 소유: 가져오기로 권한 승격/재활성화하지 않는다.
                gw.update(c, ctx, "person", by_hr[code]["id"], data)
                updated += 1
            else:
                person_code = (
                    code
                    if re.fullmatch(r"[A-Z][A-Z0-9-]{1,29}", code)
                    else "HR-" + hashlib.sha256(code.encode()).hexdigest()[:20].upper()
                )
                if person_code in used_codes:
                    raise ApiError(
                        409,
                        "PRECONDITION_NOT_MET",
                        "GW 코드가 이미 사용 중입니다. 기존 담당자를 자동 연결하지 않습니다.",
                        {"reason": "HR_CODE_COLLISION", "employeeCode": code},
                    )
                gw.insert(
                    c,
                    ctx,
                    "person",
                    {
                        "code": person_code,
                        "hr_employee_code": code,
                        "job_role": "STAFF",
                        **data,
                    },
                )
                used_codes.add(person_code)
                created += 1
        result = {
            "created": created,
            "updated": updated,
            "departments": len(source["departments"]),
            "syncedAt": stamp.isoformat(),
        }
        gw.audit(
            c,
            ctx,
            "people",
            ctx.workspace_id,
            "import-hr",
            result,
            table="organization_unit",
            summary=result,
        )
        return (
            result,
            "gw.organization_unit",
            next(iter(org.values()), ctx.workspace_id),
        )

    return action("gw", context, "gw.import-hr", key, values, run)


def enrich_people(c, ctx, people):
    units, _ = local(c, ctx)
    units = {u["id"]: u for u in units}
    employees = hr.employees(c, ctx, status=None)
    statuses = (
        {e["employeeCode"]: e["status"] for e in employees}
        if employees is not None
        else None
    )
    for p in people:
        p["organization_name"] = units.get(p["organization_unit_id"], {}).get("name")
        code = p["hr_employee_code"]
        p["hr_status"] = (
            "UNLINKED"
            if not code
            else "UNAVAILABLE"
            if statuses is None
            else statuses.get(code, "MISSING")
        )
    return people
