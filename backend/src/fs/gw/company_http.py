"""기존 63경로의 회사 전용 입력 계약과 분기. 개인 입력 계약은 그대로 둔다."""

from copy import deepcopy

from fastapi.encoders import jsonable_encoder
from fastapi.routing import APIRoute
from pydantic import Field, ValidationError, create_model
from sqlalchemy import text
from starlette.concurrency import run_in_threadpool
from starlette.responses import JSONResponse, Response

from fs.common.auth import resolve_auth
from fs.common.engine import mutation_key
from fs.common.errors import ApiError
from fs.gw import (
    company,
    company_collaboration,
    company_policy,
    company_service,
    company_work,
    schema,
)


def invalid():
    raise ApiError(
        400, "VALIDATION_FAILED", "회사 GW의 입력값과 조회 조건을 확인하세요."
    )


class CompanyPersonPatch(schema.PersonPatch):
    reason: schema.Text = Field(min_length=2, max_length=500)


class CompanyHrImport(schema.HrImport):
    reason: schema.Text = Field(min_length=2, max_length=500)


class CompanyRoute(APIRoute):
    def get_route_handler(self):
        personal = super().get_route_handler()
        model = self.body_field.field_info.annotation if self.body_field else None
        if (
            self.path.endswith("/people/{id}")
            or self.path.endswith("/people-master/{id}")
        ) and "PATCH" in self.methods:
            model = CompanyPersonPatch
        if self.path.endswith("/import-hr"):
            model = CompanyHrImport
        company_model = (
            create_model(
                "Company" + model.__name__,
                __base__=schema.Model,
                **{
                    name: (field.annotation, deepcopy(field))
                    for name, field in model.model_fields.items()
                    if name != "acting_person_id"
                },
            )
            if model
            else schema.Version
            if "DELETE" in self.methods
            else schema.Model
        )

        async def handle(request):
            if "companyId" not in request.query_params:
                return await personal(request)
            # Fail closed until every company route and UI is ready.
            if not company.BUSINESS_READY:
                return await personal(request)
            body = None
            if request.method != "GET":
                try:
                    body = await request.json()
                except ValueError:
                    invalid()
                if not isinstance(body, dict):
                    invalid()
            return await run_in_threadpool(
                self.company_response, request, company_model, body
            )

        return handle

    def company_response(self, request, model, body):
        context = resolve_auth(request.cookies.get("fs_session"))
        try:
            company_id = int(request.query_params["companyId"])
            if (
                not 0 < company_id <= 2147483647
                or len(request.query_params.getlist("companyId")) != 1
            ):
                invalid()
        except ValueError, TypeError:
            invalid()
        # Every service repeats this authorization inside its own business TX.
        with company.transaction(context, company_id) as (c, ctx, _):
            if (
                "personId" in request.query_params
                or isinstance(body, dict)
                and {"actingPersonId", "acting_person_id"} & body.keys()
            ):
                invalid()
            if not c.execute(
                text(f"SELECT 1 FROM gw.collaboration_settings WHERE {company.S}"),
                {"w": ctx.workspace_id, "g": ctx.generation_id},
            ).first():
                raise ApiError(
                    409, "GW_SETUP_REQUIRED", "회사 GW 최초 설정이 필요합니다."
                )
            company.principal(c, ctx)
        q = {}
        allowed = {"companyId"}
        for field in [*self.dependant.query_params, *self.dependant.path_params]:
            if field.alias == "personId":
                continue
            source = (
                request.path_params
                if field in self.dependant.path_params
                else request.query_params
            )
            value = source.get(
                field.alias,
                field.default if not field.field_info.is_required() else None,
            )
            value, errors = field.validate(value, {}, loc=("query", field.alias))
            if errors:
                invalid()
            q[field.name] = value
            if field in self.dependant.query_params:
                allowed.add(field.alias)
        if self.path.endswith("/people-options"):
            for name, default in (("limit", 50), ("offset", 0)):
                try:
                    q[name] = int(request.query_params.get(name, default))
                except ValueError:
                    invalid()
            q["search"] = request.query_params.get("search", "")
            if not 1 <= q["limit"] <= 100 or q["offset"] < 0 or len(q["search"]) > 100:
                invalid()
            allowed |= {"limit", "offset", "search"}
        if any(
            k not in allowed or len(request.query_params.getlist(k)) != 1
            for k in request.query_params
        ):
            invalid()
        try:
            values = (
                model.model_validate(body or {}).model_dump(
                    exclude_unset=request.method in {"PATCH", "DELETE"}
                )
                if request.method != "GET"
                else {}
            )
        except ValidationError as error:
            raise ApiError(
                400,
                "VALIDATION_FAILED",
                "입력값을 확인해 주세요.",
                {
                    "fields": {
                        "body."
                        + ".".join(
                            map(str, item["loc"])
                        ): "필수 입력·형식·길이를 확인하세요."
                        for item in error.errors(include_input=False)
                    }
                },
            ) from error
        if request.method != "GET":
            key = mutation_key(
                context,
                request.headers.get("X-CSRF-Token"),
                request.headers.get("Idempotency-Key"),
            )
        else:
            key = None
        if q.get("id") is not None and not 0 < q["id"] <= 9223372036854775807:
            invalid()
        path = self.path.removeprefix("/api/v1/gw")
        # include_router retains a prefixed path; the final three segments define resource/operation.
        result, page = dispatch(
            context, company_id, path, request.method, q, values, key
        )
        if self.status_code == 204:
            return Response(status_code=204)
        return JSONResponse(
            jsonable_encoder({"data": result, **({"page": page} if page else {})}),
            status_code=self.status_code or 200,
        )


def dispatch(context, company_id, path, method, q, values, key):
    parts = path.strip("/").split("/")
    resource = parts[0]
    id = q.pop("id", None)
    if "kind" in q:
        q["document_kind" if resource == "documents" else "source_kind"] = q.pop("kind")
    operation = parts[2] if len(parts) > 2 else "create" if id is None else "edit"
    if method == "GET":
        if resource in {"comments", "calendar", "notifications", "channels"}:
            if resource == "channels" and len(parts) > 2:
                resource = "messages"
            return company_collaboration.query(
                context, company_id, resource, **q, **({"id": id} if id else {})
            ), None
        if resource in {"authority-rules", "delegations"}:
            data = company_policy.read(context, company_id, resource, **q)
        else:
            kind = "people" if resource == "people-master" else resource
            data = company_service.read(context, company_id, kind, id, **q)
        if resource in {"people-master", "authority-rules"}:
            return data["rows"], {k: data[k] for k in ("total", "offset", "limit")}
        if resource == "people-options":
            return data["rows"], {k: data[k] for k in ("total", "offset", "limit")}
        return data, None
    if resource in {"comments", "calendar", "notifications", "channels"}:
        if resource == "channels" and operation == "messages":
            resource, operation = "messages", "send"
        return company_collaboration.mutate(
            context, company_id, resource, id, operation, values, key
        ), None
    if resource in {"authority-rules", "delegations"}:
        if method == "DELETE":
            operation = "delete"
        return company_policy.mutate(
            context, company_id, resource, id, operation, values, key
        ), None
    if resource in {"people", "people-master"}:
        return company_service.mutate_person(context, company_id, id, values, key), None
    if resource == "import-hr":
        from fs.gw import company_identity, organization

        def run(c, ctx, p):
            result = organization.import_snapshot(c, ctx, values)
            company_identity.bump(c, ctx)
            company_identity.audit(
                c,
                ctx,
                "organization_unit",
                ctx.workspace_id,
                "import-hr",
                values["reason"],
            )
            return result

        return company.action(
            context,
            company_id,
            "company.import-hr",
            key,
            values,
            run,
            authorize=lambda c, ctx, p: company.principal(c, ctx, "ORG_ADMIN"),
        ), None
    if resource not in {"documents", "posts", "routes"}:
        company_work.not_found()
    return company_work.mutate(
        context, company_id, resource, id, operation, values, key
    ), None
