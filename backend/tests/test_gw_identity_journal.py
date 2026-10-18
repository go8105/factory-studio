"""Real PostgreSQL/HTTP connection revocation and journal storage failure."""

from uuid import uuid4

from sqlalchemy import text
from test_gw_company_work import api, connect_staff, initialize
from test_hr_work import company_env  # noqa: F401
from test_security_journal import journal  # noqa: F401

from fs.core.security.journal import verify


def test_http_revocation_record_and_storage_failure(company_env, journal):  # noqa: F811
    engine, co, admin, _ = company_env
    directory, key = journal
    initialize(company_env)
    assert verify(directory, key)["records"] == 1
    _, binding = connect_staff(company_env)
    assert verify(directory, key)["records"] == 3

    def current():
        with engine.connect() as c:
            return c.execute(
                text(
                    "SELECT state,version FROM gw.person_identity_binding WHERE id=:id"
                ),
                {"id": int(binding)},
            ).one()

    before = current()
    values = {"expectedVersion": before.version, "reason": "합성 연결 회수 검증"}
    idempotency_key = str(uuid4())
    directory.chmod(0o755)
    failed = api(
        admin, co, f"identity-bindings/{binding}/suspend", values, key=idempotency_key
    )
    assert failed.status_code == 503
    assert failed.json()["error"]["code"] == "SECURITY_JOURNAL_UNAVAILABLE"
    assert current() == before
    directory.chmod(0o700)
    saved = api(
        admin, co, f"identity-bindings/{binding}/suspend", values, key=idempotency_key
    )
    assert saved.status_code == 200
    assert current().state == "SUSPENDED"
    state = verify(directory, key)
    assert state["records"] == 4 and not state["completenessConfirmed"]
    assert (
        api(
            admin,
            co,
            f"identity-bindings/{binding}/suspend",
            values,
            key=idempotency_key,
        ).status_code
        == 200
    )
    assert verify(directory, key)["records"] == 4
