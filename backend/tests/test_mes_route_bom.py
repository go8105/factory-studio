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
        {"steps": []},
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
        {"steps": [{"processId": ins}, {"processId": inj}, {"processId": ins}]},
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
        {"steps": [{"processId": 999999}]},
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
        {"steps": []},
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


def test_route_step_attributes_crud(mes):
    client, created = mes
    item = _id(client, "/items", "itemCode", "RM-PBT")
    created_route = _call(
        client,
        created,
        "POST",
        "/routes",
        "new-attr",
        {"itemId": item, "routeCode": "RT-ATTR"},
    )
    route_id = created_route.json()["data"]["id"]
    inj = _id(client, "/processes", "processCode", "INJ")
    ins = _id(client, "/processes", "processCode", "INS")

    # 1. 외주 아닌 단계(isSubcontract=False)에 subcontractorCode가 주어져도 비워짐
    # 2. 외주 단계(isSubcontract=True)에는 subcontractorCode 보존
    payload = {
        "steps": [
            {
                "processId": inj,
                "standardCycleSec": "45.50",
                "setupMinutes": 30,
                "isSubcontract": False,
                "subcontractorCode": "VENDOR-IGNORED",
            },
            {
                "processId": ins,
                "standardCycleSec": "12.00",
                "setupMinutes": 0,
                "isSubcontract": True,
                "subcontractorCode": "VENDOR-EXT",
            },
        ]
    }
    response = _call(
        client,
        created,
        "PUT",
        f"/routes/{route_id}/steps",
        "save-attr",
        payload,
    )
    assert response.status_code == 200
    steps = response.json()["data"]["steps"]
    assert len(steps) == 2

    assert steps[0]["sequenceNo"] == 1
    assert steps[0]["processId"] == inj
    assert steps[0]["standardCycleSec"] == "45.50"
    assert steps[0]["setupMinutes"] == 30
    assert steps[0]["isSubcontract"] is False
    assert steps[0]["subcontractorCode"] is None

    assert steps[1]["sequenceNo"] == 2
    assert steps[1]["processId"] == ins
    assert steps[1]["standardCycleSec"] == "12.00"
    assert steps[1]["setupMinutes"] == 0
    assert steps[1]["isSubcontract"] is True
    assert steps[1]["subcontractorCode"] == "VENDOR-EXT"

    # 목록 조회 시에도 자식에 속성들이 실리는지 확인
    found = _find(client, "/routes", "id", route_id)
    assert found["steps"][0]["standardCycleSec"] == "45.50"
    assert found["steps"][1]["subcontractorCode"] == "VENDOR-EXT"


def test_route_step_attributes_validation(mes):
    client, created = mes
    draft = _find(client, "/routes", "routeCode", "RT-H100")
    inj = _id(client, "/processes", "processCode", "INJ")

    # standardCycleSec <= 0 에러
    res_zero = _call(
        client,
        created,
        "PUT",
        f"/routes/{draft['id']}/steps",
        "zero-cycle",
        {"steps": [{"processId": inj, "standardCycleSec": "0"}]},
    )
    assert res_zero.status_code == 400
    assert "steps" in res_zero.json()["error"]["details"]["fields"]

    # setupMinutes < 0 에러
    res_neg_setup = _call(
        client,
        created,
        "PUT",
        f"/routes/{draft['id']}/steps",
        "neg-setup",
        {"steps": [{"processId": inj, "setupMinutes": -1}]},
    )
    assert res_neg_setup.status_code in (400, 422)


def test_revise_route_copies_step_attributes(mes):
    client, created = mes
    item = _id(client, "/items", "itemCode", "RM-PBT")
    created_route = _call(
        client,
        created,
        "POST",
        "/routes",
        "rev-attr",
        {"itemId": item, "routeCode": "RT-REV-ATTR"},
    )
    route_id = created_route.json()["data"]["id"]
    inj = _id(client, "/processes", "processCode", "INJ")
    _call(
        client,
        created,
        "PUT",
        f"/routes/{route_id}/steps",
        "save-steps",
        {
            "steps": [
                {
                    "processId": inj,
                    "standardCycleSec": "60.00",
                    "setupMinutes": 15,
                    "isSubcontract": True,
                    "subcontractorCode": "VENDOR-A",
                }
            ]
        },
    )
    # 게시
    _call(client, created, "POST", f"/routes/{route_id}/publish", "pub-attr")

    # 개정
    rev_res = _call(
        client, created, "POST", f"/routes/{route_id}/revise", "rev-attr-action"
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    assert rev_data["version"] == 2
    assert rev_data["status"] == "draft"
    assert len(rev_data["steps"]) == 1
    copied = rev_data["steps"][0]
    assert copied["processId"] == inj
    assert copied["standardCycleSec"] == "60.00"
    assert copied["setupMinutes"] == 15
    assert copied["isSubcontract"] is True
    assert copied["subcontractorCode"] == "VENDOR-A"


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


# ---- R-3 & R-4: 투입 공정, 키 기반 맞춤 저장, 대체 자재 ----
def test_bom_line_issue_process_id(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    inj = _id(client, "/processes", "processCode", "INJ")
    body = _lines(
        client,
        (
            "RM-PBT",
            {
                "qtyPerUnit": "0.010",
                "unit": "KG",
                "lossRate": "2",
                "issueProcessId": inj,
            },
        ),
        ("RM-PIN", {"qtyPerUnit": "1.000", "unit": "EA", "issueProcessId": None}),
    )
    res = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "issue-proc", body
    )
    assert res.status_code == 200
    lines = res.json()["data"]["lines"]
    assert lines[0]["issueProcessId"] == inj
    assert lines[1]["issueProcessId"] is None

    # 잘못된 공정 ID
    bad_body = _lines(
        client,
        (
            "RM-PBT",
            {"qtyPerUnit": "0.010", "unit": "KG", "issueProcessId": 999999},
        ),
    )
    bad_res = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "bad-proc", bad_body
    )
    assert bad_res.status_code == 400
    assert "유효하지 않은 공정" in bad_res.json()["error"]["details"]["fields"]["lines"]


def test_bom_lines_reconciliation_preserves_line_id(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    body1 = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG", "lossRate": "0"}),
        ("RM-PIN", {"qtyPerUnit": "2.000", "unit": "EA", "lossRate": "0"}),
    )
    res1 = _call(client, created, "PUT", f"/boms/{draft['id']}/lines", "recon-1", body1)
    assert res1.status_code == 200
    lines1 = res1.json()["data"]["lines"]
    line_map1 = {l["materialItemId"]: l["id"] for l in lines1}

    # 수량 변경 후 다시 저장
    body2 = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.015", "unit": "KG", "lossRate": "1"}),
        ("RM-PIN", {"qtyPerUnit": "3.000", "unit": "EA", "lossRate": "0"}),
    )
    res2 = _call(client, created, "PUT", f"/boms/{draft['id']}/lines", "recon-2", body2)
    assert res2.status_code == 200
    lines2 = res2.json()["data"]["lines"]
    line_map2 = {l["materialItemId"]: l["id"] for l in lines2}

    # material_item_id가 같은 라인은 id가 보존되어야 한다
    assert line_map1 == line_map2
    assert lines2[0]["qtyPerUnit"] == "0.015"


def test_bom_substitutes_crud_and_rules(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    pbt_id = _id(client, "/items", "itemCode", "RM-PBT")
    pin_id = _id(client, "/items", "itemCode", "RM-PIN")
    target_item_id = draft["itemId"]

    # 라인 설정
    body = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG"}),
    )
    res_line = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "sub-lines", body
    )
    assert res_line.status_code == 200
    line_id = res_line.json()["data"]["lines"][0]["id"]

    # 1. 목록 조회 (비어있음)
    list_res = client.get(f"{BASE}/boms/{draft['id']}/lines/{line_id}/substitutes")
    assert list_res.status_code == 200
    assert list_res.json()["data"] == []

    # 2. 유효성 검사 실패 케이스들
    # 2-1. 완제품 자신
    self_sub = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line_id}/substitutes",
        "sub-self",
        {
            "substitutes": [
                {"substituteItemId": target_item_id, "priority": 1, "ratio": "1"}
            ]
        },
    )
    assert self_sub.status_code == 400
    assert "자신" in self_sub.json()["error"]["details"]["fields"]["substitutes"]

    # 2-2. 원래 구성 자재와 동일
    same_sub = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line_id}/substitutes",
        "sub-same",
        {"substitutes": [{"substituteItemId": pbt_id, "priority": 1, "ratio": "1"}]},
    )
    assert same_sub.status_code == 400
    assert (
        "원래 구성 자재" in same_sub.json()["error"]["details"]["fields"]["substitutes"]
    )

    # 2-3. 중복된 대체 자재
    dup_sub = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line_id}/substitutes",
        "sub-dup",
        {
            "substitutes": [
                {"substituteItemId": pin_id, "priority": 1, "ratio": "1"},
                {"substituteItemId": pin_id, "priority": 2, "ratio": "1"},
            ]
        },
    )
    assert dup_sub.status_code == 400
    assert (
        "같은 대체 자재" in dup_sub.json()["error"]["details"]["fields"]["substitutes"]
    )

    # 2-4. 유효하지 않은 품목
    bad_item = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line_id}/substitutes",
        "sub-bad-item",
        {"substitutes": [{"substituteItemId": 999999, "priority": 1, "ratio": "1"}]},
    )
    assert bad_item.status_code == 400
    assert (
        "유효하지 않은 품목"
        in bad_item.json()["error"]["details"]["fields"]["substitutes"]
    )

    # 3. 정상 등록
    sub_payload = {
        "substitutes": [
            {"substituteItemId": pin_id, "priority": 1, "ratio": "1.000000"}
        ]
    }
    save_sub = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line_id}/substitutes",
        "sub-ok",
        sub_payload,
    )
    assert save_sub.status_code == 200
    saved = save_sub.json()["data"]
    assert len(saved) == 1
    assert saved[0]["substituteItemId"] == pin_id
    assert saved[0]["priority"] == 1
    assert saved[0]["ratio"] == "1.000000"

    # GET /boms 에서도 라인 아래에 substitutes가 함께 반환되어야 함
    bom_data = _find(client, "/boms", "id", draft["id"])
    line_with_sub = next(l for l in bom_data["lines"] if l["id"] == line_id)
    assert len(line_with_sub["substitutes"]) == 1
    assert line_with_sub["substitutes"][0]["substituteItemId"] == pin_id


def test_delete_bom_line_with_substitutes_fails_with_409(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    pin_id = _id(client, "/items", "itemCode", "RM-PIN")

    # 2개 라인 등록
    body = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG"}),
        ("RM-PIN", {"qtyPerUnit": "1.000", "unit": "EA"}),
    )
    res_line = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "lines-del-sub", body
    )
    line1 = res_line.json()["data"]["lines"][0]

    # line1에 대체 자재 등록
    _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line1['id']}/substitutes",
        "add-sub",
        {"substitutes": [{"substituteItemId": pin_id, "priority": 1, "ratio": "1"}]},
    )

    # line1을 빼고(삭제 시도) line2만 저장하려고 할 때 -> 409 REFERENCED_BY_OTHERS
    del_body = _lines(
        client,
        ("RM-PIN", {"qtyPerUnit": "1.000", "unit": "EA"}),
    )
    del_res = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines",
        "del-line-with-sub",
        del_body,
    )
    assert del_res.status_code == 409
    assert del_res.json()["error"]["code"] == "REFERENCED_BY_OTHERS"
    assert "대체 자재를 먼저 지우세요" in del_res.json()["error"]["message"]

    # 대체 자재를 먼저 삭제(빈 목록으로 교체)
    empty_sub = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{line1['id']}/substitutes",
        "rm-sub",
        {"substitutes": []},
    )
    assert empty_sub.status_code == 200

    # 이제 line1 삭제 가능
    ok_del_res = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "del-line-ok", del_body
    )
    assert ok_del_res.status_code == 200
    assert len(ok_del_res.json()["data"]["lines"]) == 1


def test_published_bom_substitutes_are_locked(mes):
    client, created = mes
    bom = _find(client, "/boms", "bomCode", "BOM-C100")
    line_id = bom["lines"][0]["id"]
    res = _call(
        client,
        created,
        "PUT",
        f"/boms/{bom['id']}/lines/{line_id}/substitutes",
        "locked-sub",
        {"substitutes": []},
    )
    assert res.status_code == 409
    assert _reason(res) == "VERSION_LOCKED"


def test_bom_revise_copies_substitutes(mes):
    client, created = mes
    pbt = _id(client, "/items", "itemCode", "RM-PBT")
    pin = _id(client, "/items", "itemCode", "RM-PIN")

    # 신규 품목 등록 (draft 중복 방지)
    item_res = _call(
        client,
        created,
        "POST",
        "/items",
        "new-item-for-sub",
        {
            "itemCode": "FG-REV-SUB",
            "name": "대체자재복제품목",
            "itemType": "finished",
            "baseUnit": "EA",
        },
    )
    assert item_res.status_code == 201
    item = item_res.json()["data"]["id"]

    # 신규 BOM 생성
    new_bom = _call(
        client,
        created,
        "POST",
        "/boms",
        "new-bom-for-sub",
        {"itemId": item, "bomCode": "BOM-COPY-SUB"},
    )
    assert new_bom.status_code == 201
    bom_id = new_bom.json()["data"]["id"]

    # 라인 추가
    _call(
        client,
        created,
        "PUT",
        f"/boms/{bom_id}/lines",
        "put-line-for-sub",
        {
            "lines": [
                {
                    "materialItemId": pbt,
                    "qtyPerUnit": "0.05",
                    "unit": "KG",
                    "lossRate": "1",
                }
            ]
        },
    )
    bom_info = _find(client, "/boms", "id", bom_id)
    line_id = bom_info["lines"][0]["id"]

    # 대체 자재 추가
    _call(
        client,
        created,
        "PUT",
        f"/boms/{bom_id}/lines/{line_id}/substitutes",
        "put-sub-for-sub",
        {
            "substitutes": [
                {"substituteItemId": pin, "priority": 1, "ratio": "2.500000"}
            ]
        },
    )

    # 게시
    _call(client, created, "POST", f"/boms/{bom_id}/publish", "pub-copy-sub")

    # 개정
    rev_res = _call(
        client,
        created,
        "POST",
        f"/boms/{bom_id}/revise",
        "rev-copy-sub",
        {"bomCode": "BOM-COPY-SUB-V2"},
    )
    assert rev_res.status_code == 201
    rev_data = rev_res.json()["data"]
    assert rev_data["versionNo"] == 2
    assert rev_data["status"] == "draft"
    assert len(rev_data["lines"]) == 1
    rev_line = rev_data["lines"][0]
    assert rev_line["materialItemId"] == pbt
    assert len(rev_line["substitutes"]) == 1
    assert rev_line["substitutes"][0]["substituteItemId"] == pin
    assert rev_line["substitutes"][0]["priority"] == 1
    assert rev_line["substitutes"][0]["ratio"] == "2.500000"
    assert rev_line["substitutes"][0]["bomLineId"] == rev_line["id"]
    assert rev_line["id"] != line_id


def test_bom_lines_reordering_preserves_line_ids_and_substitutes(mes):
    client, created = mes
    draft = _find(client, "/boms", "bomCode", "BOM-H100")
    pbt_id = _id(client, "/items", "itemCode", "RM-PBT")
    pin_id = _id(client, "/items", "itemCode", "RM-PIN")

    # 1. 자재 2개 등록: 1번 RM-PBT, 2번 RM-PIN
    body1 = _lines(
        client,
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG", "lossRate": "0"}),
        ("RM-PIN", {"qtyPerUnit": "2.000", "unit": "EA", "lossRate": "0"}),
    )
    res1 = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "reorder-init", body1
    )
    assert res1.status_code == 200
    lines1 = res1.json()["data"]["lines"]
    assert len(lines1) == 2
    assert lines1[0]["materialItemId"] == pbt_id and lines1[0]["lineNo"] == 1
    assert lines1[1]["materialItemId"] == pin_id and lines1[1]["lineNo"] == 2
    pbt_line_id = lines1[0]["id"]
    pin_line_id = lines1[1]["id"]

    # 2. 첫 번째 자재(RM-PBT)에 대체 자재 등록
    sub_res = _call(
        client,
        created,
        "PUT",
        f"/boms/{draft['id']}/lines/{pbt_line_id}/substitutes",
        "reorder-sub",
        {
            "substitutes": [
                {"substituteItemId": pin_id, "priority": 1, "ratio": "1.500000"}
            ]
        },
    )
    assert sub_res.status_code == 200

    # 3. 자재 2개의 순서를 바꿔 저장: 1번 RM-PIN, 2번 RM-PBT (BOM-FIX: UK 충돌 없이 200 성공해야 함)
    body2 = _lines(
        client,
        ("RM-PIN", {"qtyPerUnit": "2.000", "unit": "EA", "lossRate": "0"}),
        ("RM-PBT", {"qtyPerUnit": "0.010", "unit": "KG", "lossRate": "0"}),
    )
    res2 = _call(
        client, created, "PUT", f"/boms/{draft['id']}/lines", "reorder-swap", body2
    )
    assert res2.status_code == 200
    lines2 = res2.json()["data"]["lines"]
    assert len(lines2) == 2
    assert lines2[0]["materialItemId"] == pin_id and lines2[0]["lineNo"] == 1
    assert lines2[1]["materialItemId"] == pbt_id and lines2[1]["lineNo"] == 2

    # 4. 각 줄의 bom_line.id가 보존되었는지 검증
    assert lines2[0]["id"] == pin_line_id
    assert lines2[1]["id"] == pbt_line_id

    # 5. RM-PBT의 대체 자재가 그대로 살아있는지 검증
    pbt_subs = lines2[1]["substitutes"]
    assert len(pbt_subs) == 1
    assert pbt_subs[0]["substituteItemId"] == pin_id
    assert pbt_subs[0]["ratio"] == "1.500000"
