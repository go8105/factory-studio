"""FS-026b1 AC-140~150: API, PostgreSQL atomicity and source routing."""

from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from decimal import Decimal
from threading import Barrier
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from test_wms import W, _call, _clear, _ok, _reason, _setup, _sync


@pytest.fixture
def receiving_env(guest_space):
    client, auth, engine = guest_space
    _clear(engine, auth)
    ids = _setup(client, auth)
    wh = next(x for x in _ok(client.get(W + "/warehouses")) if x["code"] == "WH-RAW")
    ids["warehouse"] = wh["id"]
    ids["quarantine"] = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{wh['id']}/locations",
            {"code": "R-Q01", "name": "격리", "locationType": "QUARANTINE"},
        ),
        201,
    )["id"]
    return client, auth, engine, ids


def notice(env, qty="100", item="RM-PBT", **overrides):
    client, auth, _, ids = env
    body = {
        "businessKey": uuid4().hex,
        "warehouseId": ids["warehouse"],
        "expectedOn": "2026-09-24",
        "lines": [
            {
                "itemId": ids[item],
                "expectedQty": qty,
                "normalLocationId": ids["R-A01"],
                "quarantineLocationId": ids["quarantine"],
            }
        ],
    }
    body.update(overrides)
    return _ok(_call(client, auth, "POST", "/inbound-notices", body), 201)


def act(env, n, action, **values):
    return _call(
        env[0],
        env[1],
        "POST",
        f"/inbound-notices/{n['id']}/{action}",
        {"expectedVersion": n["version"], **values},
    )


def inspect_body(n, accepted="95", held="3", short="2"):
    return {
        "lines": [
            {
                "lineId": line["id"],
                "acceptedQty": accepted
                if i == 0
                else line["expectedQty"]
                if Decimal(accepted) > 0
                else "0",
                "quarantinedQty": held if i == 0 else "0",
                "shortageQty": short
                if i == 0
                else line["expectedQty"]
                if Decimal(accepted) == 0
                else "0",
                "reason": "입고 검수 차이",
            }
            for i, line in enumerate(n["lines"])
        ]
    }


def ledger(env):
    with env[2].connect() as c:
        return c.execute(
            text(
                "SELECT count(*),coalesce(sum(qty_delta),0) FROM wms.stock_move WHERE workspace_id=:w AND generation_id=:g"
            ),
            {"w": env[1]["workspaceId"], "g": env[1]["generationId"]},
        ).one()


def source_notice(env, ref="PI-0004"):
    rows = _ok(
        env[0].get(W + "/sources", params={"kind": "ERP_PURCHASE", "state": "all"})
    )["rows"]
    src = next(x for x in rows if x["sourceRef"] == ref)
    ids = env[3]
    lines = [
        {
            "itemId": ids[line["itemCode"]],
            "expectedQty": format(
                Decimal(line["qty"]) * (10000 if line["unit"] == "BOX" else 1), "f"
            ),
            "normalLocationId": ids["R-A01"],
            "quarantineLocationId": ids["quarantine"],
        }
        for line in src["lines"]
    ]
    return notice(env, lines=lines), src


def link(env, n, src):
    return _ok(act(env, n, "source-link", sourceKey=src["sourceKey"]))


def test_arrival_and_inspection_clock_quantity_replay(receiving_env, monkeypatch):
    env = receiving_env
    monkeypatch.setenv("FS_TODAY", "1999-01-01")
    n = notice(env)
    a = _ok(act(env, n, "arrive"))
    repeated = _ok(act(env, n, "arrive"))
    assert a["arrivedAt"] == repeated["arrivedAt"] and ledger(env) == (0, 0)
    done = _ok(act(env, a, "inspect", **inspect_body(a)))
    replay = _ok(act(env, a, "inspect", **inspect_body(a)))
    assert replay["stockDocumentId"] == done["stockDocumentId"]
    assert ledger(env) == (2, Decimal(98))
    doc = _ok(env[0].get(f"{W}/documents/{done['stockDocumentId']}"))
    assert doc["documentOn"] != "1999-01-01"
    assert doc["postedAt"] == done["inspectedAt"]
    assert doc["documentNo"].startswith("WD-" + doc["documentOn"].replace("-", ""))
    assert sorted(Decimal(x["qtyDelta"]) for x in doc["moves"]) == [3, 95]
    assert all(x["movedAt"] == done["inspectedAt"] for x in doc["moves"])
    assert _ok(env[0].get(f"{W}/inbound-notices/{n['id']}"))["status"] == "INSPECTED"
    assert (
        _ok(env[0].get(W + "/inbound-notices", params={"status": "INSPECTED"}))["total"]
        == 1
    )
    assert act(env, a, "inspect", **inspect_body(a, "94", "4", "2")).status_code == 409


def test_all_short_claim_prevents_later_sync(receiving_env):
    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    batch = _sync(
        env[0], env[1], "ERP_PURCHASE", src["sourceKey"], "ERP:PURCHASE:PI-0001"
    )
    assert batch["deferred"] == 1 and batch["synced"] == 1 and batch["blocked"] == 0
    before = ledger(env)
    n = _ok(act(env, n, "arrive"))
    done = _ok(
        act(
            env, n, "inspect", **inspect_body(n, "0", "0", n["lines"][0]["expectedQty"])
        )
    )
    assert (
        done["stockDocumentId"] is None and done["sourceClaim"]["status"] == "COMPLETED"
    )
    result = _sync(env[0], env[1], "ERP_PURCHASE", src["sourceKey"])
    assert result["inspected"] == 1 and result["synced"] == 0 and ledger(env) == before
    listed = _ok(
        env[0].get(W + "/sources", params={"kind": "ERP_PURCHASE", "state": "synced"})
    )["rows"]
    assert (
        next(x for x in listed if x["sourceKey"] == src["sourceKey"])["documentId"]
        is None
    )


@pytest.mark.parametrize(
    "case",
    ["sum", "negative", "precision", "missing", "duplicate", "unknown", "reason"],
)
def test_bad_quantities_are_400_and_atomic(receiving_env, case):
    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    body = inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
    row = body["lines"][0]
    if case == "sum":
        row["acceptedQty"] = "0"
    if case == "negative":
        row["acceptedQty"] = "-1"
    if case == "precision":
        row["acceptedQty"] = "0.0001"
    if case == "missing":
        body["lines"] = []
    if case == "duplicate":
        body["lines"].append(dict(row))
    if case == "unknown":
        row["lineId"] += 999999
    if case == "reason":
        row.update(
            acceptedQty="0", shortageQty=n["lines"][0]["expectedQty"], reason=" "
        )
    r = act(env, n, "inspect", **body)
    assert r.status_code == 400, r.text
    assert r.json()["error"]["code"] == "VALIDATION_FAILED"
    assert r.json()["error"]["details"]["fields"]
    current = _ok(env[0].get(f"{W}/inbound-notices/{n['id']}"))
    assert (
        current["version"] == n["version"]
        and current["sourceClaim"]["status"] == "CLAIMED"
        and ledger(env) == (0, 0)
    )


def test_claim_release_cancel_direct_route_and_posthoc(receiving_env):
    env = receiving_env
    n, src = source_notice(env)
    other, _ = source_notice(env)
    linked = link(env, n, src)
    assert (
        _reason(act(env, other, "source-link", sourceKey=src["sourceKey"]))
        == "SOURCE_CLAIMED"
    )
    unlinked = _ok(act(env, linked, "source-unlink", reason="배정 변경"))
    linked = link(env, other, src)
    _ok(act(env, linked, "cancel", reason="예정 취소"))
    linked = link(env, unlinked, src)
    _ok(act(env, linked, "source-unlink", reason="직접 반영"))
    _sync(env[0], env[1], "ERP_PURCHASE", src["sourceKey"])
    assert _reason(act(env, unlinked, "source-link", sourceKey=src["sourceKey"])) in {
        "STALE_VERSION",
        "SOURCE_ALREADY_POSTED",
    }
    fresh, _ = source_notice(env)
    assert (
        _reason(act(env, fresh, "source-link", sourceKey=src["sourceKey"]))
        == "SOURCE_ALREADY_POSTED"
    )
    manual, src2 = source_notice(env, "PI-0002")
    manual = _ok(act(env, manual, "arrive"))
    done = _ok(
        act(
            env,
            manual,
            "inspect",
            **inspect_body(manual, manual["lines"][0]["expectedQty"], "0", "0"),
        )
    )
    before = ledger(env)
    done = link(env, done, src2)
    assert done["sourceClaim"]["status"] == "COMPLETED"
    assert _sync(env[0], env[1], "ERP_PURCHASE", src2["sourceKey"])["inspected"] == 1
    assert ledger(env) == before


def _cancel_invoice(env, ref):
    invoice = next(
        x
        for x in _ok(env[0].get("/api/v1/erp/purchase-invoices"))
        if x["invoiceNo"] == ref
    )
    return _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/api/v1/erp/purchase-invoices/{invoice['id']}/cancel",
            {"reason": "검수 원천 취소"},
        )
    )


@pytest.mark.parametrize("after", [False, True])
def test_source_cancellation_does_not_reverse_inspection(receiving_env, after):
    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    body = inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
    if after:
        n = _ok(act(env, n, "inspect", **body))
    before = ledger(env)
    _cancel_invoice(env, "PI-0004")
    if not after:
        r = act(env, n, "inspect", **body)
        assert r.status_code == 409 and _reason(r) == "SOURCE_CANCELLED"
    else:
        result = _sync(env[0], env[1], "ERP_PURCHASE", src["sourceKey"])
        assert result["results"][0]["state"] == "inspected_cancelled"
    assert ledger(env) == before


def test_digest_ignores_time_but_detects_meaning(receiving_env, monkeypatch):
    from fs.wms import receiving

    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    original = receiving.erp.purchase_receipts

    def altered(c, scope):
        rows = deepcopy(original(c, scope))
        for row in rows:
            row["confirmedAt"] = "2001-02-03T04:05:06+00:00"
        return rows

    monkeypatch.setattr(receiving.erp, "purchase_receipts", altered)
    n = _ok(
        act(
            env, n, "inspect", **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
        )
    )
    assert n["sourceClaim"]["status"] == "COMPLETED"
    other, src2 = source_notice(env, "PI-0002")
    other = link(env, other, src2)
    other = _ok(act(env, other, "arrive"))

    def changed(c, scope):
        rows = altered(c, scope)
        for row in rows:
            if row["invoiceNo"] == "PI-0002":
                row["lines"][0]["qty"] = str(Decimal(row["lines"][0]["qty"]) + 1)
        return rows

    monkeypatch.setattr(receiving.erp, "purchase_receipts", changed)
    before = ledger(env)
    assert (
        _reason(
            act(
                env,
                other,
                "inspect",
                **inspect_body(other, other["lines"][0]["expectedQty"], "0", "0"),
            )
        )
        == "SOURCE_CHANGED"
    )
    assert ledger(env) == before


@pytest.mark.parametrize("race", ["link", "inspect"])
def test_real_connections_source_race(receiving_env, race, monkeypatch):
    from fs.common import engine as scope

    env = receiving_env
    n, src = source_notice(env)
    if race == "inspect":
        n = link(env, n, src)
        n = _ok(act(env, n, "arrive"))
    barrier = Barrier(2)
    pids = set()
    original = scope.write_scope

    def lock(c, *args, **kwargs):
        pids.add(c.execute(text("SELECT pg_backend_pid()")).scalar_one())
        barrier.wait(timeout=15)
        return original(c, *args, **kwargs)

    monkeypatch.setattr(scope, "write_scope", lock)

    def call_action():
        with TestClient(env[0].app, base_url=str(env[0].base_url)) as client:
            client.cookies.update(env[0].cookies)
            parallel = (client, *env[1:])
            return (
                act(parallel, n, "source-link", sourceKey=src["sourceKey"])
                if race == "link"
                else act(
                    parallel,
                    n,
                    "inspect",
                    **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0"),
                )
            )

    def call_sync():
        with TestClient(env[0].app, base_url=str(env[0].base_url)) as client:
            client.cookies.update(env[0].cookies)
            return _call(
                client,
                env[1],
                "POST",
                "/sources/sync",
                {"kind": "ERP_PURCHASE", "sourceKeys": [src["sourceKey"]]},
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        a = pool.submit(call_action)
        b = pool.submit(call_sync)
        a = a.result()
        b = b.result()
    assert len(pids) == 2
    assert a.status_code in {200, 409} and b.status_code == 200
    result = b.json()["data"]["results"][0]
    if race == "inspect":
        assert ledger(env) == (
            len(n["lines"]),
            sum(Decimal(x["expectedQty"]) for x in n["lines"]),
        )
    elif a.status_code == 200:
        assert result["state"] == "inspection_pending" and ledger(env) == (0, 0)
    else:
        assert result["state"] == "synced" and ledger(env) == (
            len(n["lines"]),
            sum(Decimal(x["expectedQty"]) for x in n["lines"]),
        )


def test_master_reference_and_location_type_rules(receiving_env):
    env = receiving_env
    n = notice(env)
    ids = env[3]
    for path, body in [
        (f"/warehouses/{ids['warehouse']}", {"isActive": False}),
        (f"/items/{ids['RM-PBT']}", {"isActive": False}),
        (f"/locations/{ids['quarantine']}", {"isActive": False}),
        (f"/locations/{ids['quarantine']}", {"locationType": "NORMAL"}),
    ]:
        assert _call(env[0], env[1], "PATCH", path, body).status_code == 409
    assert (
        _call(env[0], env[1], "DELETE", f"/locations/{ids['quarantine']}").status_code
        == 409
    )
    r = _call(
        env[0], env[1], "PATCH", f"/locations/{ids['quarantine']}", {"isDefault": True}
    )
    assert r.status_code == 400
    _ok(act(env, n, "cancel", reason="취소"))
    _ok(
        _call(
            env[0],
            env[1],
            "PATCH",
            f"/locations/{ids['quarantine']}",
            {"isActive": False},
        )
    )
    # Retained history still prevents deletion or type mutation.
    assert (
        _call(env[0], env[1], "DELETE", f"/locations/{ids['quarantine']}").status_code
        == 409
    )


def test_version_idempotency_and_planned_edit(receiving_env):
    env = receiving_env
    n = notice(env)
    body = {
        "expectedVersion": n["version"],
        "warehouseId": env[3]["warehouse"],
        "expectedOn": "2026-10-01",
        "lines": [
            {
                "itemId": env[3]["RM-PBT"],
                "expectedQty": "101",
                "normalLocationId": env[3]["R-A01"],
            }
        ],
    }
    revised = _ok(_call(env[0], env[1], "PATCH", f"/inbound-notices/{n['id']}", body))
    assert revised["version"] == 2 and revised["lines"][0]["expectedQty"] == "101.000"
    assert _reason(act(env, n, "arrive")) == "STALE_VERSION"
    headers = {
        "X-CSRF-Token": env[1]["csrfToken"],
        "Idempotency-Key": "arrival-receipt",
    }
    url = f"{W}/inbound-notices/{n['id']}/arrive"
    a = env[0].post(url, json={"expectedVersion": 2}, headers=headers)
    b = env[0].post(url, json={"expectedVersion": 2}, headers=headers)
    assert _ok(a) == _ok(b)
    different = env[0].post(url, json={"expectedVersion": 3}, headers=headers)
    assert (
        different.status_code == 422
        and different.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"
    )
    assert (
        _call(
            env[0],
            env[1],
            "PATCH",
            f"/inbound-notices/{n['id']}",
            {**body, "expectedVersion": 3},
        ).status_code
        == 409
    )


def test_erp_disabled_manual_and_guest_isolation(receiving_env):
    from test_wms import _other_guest

    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    _ok(
        _call(
            env[0],
            env[1],
            "PATCH",
            "/api/v1/core/workspace/modules/erp",
            {"enabled": False},
        )
    )
    r = act(
        env, n, "inspect", **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
    )
    assert r.status_code == 409 and _reason(r) == "SOURCE_MODULE_DISABLED"
    manual = notice(env)
    manual = _ok(act(env, manual, "arrive"))
    _ok(act(env, manual, "inspect", **inspect_body(manual)))
    other, auth = _other_guest(env[0])
    try:
        assert other.get(f"{W}/inbound-notices/{n['id']}").status_code == 404
        assert (
            _call(
                other,
                auth,
                "POST",
                f"/inbound-notices/{n['id']}/arrive",
                {"expectedVersion": n["version"]},
            ).status_code
            == 404
        )
    finally:
        other.close()
    _ok(_call(env[0], env[1], "POST", "/api/v1/core/workspace/generations"), 201)
    assert env[0].get(f"{W}/inbound-notices/{n['id']}").status_code == 404


def test_conversion_missing_precision_and_changed_factor(receiving_env, monkeypatch):
    from fs.wms import receiving

    env = receiving_env
    n, src = source_notice(env)
    conversion = next(
        x for x in _ok(env[0].get(W + "/items")) if x["itemCode"] == "RM-PIN"
    )["conversions"][0]
    _ok(
        _call(
            env[0],
            env[1],
            "DELETE",
            f"/items/{env[3]['RM-PIN']}/conversions/{conversion['id']}",
        )
    )
    assert act(env, n, "source-link", sourceKey=src["sourceKey"]).status_code == 400
    _ok(
        _call(
            env[0],
            env[1],
            "POST",
            f"/items/{env[3]['RM-PIN']}/conversions",
            {"fromUnit": "BOX", "factor": "0.000001"},
        ),
        201,
    )
    assert act(env, n, "source-link", sourceKey=src["sourceKey"]).status_code == 400
    original = receiving.base._items_by_code

    def restored(c, scope):
        items = original(c, scope)
        items["RM-PIN"]["factors"]["BOX"] = Decimal(10000)
        return items

    monkeypatch.setattr(receiving.base, "_items_by_code", restored)
    n = link(env, n, src)
    pin = next(
        x
        for x in n["sourceClaim"]["sourceSnapshot"]["lines"]
        if x["itemCode"] == "RM-PIN"
    )
    assert pin["sources"] == [{"unit": "BOX", "factor": "10000", "qty": "6"}]
    n = _ok(act(env, n, "arrive"))
    monkeypatch.setattr(receiving.base, "_items_by_code", original)
    before = ledger(env)
    assert (
        act(
            env, n, "inspect", **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
        ).status_code
        == 400
    )
    assert ledger(env) == before

    def changed(c, scope):
        items = restored(c, scope)
        items["RM-PIN"]["factors"]["BOX"] = Decimal(20000)
        return items

    monkeypatch.setattr(receiving.base, "_items_by_code", changed)
    assert (
        _reason(
            act(
                env,
                n,
                "inspect",
                **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0"),
            )
        )
        == "SOURCE_CHANGED"
    )
    assert ledger(env) == before


def test_guest_copy_preserves_digest_shifts_snapshot_and_keys(receiving_env):
    from datetime import date, datetime, timedelta

    from seed.copy import copy_template

    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    n = _ok(
        act(
            env, n, "inspect", **inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
        )
    )
    with env[2].begin() as c:
        seed_date = c.execute(
            text("SELECT seed_date FROM core.data_generation WHERE id=:g"),
            {"g": env[1]["generationId"]},
        ).scalar_one()
        w, g, _, _ = copy_template(
            c,
            env[1]["workspaceId"],
            env[1]["generationId"],
            seed_date + timedelta(days=5),
            "copy-" + uuid4().hex,
        )
        row = (
            c.execute(
                text(
                    "SELECT n.notice_no,d.source_key,d.source_ref,sc.source_digest,sc.source_snapshot FROM wms.inbound_notice n JOIN wms.stock_document d ON d.workspace_id=n.workspace_id AND d.generation_id=n.generation_id AND d.id=n.stock_document_id JOIN wms.source_claim sc ON sc.workspace_id=n.workspace_id AND sc.generation_id=n.generation_id AND sc.notice_id=n.id WHERE n.workspace_id=:w AND n.generation_id=:g"
                ),
                {"w": w, "g": g},
            )
            .mappings()
            .one()
        )
        assert row["source_digest"] == n["sourceClaim"]["sourceDigest"]
        before = n["sourceClaim"]["sourceSnapshot"]
        after = row["source_snapshot"]
        assert (
            after["lines"] == before["lines"]
            and after["invoiceNo"] == before["invoiceNo"]
        )
        assert datetime.fromisoformat(after["confirmedAt"]) - datetime.fromisoformat(
            before["confirmedAt"]
        ) == timedelta(days=5)
        assert (
            row["source_key"] == "WMS:INSPECTION:" + row["notice_no"]
            and row["source_ref"] == row["notice_no"]
        )
        assert date.fromisoformat(row["notice_no"][3:11]) - date.fromisoformat(
            n["noticeNo"][3:11]
        ) == timedelta(days=5)


def test_fractional_kg_and_canonical_source_order(receiving_env, monkeypatch):
    from fs.wms import receiving

    env = receiving_env
    original = receiving.erp.purchase_receipts

    def fractional(c, scope):
        rows = deepcopy(original(c, scope))
        for row in rows:
            if row["invoiceNo"] == "PI-0004":
                row["lines"] = [
                    {"itemCode": "RM-PBT", "qty": "0.025", "unit": "KG"},
                    {"itemCode": "RM-PBT", "qty": "0.100", "unit": "KG"},
                ]
        return rows

    monkeypatch.setattr(receiving.erp, "purchase_receipts", fractional)
    n = notice(env, "0.125")
    n = _ok(act(env, n, "source-link", sourceKey="ERP:PURCHASE:PI-0004"))
    assert n["sourceClaim"]["sourceSnapshot"]["lines"][0]["baseQty"] == "0.125"

    def reversed_lines(c, scope):
        rows = fractional(c, scope)
        for row in rows:
            row["lines"].reverse()
        return rows

    monkeypatch.setattr(receiving.erp, "purchase_receipts", reversed_lines)
    n = _ok(act(env, n, "arrive"))
    _ok(act(env, n, "inspect", **inspect_body(n, "0.125", "0", "0")))
    assert ledger(env) == (1, Decimal("0.125"))


def test_reordered_lines_error_points_to_input_position(receiving_env):
    env = receiving_env
    n, src = source_notice(env)
    n = link(env, n, src)
    n = _ok(act(env, n, "arrive"))
    body = inspect_body(n, n["lines"][0]["expectedQty"], "0", "0")
    body["lines"].reverse()
    body["lines"][0]["acceptedQty"] = "0"
    r = act(env, n, "inspect", **body)
    assert r.status_code == 400
    assert "lines.0.shortageQty" in r.json()["error"]["details"]["fields"]
    assert ledger(env) == (0, 0)


def test_inspection_document_number_survives_deleted_draft_gap(
    receiving_env, monkeypatch
):
    from datetime import date

    from fs.wms import service

    env = receiving_env
    # Number manually created drafts on the same real server day as the inspection.
    with env[2].connect() as c:
        day = c.execute(
            text("SELECT (clock_timestamp() AT TIME ZONE 'Asia/Seoul')::date")
        ).scalar_one()
    monkeypatch.setattr(service, "business_today", lambda: day)
    body = {
        "documentType": "OPENING",
        "documentOn": day.isoformat(),
        "lines": [
            {"itemId": env[3]["RM-PBT"], "locationId": env[3]["R-A01"], "qty": "1"}
        ],
    }
    a = _ok(_call(env[0], env[1], "POST", "/documents", body), 201)
    b = _ok(_call(env[0], env[1], "POST", "/documents", body), 201)
    _ok(_call(env[0], env[1], "DELETE", f"/documents/{a['id']}"))
    n = notice(env)
    n = _ok(act(env, n, "arrive"))
    n = _ok(act(env, n, "inspect", **inspect_body(n)))
    doc = _ok(env[0].get(f"{W}/documents/{n['stockDocumentId']}"))
    assert int(doc["documentNo"][12:]) == int(b["documentNo"][12:]) + 1
    assert date.fromisoformat(doc["documentOn"]) == day


def test_receiving_location_allowed_as_normal_location(receiving_env):
    env = receiving_env
    client, auth, _, ids = env
    rec_loc = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-REC-T", "name": "입고장 시험", "locationType": "RECEIVING"},
        ),
        201,
    )
    n = notice(
        env,
        qty="50",
        lines=[
            {
                "itemId": ids["RM-PBT"],
                "expectedQty": "50",
                "normalLocationId": rec_loc["id"],
            }
        ],
    )
    assert n["lines"][0]["normalLocationId"] == rec_loc["id"]

    n = _ok(act(env, n, "arrive"))
    n = _ok(
        act(env, n, "inspect", **inspect_body(n, accepted="50", held="0", short="0"))
    )
    assert n["status"] == "INSPECTED"

    bad_body = {
        "businessKey": uuid4().hex,
        "warehouseId": ids["warehouse"],
        "expectedOn": "2026-09-24",
        "lines": [
            {
                "itemId": ids["RM-PBT"],
                "expectedQty": "10",
                "normalLocationId": ids["quarantine"],
            }
        ],
    }
    r = _call(client, auth, "POST", "/inbound-notices", bad_body)
    assert r.status_code == 400
    assert "lines.0.normalLocationId" in r.json()["error"]["details"]["fields"]


def test_putaway_task_creation_and_idempotency_on_inspection(receiving_env):
    env = receiving_env
    client, auth, engine, ids = env
    rec_loc = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-REC-PT", "name": "입고장", "locationType": "RECEIVING"},
        ),
        201,
    )
    n = notice(
        env,
        qty="100",
        lines=[
            {
                "itemId": ids["RM-PBT"],
                "expectedQty": "100",
                "normalLocationId": rec_loc["id"],
                "quarantineLocationId": ids["quarantine"],
            },
            {
                "itemId": ids["RM-PIN"],
                "expectedQty": "50",
                "normalLocationId": rec_loc["id"],
                "quarantineLocationId": ids["quarantine"],
            },
        ],
    )
    n = _ok(act(env, n, "arrive"))
    insp_body = {
        "lines": [
            {
                "lineId": n["lines"][0]["id"],
                "acceptedQty": "70",
                "quarantinedQty": "20",
                "shortageQty": "10",
                "reason": "검수",
            },
            {
                "lineId": n["lines"][1]["id"],
                "acceptedQty": "0",
                "quarantinedQty": "50",
                "shortageQty": "0",
                "reason": "불량 전량 격리",
            },
        ]
    }
    n = _ok(act(env, n, "inspect", **insp_body))
    assert n["status"] == "INSPECTED"

    res = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    assert res["total"] == 1
    task = res["rows"][0]
    assert task["taskNo"].startswith("PT-")
    assert Decimal(task["qty"]) == Decimal(70)
    assert task["itemId"] == ids["RM-PBT"]
    assert task["fromLocationId"] == rec_loc["id"]
    assert task["status"] == "OPEN"
    assert task["toLocationId"] is None

    with engine.connect() as c:
        row = (
            c.execute(
                text(
                    "SELECT suggested_location_id, to_location_id, status FROM wms.putaway_task WHERE id=:id"
                ),
                {"id": task["id"]},
            )
            .mappings()
            .one()
        )
        assert row["suggested_location_id"] is None
        assert row["to_location_id"] is None
        assert row["status"] == "OPEN"

    act(env, n, "inspect", **insp_body)
    res_after = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    assert res_after["total"] == 1


def test_putaway_task_recommendation_algorithm_and_filters(receiving_env):
    env = receiving_env
    client, auth, engine, ids = env

    loc_same_lot = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-B01", "name": "1순위 후보", "locationType": "NORMAL"},
        ),
        201,
    )
    loc_same_item = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-B02", "name": "2순위 후보", "locationType": "NORMAL"},
        ),
        201,
    )
    loc_empty = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-B03", "name": "3순위 후보", "locationType": "NORMAL"},
        ),
        201,
    )
    loc_mix = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-B04", "name": "4순위 후보", "locationType": "NORMAL"},
        ),
        201,
    )
    rec_loc = _ok(
        _call(
            client,
            auth,
            "POST",
            f"/warehouses/{ids['warehouse']}/locations",
            {"code": "R-REC-AL", "name": "입고장", "locationType": "RECEIVING"},
        ),
        201,
    )

    with engine.connect() as c:
        c.execute(
            text(
                "UPDATE wms.storage_location SET capacity_qty=1 "
                "WHERE workspace_id=:w AND generation_id=:g AND id NOT IN (:loc1, :loc2, :loc3, :loc4, :rec, :q)"
            ),
            {
                "w": auth["workspaceId"],
                "g": auth["generationId"],
                "loc1": loc_same_lot["id"],
                "loc2": loc_same_item["id"],
                "loc3": loc_empty["id"],
                "loc4": loc_mix["id"],
                "rec": rec_loc["id"],
                "q": ids["quarantine"],
            },
        )
        c.commit()

    _ok(_call(client, auth, "PATCH", f"/items/{ids['RM-PBT']}", {"lotTracked": True}))

    opening = _ok(
        _call(
            client,
            auth,
            "POST",
            "/documents",
            {
                "documentType": "OPENING",
                "documentOn": "2026-10-18",
                "lines": [
                    {
                        "itemId": ids["RM-PBT"],
                        "locationId": loc_same_lot["id"],
                        "qty": "20",
                        "lotNo": "LOT-100",
                    },
                    {
                        "itemId": ids["RM-PBT"],
                        "locationId": loc_same_item["id"],
                        "qty": "20",
                        "lotNo": "LOT-200",
                    },
                    {
                        "itemId": ids["RM-PIN"],
                        "locationId": loc_mix["id"],
                        "qty": "20",
                    },
                ],
            },
        ),
        201,
    )
    _ok(_call(client, auth, "POST", f"/documents/{opening['id']}/post"))

    n = notice(
        env,
        qty="30",
        lines=[
            {
                "itemId": ids["RM-PBT"],
                "lotNo": "LOT-100",
                "expectedQty": "30",
                "normalLocationId": rec_loc["id"],
            }
        ],
    )
    n = _ok(act(env, n, "arrive"))
    n = _ok(
        act(env, n, "inspect", **inspect_body(n, accepted="30", held="0", short="0"))
    )

    # 1. 1순위: 같은 품목 + 같은 LOT이 있는 loc_same_lot (R-B01) 추천
    res = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    task = res["rows"][0]
    assert task["suggestedLocationId"] == loc_same_lot["id"]
    assert task["suggestedLocationCode"] == "R-B01"

    # 2. 용량 초과 및 LOT 혼적 차단 방어 테스트:
    # loc_same_lot: 용량 20으로 설정 -> 현재고 20 + 30 = 50 > 20 이므로 탈락!
    # loc_same_item: mix_lots = false 로 설정 -> 다른 LOT이므로 탈락!
    # loc_empty: 빈 칸 -> 3순위로 추천되어야 함!
    with engine.connect() as c:
        c.execute(
            text("UPDATE wms.storage_location SET capacity_qty=20 WHERE id=:id"),
            {"id": loc_same_lot["id"]},
        )
        c.execute(
            text("UPDATE wms.storage_location SET mix_lots=false WHERE id=:id"),
            {"id": loc_same_item["id"]},
        )
        c.commit()

    res = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    task = res["rows"][0]
    assert task["suggestedLocationId"] == loc_empty["id"]
    assert task["suggestedLocationCode"] == "R-B03"

    # 3. 품목 혼적 차단 방어 테스트:
    # loc_empty: 용량 10으로 설정 -> 적치 수량 30 > 10 이므로 탈락!
    # loc_mix: 다른 품목(RM-PIN) 재고 있음, mix_items=true -> 4순위 추천!
    with engine.connect() as c:
        c.execute(
            text("UPDATE wms.storage_location SET capacity_qty=10 WHERE id=:id"),
            {"id": loc_empty["id"]},
        )
        c.commit()

    res = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    task = res["rows"][0]
    assert task["suggestedLocationId"] == loc_mix["id"]
    assert task["suggestedLocationCode"] == "R-B04"

    # loc_mix: mix_items = false 로 설정 -> 다른 품목 혼적 불가로 탈락!
    # 모든 칸 탈락 -> "추천 없음"(None)
    with engine.connect() as c:
        c.execute(
            text("UPDATE wms.storage_location SET mix_items=false WHERE id=:id"),
            {"id": loc_mix["id"]},
        )
        c.commit()

    res = _ok(_call(client, auth, "GET", "/putaway-tasks"))
    task = res["rows"][0]
    assert task["suggestedLocationId"] is None
    assert task["suggestedLocationCode"] is None
    assert task["suggestedLocationName"] is None
