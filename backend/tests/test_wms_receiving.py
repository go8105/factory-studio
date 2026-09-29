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
    from fs.wms import service as scope

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
        with TestClient(env[0].app) as client:
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
        with TestClient(env[0].app) as client:
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
