"""FS-020b MES 공정 경로(M-14)·BOM(M-15) 버전 API. 검증 항목마다 테스트를 나눈다."""

import pytest

BASE = "/api/v1/mes"


@pytest.fixture
def mes(guest_space):
    return guest_space[:2]


def _headers(created, key: str) -> dict[str, str]:
    return {"X-CSRF-Token": created["csrfToken"], "Idempotency-Key": key}


def _rows(client, path: str) -> list[dict]:
    return client.get(f"{BASE}{path}").json()["data"]


def _find(client, path: str, field: str, value) -> dict:
    return next(r for r in _rows(client, path) if r[field] == value)


def _id(client, path: str, field: str, code: str) -> int:
    return _find(client, path, field, code)["id"]


def _call(client, created, method: str, path: str, key: str, body=None):
    return client.request(
        method, f"{BASE}{path}", json=body, headers=_headers(created, key)
    )


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


# ---- M-14 공정 경로 ----
def test_seed_routes_with_steps(mes):
    client, _ = mes
    routes = {r["routeCode"]: r for r in _rows(client, "/routes")}
    assert routes["RT-C100"]["status"] == "published"
    assert routes["RT-H100"]["status"] == "draft"
    processes = {p["id"]: p["processCode"] for p in _rows(client, "/processes")}
    steps = routes["RT-C100"]["steps"]
    assert [(s["sequenceNo"], processes[s["processId"]]) for s in steps] == [
        (1, "INJ"),
        (2, "ASM"),
        (3, "INS"),
    ]


def test_published_route_steps_are_locked(mes):
    client, created = mes
    route = _find(client, "/routes", "routeCode", "RT-C100")
    response = _call(
        client,
        created,
        "PUT",
        f"/routes/{route['id']}/steps",
        "lock",
        {"processIds": []},
    )
    assert response.status_code == 409
    assert _reason(response) == "VERSION_LOCKED"


def test_draft_steps_follow_request_order(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    ins = _id(client, "/processes", "processCode", "INS")
    inj = _id(client, "/processes", "processCode", "INJ")
    response = _call(
        client,
        created,
        "PUT",
        f"/routes/{draft['id']}/steps",
        "order",
        {"processIds": [ins, inj, ins]},
    )
    assert response.status_code == 200
    steps = response.json()["data"]["steps"]
    assert [(s["sequenceNo"], s["processId"]) for s in steps] == [
        (1, ins),
        (2, inj),
        (3, ins),
    ]


def test_unknown_process_is_rejected(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    response = _call(
        client,
        created,
        "PUT",
        f"/routes/{draft['id']}/steps",
        "bad",
        {"processIds": [999999]},
    )
    assert response.status_code == 400
    assert "steps" in response.json()["error"]["details"]["fields"]


def test_revise_copies_steps_to_next_version(mes):
    client, created = mes
    route = _find(client, "/routes", "routeCode", "RT-C100")
    response = _call(client, created, "POST", f"/routes/{route['id']}/revise", "rev")
    assert response.status_code == 201
    draft = response.json()["data"]
    assert (draft["routeCode"], draft["version"], draft["status"]) == (
        "RT-C100",
        2,
        "draft",
    )
    assert [s["processId"] for s in draft["steps"]] == [
        s["processId"] for s in route["steps"]
    ]
    assert _find(client, "/routes", "id", route["id"])["status"] == "published"


def test_second_draft_is_rejected(mes):
    client, created = mes
    route = _find(client, "/routes", "routeCode", "RT-C100")
    _call(client, created, "POST", f"/routes/{route['id']}/revise", "rev1")
    response = _call(client, created, "POST", f"/routes/{route['id']}/revise", "rev2")
    assert response.status_code == 409
    assert _reason(response) == "DRAFT_EXISTS"


def test_draft_cannot_be_revised(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    response = _call(client, created, "POST", f"/routes/{draft['id']}/revise", "rev-d")
    assert response.status_code == 409
    assert _reason(response) == "IS_DRAFT"


def test_publish_then_retire(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    published = _call(client, created, "POST", f"/routes/{draft['id']}/publish", "pub")
    assert published.status_code == 200
    assert published.json()["data"]["publishedAt"] is not None
    again = _call(client, created, "POST", f"/routes/{draft['id']}/publish", "pub2")
    assert _reason(again) == "INVALID_TRANSITION"
    retired = _call(client, created, "POST", f"/routes/{draft['id']}/retire", "ret")
    assert retired.json()["data"]["status"] == "retired"
    assert retired.json()["data"]["retiredAt"] is not None


def test_empty_route_cannot_be_published(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    _call(
        client,
        created,
        "PUT",
        f"/routes/{draft['id']}/steps",
        "empty",
        {"processIds": []},
    )
    response = _call(client, created, "POST", f"/routes/{draft['id']}/publish", "pub-e")
    assert response.status_code == 409
    assert _reason(response) == "EMPTY_VERSION"


def test_new_route_starts_at_version_one(mes):
    client, created = mes
    item = _id(client, "/items", "itemCode", "RM-PBT")
    response = _call(
        client,
        created,
        "POST",
        "/routes",
        "new",
        {"itemId": item, "routeCode": "RT-NEW"},
    )
    assert response.status_code == 201
    data = response.json()["data"]
    assert (data["version"], data["status"], data["steps"]) == (1, "draft", [])


def test_existing_route_code_is_rejected(mes):
    client, created = mes
    item = _id(client, "/items", "itemCode", "RM-PBT")
    response = _call(
        client,
        created,
        "POST",
        "/routes",
        "dup",
        {"itemId": item, "routeCode": "RT-C100"},
    )
    assert response.status_code == 400
    assert "routeCode" in response.json()["error"]["details"]["fields"]


def test_only_draft_route_can_be_deleted(mes):
    client, created = mes
    published = _find(client, "/routes", "routeCode", "RT-C100")
    locked = _call(client, created, "DELETE", f"/routes/{published['id']}", "del-p")
    assert _reason(locked) == "VERSION_LOCKED"
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    ok = _call(client, created, "DELETE", f"/routes/{draft['id']}", "del-d")
    assert ok.status_code == 204
    assert all(r["routeCode"] != "RT-H100" for r in _rows(client, "/routes"))


# ---- M-15 BOM ----
def test_seed_boms_with_lines(mes):
    client, _ = mes
    bom = _find(client, "/boms", "bomCode", "BOM-C100")
    items = {i["id"]: i["itemCode"] for i in _rows(client, "/items")}
    assert bom["status"] == "published"
    assert [
        (
            items[line["materialItemId"]],
            line["qtyPerUnit"],
            line["unit"],
            line["lossRate"],
        )
        for line in bom["lines"]
    ] == [("RM-PBT", "0.012", "KG", "2.00"), ("RM-PIN", "4.000", "EA", "0.50")]


def test_bom_revise_needs_new_code(mes):
    client, created = mes
    bom = _find(client, "/boms", "bomCode", "BOM-C100")
    same = _call(
        client,
        created,
        "POST",
        f"/boms/{bom['id']}/revise",
        "same",
        {"bomCode": "BOM-C100"},
    )
    assert same.status_code == 400
    ok = _call(
        client,
        created,
        "POST",
        f"/boms/{bom['id']}/revise",
        "v2",
        {"bomCode": "BOM-C100-V2"},
    )
    assert ok.status_code == 201
    data = ok.json()["data"]
    assert (data["versionNo"], data["status"], len(data["lines"])) == (2, "draft", 2)


def _lines(client, *rows):
    return {
        "lines": [
            {"materialItemId": _id(client, "/items", "itemCode", code), **extra}
            for code, extra in rows
        ]
    }


def test_bom_lines_accept_conversion_unit(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    body = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG", "lossRate": "2"}),
        ("RM-PIN", {"qtyPerUnit": "0.001", "unit": "BOX"}),
    )
    response = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "lines", body
    )
    assert response.status_code == 200
    lines = response.json()["data"]["lines"]
    assert [(line["lineNo"], line["unit"]) for line in lines] == [(1, "KG"), (2, "BOX")]


@pytest.mark.parametrize(
    ("rows", "message"),
    [
        ((("SF-H100", {"qtyPerUnit": "1", "unit": "EA"}),), "자재가 될 수 없습니다"),
        (
            (
                ("RM-PBT", {"qtyPerUnit": "1", "unit": "KG"}),
                ("RM-PBT", {"qtyPerUnit": "2", "unit": "KG"}),
            ),
            "같은 자재",
        ),
        ((("RM-PBT", {"qtyPerUnit": "1", "unit": "EA"}),), "단위는"),
        ((("RM-PBT", {"qtyPerUnit": "0", "unit": "KG"}),), "소요량"),
        ((("RM-PBT", {"qtyPerUnit": "1", "unit": "KG", "lossRate": "100"}),), "손실률"),
    ],
    ids=["self", "duplicate", "unit", "zero-qty", "loss-100"],
)
def test_bom_line_rules(mes, rows, message):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    response = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines",
        "rule",
        _lines(client, *rows),
    )
    assert response.status_code == 400
    assert message in response.json()["error"]["details"]["fields"]["lines"]


def test_published_bom_lines_are_locked(mes):
    client, created = mes
    bom = _find(client, "/boms", "bomCode", "BOM-C100")
    response = _call(
        client, created, "PUT", f"/boms/{bom['id']}/lines", "lock", {"lines": []}
    )
    assert _reason(response) == "VERSION_LOCKED"


def test_bom_in_use_cannot_be_deleted_even_if_retired(mes):
    client, created = mes
    bom = _find(client, "/boms", "bomCode", "BOM-C100")
    _call(client, created, "POST", f"/boms/{bom['id']}/retire", "ret")
    response = _call(client, created, "DELETE", f"/boms/{bom['id']}", "del")
    assert _reason(response) == "VERSION_LOCKED"


def test_version_actions_are_idempotent(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    first = _call(client, created, "POST", f"/boms/{draft['id']}/publish", "same")
    second = _call(client, created, "POST", f"/boms/{draft['id']}/publish", "same")
    assert first.json() == second.json()


def test_version_action_requires_csrf(mes):
    client, _ = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    response = client.post(
        f"{BASE}/boms/{draft['id']}/publish", headers={"Idempotency-Key": "k"}
    )
    assert response.status_code == 403
