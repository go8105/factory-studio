"""FS-030 GW API. All writes require CSRF and an idempotency key."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header, Query

from fs.common import master
from fs.common.auth import AuthContext, resolve_auth
from fs.common.engine import mutation_key
from fs.gw import policy, schema, service

router = APIRouter()
Auth = Annotated[AuthContext, Depends(resolve_auth)]
Key = Annotated[str | None, Header(alias="Idempotency-Key")]
Csrf = Annotated[str | None, Header(alias="X-CSRF-Token")]
Person = Annotated[int | None, Query(alias="personId", gt=0)]
Offset = Annotated[int, Query(ge=0)]
Limit = Annotated[int, Query(ge=1, le=100)]
Search = Annotated[str, Query(max_length=100)]


def write(ctx, csrf, key, kind, id, action, payload):
    mutation_key(ctx, csrf, key)
    return {
        "data": service.mutate(
            ctx, kind, id, action, _values(payload, full=id is None), key
        )
    }


def _values(payload, full=False):
    return payload.model_dump(exclude_unset=not full)


@router.get("/dashboard")
def dashboard(context: Auth, person_id: Person = None):
    return {"data": service.read(context, "dashboard", person_id=person_id)}


@router.get("/sources")
def sources(
    context: Auth,
    kind: Literal[
        "PURCHASE_INVOICE", "PURCHASE_ORDER", "EXPENSE_CLAIM", "ECO"
    ] = "PURCHASE_INVOICE",
    search: Search = "",
    offset: Offset = 0,
    limit: Limit = 50,
):
    return {
        "data": service.read(
            context,
            "sources",
            source_kind=kind,
            search=search,
            offset=offset,
            limit=limit,
        )
    }


@router.get("/sources/{kind}/{document_no}")
def source(
    context: Auth,
    kind: Literal["PURCHASE_INVOICE", "PURCHASE_ORDER", "EXPENSE_CLAIM", "ECO"],
    document_no: str,
):
    return {"data": service.read(context, "sources", document_no, source_kind=kind)}


@router.get("/documents")
def documents(
    context: Auth,
    person_id: Person = None,
    box: Literal["drafts", "pending", "archive", "all"] = "all",
    status: Literal["DRAFT", "IN_REVIEW", "APPROVED", "REJECTED", "WITHDRAWN"]
    | None = None,
    kind: schema.DocumentKind | None = None,
    search: Search = "",
    offset: Offset = 0,
    limit: Limit = 50,
    sort: Literal["serial", "status", "title"] = "serial",
):
    return {
        "data": service.read(
            context,
            "documents",
            person_id=person_id,
            box=box,
            status=status,
            document_kind=kind,
            search=search,
            offset=offset,
            limit=limit,
            sort=sort,
        )
    }


@router.get("/posts")
def posts(
    context: Auth,
    person_id: Person = None,
    board_kind: Annotated[
        Literal["NOTICE", "FREE"] | None, Query(alias="boardKind")
    ] = None,
    status: Literal["DRAFT", "PUBLISHED", "WITHDRAWN"] | None = None,
    mine: bool = False,
    search: Search = "",
    offset: Offset = 0,
    limit: Limit = 50,
    sort: Literal["serial", "status", "title"] = "serial",
):
    return {
        "data": service.read(
            context,
            "posts",
            person_id=person_id,
            board_kind=board_kind,
            status=status,
            mine=mine,
            search=search,
            offset=offset,
            limit=limit,
            sort=sort,
        )
    }


@router.get("/people")
def list_people(
    context: Auth, search: Search = "", offset: Offset = 0, limit: Limit = 50
):
    return {
        "data": service.read(
            context, "people", search=search, offset=offset, limit=limit
        )
    }


@router.get("/people/{id}")
def get_people(id: int, context: Auth, person_id: Person = None):
    return {"data": service.read(context, "people", id, person_id=person_id)}


@router.post("/people", status_code=201)
def post_people(
    payload: schema.PersonCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "people", None, "create", payload)


@router.patch("/people/{id}")
def patch_people(
    id: int,
    payload: schema.PersonUpdate,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return write(context, csrf, key, "people", id, "edit", payload)


@router.get("/routes")
def list_routes(
    context: Auth, search: Search = "", offset: Offset = 0, limit: Limit = 50
):
    return {
        "data": service.read(
            context, "routes", search=search, offset=offset, limit=limit
        )
    }


@router.get("/routes/{id}")
def get_routes(id: int, context: Auth, person_id: Person = None):
    return {"data": service.read(context, "routes", id, person_id=person_id)}


@router.post("/routes", status_code=201)
def post_routes(
    payload: schema.RouteCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "routes", None, "create", payload)


@router.patch("/routes/{id}")
def patch_routes(
    id: int,
    payload: schema.RouteUpdate,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return write(context, csrf, key, "routes", id, "edit", payload)


@router.get("/documents/{id}")
def get_documents(id: int, context: Auth, person_id: Person = None):
    return {"data": service.read(context, "documents", id, person_id=person_id)}


@router.post("/documents", status_code=201)
def post_documents(
    payload: schema.DocumentCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", None, "create", payload)


@router.patch("/documents/{id}")
def patch_documents(
    id: int,
    payload: schema.DocumentUpdate,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return write(context, csrf, key, "documents", id, "edit", payload)


@router.get("/posts/{id}")
def get_posts(id: int, context: Auth, person_id: Person = None):
    return {"data": service.read(context, "posts", id, person_id=person_id)}


@router.post("/posts", status_code=201)
def post_posts(
    payload: schema.PostCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "posts", None, "create", payload)


@router.patch("/posts/{id}")
def patch_posts(
    id: int,
    payload: schema.PostUpdate,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return write(context, csrf, key, "posts", id, "edit", payload)


@router.post("/documents/{id}/select-route")
def documents_select_route(
    id: int,
    payload: schema.RouteSelect,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return write(context, csrf, key, "documents", id, "select-route", payload)


@router.post("/documents/{id}/refresh-source")
def documents_refresh_source(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "refresh-source", payload)


@router.post("/documents/{id}/submit")
def documents_submit(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "submit", payload)


@router.post("/documents/{id}/approve")
def documents_approve(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "approve", payload)


@router.post("/documents/{id}/reject")
def documents_reject(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "reject", payload)


@router.post("/documents/{id}/withdraw")
def documents_withdraw(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "withdraw", payload)


@router.post("/documents/{id}/resubmit")
def documents_resubmit(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "resubmit", payload)


@router.post("/posts/{id}/publish")
def posts_publish(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "posts", id, "publish", payload)


@router.post("/posts/{id}/withdraw")
def posts_withdraw(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "posts", id, "withdraw", payload)


@router.post("/posts/{id}/correct")
def posts_correct(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "posts", id, "correct", payload)


@router.get("/authority-rules")
def authority_rules(context: Auth, offset: Offset = 0, limit: Limit = 50):
    rows, total = master.listing(policy.AUTHORITY, context, offset=offset, limit=limit)
    return {"data": rows, "page": {"total": total, "offset": offset, "limit": limit}}


@router.post("/authority-rules", status_code=201)
def create_authority(
    payload: schema.AuthorityCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return {
        "data": policy.rules_write(
            context,
            None,
            "create",
            _values(payload, full=True),
            mutation_key(context, csrf, key),
        )
    }


@router.patch("/authority-rules/{id}")
def patch_authority(
    id: int,
    payload: schema.AuthorityPatch,
    context: Auth,
    csrf: Csrf = None,
    key: Key = None,
):
    return {
        "data": policy.rules_write(
            context, id, "edit", _values(payload), mutation_key(context, csrf, key)
        )
    }


@router.delete("/authority-rules/{id}", status_code=204)
def delete_authority(id: int, context: Auth, csrf: Csrf = None, key: Key = None):
    policy.rules_write(
        context, id, "delete", {"id": id}, mutation_key(context, csrf, key)
    )


@router.get("/delegations")
def list_delegations(context: Auth, offset: Offset = 0, limit: Limit = 50):
    return {"data": policy.delegations(context, offset, limit)}


@router.post("/delegations", status_code=201)
def create_delegation(
    payload: schema.DelegationCreate, context: Auth, csrf: Csrf = None, key: Key = None
):
    return {
        "data": policy.delegation_write(
            context, None, _values(payload, full=True), mutation_key(context, csrf, key)
        )
    }


@router.post("/delegations/{id}/revoke")
def revoke_delegation(
    id: int, payload: schema.Act, context: Auth, csrf: Csrf = None, key: Key = None
):
    return {
        "data": policy.delegation_write(
            context, id, _values(payload), mutation_key(context, csrf, key)
        )
    }


@router.post("/documents/{id}/consent")
def consent_document(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "consent", payload)


@router.post("/documents/{id}/oppose")
def oppose_document(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "oppose", payload)


@router.post("/documents/{id}/reference")
def reference_document(
    id: int, payload: schema.Decision, context: Auth, csrf: Csrf = None, key: Key = None
):
    return write(context, csrf, key, "documents", id, "reference", payload)
