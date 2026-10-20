"""Real HTTP identity transitions with fail-closed journal storage and retries."""

# ruff: noqa: F811
from uuid import uuid4

import pytest
from fs.core.security.journal import verified_records, verify
from fs.gw.security_journal import confirm_records
from sqlalchemy import text
from test_gw_company_work import api, connect_staff, import_staff, initialize, ok
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401


def snapshot(engine, company):
    with engine.connect() as c:
        generation = c.scalar(
            text("SELECT active_generation_id FROM core.workspace WHERE id=:w"),
            {"w": company["companyId"]},
        )
        params = {"w": company["companyId"], "g": generation}
        return tuple(
            tuple(
                c.execute(
                    text(
                        f"SELECT {columns} FROM {table} WHERE workspace_id=:w AND generation_id=:g ORDER BY {order}"
                    ),
                    params,
                ).tuples()
            )
            for table, columns, order in (
                ("gw.person_identity_binding", "id,state,version", "id"),
                ("gw.person", "id,version", "id"),
                ("gw.role_grant", "id,role_key,is_active", "id"),
                ("gw.collaboration_settings", "authz_version", "authz_version"),
                (
                    "core.request_receipt",
                    "operation_key,request_key",
                    "operation_key,request_key",
                ),
            )
        )


def fail_then_retry(
    env, journal, path, values, *, method="POST", access_path="posts", before_access=403
):
    engine, company, admin, staff = env
    directory, key = journal
    before = snapshot(engine, company)
    count = verify(directory, key)["records"]
    request = str(uuid4())
    directory.chmod(0o755)
    try:
        response = api(admin, company, path, values, method=method, key=request)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "SECURITY_JOURNAL_UNAVAILABLE"
        assert snapshot(engine, company) == before
    finally:
        directory.chmod(0o700)
    assert verify(directory, key)["records"] == count
    assert api(staff, company, access_path, method="GET").status_code == before_access
    saved = ok(api(admin, company, path, values, method=method, key=request))
    after = snapshot(engine, company)
    assert verify(directory, key)["records"] == count + 1
    assert ok(api(admin, company, path, values, method=method, key=request)) == saved
    assert snapshot(engine, company) == after
    assert verify(directory, key)["records"] == count + 1
    return saved


def assert_confirmed(engine, journal, operation):
    directory, key = journal
    state = verify(directory, key)
    _, records = verified_records(directory, key, state["head"])
    with engine.connect() as c:
        assert confirm_records(c, records)["commitsConfirmed"]
    assert any(r["payload"]["operation"] == operation for r in records)
    assert not state["completenessConfirmed"]


@pytest.mark.parametrize("operation", ["cancel", "resume"])
def test_binding_transition_storage_rollback_and_access(
    company_env, journal, operation
):
    engine, company, admin, staff = company_env
    initialize(company_env)
    person, user = import_staff(company_env)
    pending = ok(
        api(
            admin,
            company,
            "identity-bindings",
            {"personId": str(person), "userId": str(user), "reason": "합성 연결 요청"},
        )
    )
    current = pending
    if operation == "resume":
        accepted = ok(
            api(
                staff,
                company,
                "me/binding/accept",
                {"bindingId": pending["id"], "expectedVersion": pending["version"]},
            )
        )
        current = ok(
            api(
                admin,
                company,
                f"identity-bindings/{pending['id']}/suspend",
                {"expectedVersion": accepted["version"], "reason": "합성 재개 준비"},
            )
        )
    assert api(staff, company, "posts", method="GET").status_code == 403
    values = {"expectedVersion": current["version"], "reason": "합성 상태 전이"}
    path = f"identity-bindings/{pending['id']}/{operation}"
    before = snapshot(engine, company)
    assert api(staff, company, path, values).status_code == 403
    assert snapshot(engine, company) == before
    saved = fail_then_retry(company_env, journal, path, values)
    assert saved["state"] == ("CANCELLED" if operation == "cancel" else "ACTIVE")
    assert api(staff, company, "posts", method="GET").status_code == (
        403 if operation == "cancel" else 200
    )
    after = snapshot(engine, company)
    assert api(admin, company, path, values).status_code == 409
    assert snapshot(engine, company) == after
    if operation == "cancel":
        assert (
            api(
                staff,
                company,
                "me/binding/accept",
                {"bindingId": pending["id"], "expectedVersion": saved["version"]},
            ).status_code
            == 403
        )
    assert_confirmed(engine, journal, f"binding.{pending['id']}.{operation}")


@pytest.mark.parametrize("change", ["grant", "revoke"])
def test_role_transition_storage_rollback_and_access(company_env, journal, change):
    engine, company, admin, staff = company_env
    own = initialize(company_env)
    person, _binding = connect_staff(company_env)
    path = f"people/{person}/roles"
    current = ok(api(admin, company, path, method="GET"))
    if change == "revoke":
        current = ok(
            api(
                admin,
                company,
                path,
                {
                    "expectedVersion": current["version"],
                    "roles": ["SECURITY_ADMIN"],
                    "reason": "합성 역할 회수 준비",
                },
                method="PATCH",
            )
        )
    expected_before = 403 if change == "grant" else 200
    assert (
        api(staff, company, "security-events", method="GET").status_code
        == expected_before
    )
    values = {
        "expectedVersion": current["version"],
        "roles": ["SECURITY_ADMIN"] if change == "grant" else [],
        "reason": "합성 역할 변경",
    }
    saved = fail_then_retry(
        company_env,
        journal,
        path,
        values,
        method="PATCH",
        access_path="security-events",
        before_access=expected_before,
    )
    assert saved["roles"] == values["roles"]
    assert api(staff, company, "security-events", method="GET").status_code == (
        200 if change == "grant" else 403
    )
    after = snapshot(engine, company)
    assert api(admin, company, path, values, method="PATCH").status_code == 409
    assert snapshot(engine, company) == after
    if change == "revoke":
        assert api(staff, company, path, values, method="PATCH").status_code == 403
        own_roles = ok(api(admin, company, f"people/{own}/roles", method="GET"))
        assert (
            api(
                admin,
                company,
                f"people/{own}/roles",
                {
                    "expectedVersion": own_roles["version"],
                    "roles": [],
                    "reason": "합성 마지막 관리자 보호",
                },
                method="PATCH",
            ).status_code
            == 409
        )
        assert snapshot(engine, company) == after
    assert_confirmed(engine, journal, f"roles.{person}")
