"""CMMS-1c: 설비 대장(C-05)과 고장 코드(C-09).

FS-029 D46 · DSN-21 Q1·Q7 — 가져온 설비는 원천 코드 1건당 1행이고 원천은 바꾸지 않는다.
계층은 라인 > 설비 > 구성품이며 자기 자신·후손을 상위로 둘 수 없다.
고장 코드는 증상·원인·조치 3종이고 원인만 4M1E+측정 분류를 갖는다.
"""

from itertools import count

import pytest
from sqlalchemy import text

C = "/api/v1/cmms"
_keys = count()


def _call(client, created, method: str, path: str, body=None, key=None):
    return client.request(
        method,
        path if path.startswith("/api") else f"{C}{path}",
        json=body,
        headers={
            "X-CSRF-Token": created["csrfToken"],
            "Idempotency-Key": key or f"c{next(_keys)}",
        },
    )


def _ok(response, status=200):
    assert response.status_code == status, response.text
    return response.json()["data"]


def _reason(response) -> str:
    return response.json()["error"]["details"]["reason"]


def _module(client, created, key: str, enabled: bool) -> None:
    _ok(
        _call(
            client,
            created,
            "PATCH",
            f"/api/v1/core/workspace/modules/{key}",
            {"enabled": enabled},
        )
    )


@pytest.fixture
def cmms(guest_space):
    """빈 CMMS 대장. 시드가 없으므로 그대로 비어 있다."""
    client, created, engine = guest_space
    with engine.begin() as c:
        c.execute(
            text("DELETE FROM cmms.asset WHERE workspace_id=:w AND generation_id=:g"),
            {"w": created["workspaceId"], "g": created["generationId"]},
        )
    return client, created, engine


def _asset(client, created, code: str, **extra):
    body = {"code": code, "name": f"{code} 설비", "assetType": "INJECTION", **extra}
    return _call(client, created, "POST", "/assets", body)


# ---------- 설비 대장 (C-05) ----------


def test_direct_asset_has_no_source_code(cmms):
    """직접 등록한 설비는 출처 CMMS이고 원천 코드가 없다(DB CHECK와 같은 규칙)."""
    client, created, _ = cmms
    asset = _ok(_asset(client, created, "PRESS-01", criticality="A"), 201)
    assert asset["source"] == "CMMS" and asset["sourceCode"] is None
    assert asset["criticality"] == "A" and asset["isActive"] is True

    # 중복은 400이다 — 어느 칸이 문제인지 가리켜야 해서 공통 엔진이 VALIDATION_FAILED로 낸다.
    duplicate = _asset(client, created, "PRESS-01")
    assert duplicate.status_code == 400
    assert "code" in duplicate.json()["error"]["details"]["fields"]

    bad_code = _asset(client, created, "press-01")
    assert bad_code.status_code == 400


def test_asset_hierarchy_rejects_cycles(cmms):
    """Q7: 라인 > 설비 > 구성품. 자기 자신이나 후손을 상위로 두면 계층이 끊긴다."""
    client, created, _ = cmms
    line = _ok(_asset(client, created, "LINE-A", assetType="LINE"), 201)
    machine = _ok(_asset(client, created, "INJ-A1", parentAssetId=line["id"]), 201)
    part = _ok(
        _asset(
            client,
            created,
            "INJ-A1-H",
            assetType="COMPONENT",
            parentAssetId=machine["id"],
        ),
        201,
    )

    itself = _call(
        client, created, "PATCH", f"/assets/{line['id']}", {"parentAssetId": line["id"]}
    )
    assert itself.status_code == 400
    assert "parentAssetId" in itself.json()["error"]["details"]["fields"]

    descendant = _call(
        client, created, "PATCH", f"/assets/{line['id']}", {"parentAssetId": part["id"]}
    )
    assert descendant.status_code == 400

    missing = _call(
        client, created, "PATCH", f"/assets/{machine['id']}", {"parentAssetId": 999_999}
    )
    assert missing.status_code == 400

    # 상위를 비우면 최상위가 된다.
    detached = _ok(
        _call(
            client, created, "PATCH", f"/assets/{part['id']}", {"parentAssetId": None}
        )
    )
    assert detached["parentAssetId"] is None


def test_asset_tree_is_ordered_by_depth_then_code(cmms):
    """트리는 상위 → 하위 순으로 펴지고 같은 층은 코드순이다. 화면은 depth만큼 들여 쓴다."""
    client, created, _ = cmms
    line = _ok(_asset(client, created, "LINE-A", assetType="LINE"), 201)
    _ok(_asset(client, created, "INJ-A2", parentAssetId=line["id"]), 201)
    _ok(_asset(client, created, "INJ-A1", parentAssetId=line["id"]), 201)
    _ok(_asset(client, created, "ZZ-ALONE"), 201)

    tree = _ok(client.get(f"{C}/assets/tree"))
    assert [(t["code"], t["depth"]) for t in tree] == [
        ("LINE-A", 0),
        ("INJ-A1", 1),
        ("INJ-A2", 1),
        ("ZZ-ALONE", 0),
    ]


def test_asset_delete_is_blocked_by_children(cmms):
    client, created, _ = cmms
    line = _ok(_asset(client, created, "LINE-A", assetType="LINE"), 201)
    child = _ok(_asset(client, created, "INJ-A1", parentAssetId=line["id"]), 201)
    blocked = _call(client, created, "DELETE", f"/assets/{line['id']}")
    assert blocked.status_code == 409
    assert _reason(blocked) == "REFERENCED_BY_OTHERS"

    assert _call(client, created, "DELETE", f"/assets/{child['id']}").status_code == 204
    assert _call(client, created, "DELETE", f"/assets/{line['id']}").status_code == 204


# ---------- 가져오기 (C-05, D46 · Q1) ----------


def test_import_is_one_row_per_source_code(cmms):
    """원천 1건당 1행. 두 번 가져와도 늘지 않고, 가져온 것은 후보에서 빠진다."""
    client, created, _ = cmms
    candidates = _ok(
        client.get(f"{C}/assets/import-candidates", params={"source": "MES"})
    )
    assert candidates, "MES 시드에 설비가 있어야 한다"
    assert {"sourceCode", "name", "assetType", "location"} <= set(candidates[0])
    # MES 설비 종류(약칭 INJ·ASM·INS)를 CMMS 종류로 옮긴다. 모두 OTHER면 매핑이 끊긴 것이다.
    kinds = {c["assetType"] for c in candidates}
    assert kinds != {"OTHER"}, f"설비 종류 매핑이 끊겼다: {kinds}"
    assert {
        c["sourceCode"][:3]: c["assetType"]
        for c in candidates
        if c["sourceCode"][:3] in ("INJ", "ASM", "INS")
    } == {"INJ": "INJECTION", "ASM": "ASSEMBLY", "INS": "INSPECTION"}

    codes = [c["sourceCode"] for c in candidates[:2]]
    first = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets/import",
            {"source": "MES", "sourceCodes": codes},
        ),
        201,
    )
    assert first["created"] == 2 and first["skipped"] == []

    rest = _ok(client.get(f"{C}/assets/import-candidates", params={"source": "MES"}))
    assert not ({c["sourceCode"] for c in rest} & set(codes))

    again = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets/import",
            {"source": "MES", "sourceCodes": codes},
            key="import-again",
        ),
        201,
    )
    assert again["created"] == 0 and sorted(again["skipped"]) == sorted(codes)

    rows = _ok(client.get(f"{C}/assets", params={"source": "MES"}))
    assert {r["code"] for r in rows} == set(codes)
    assert all(r["sourceCode"] == r["code"] for r in rows)


def test_mold_import_sets_type_mold(cmms):
    """Q1: 금형은 출처 MES_MOLD, 종류 MOLD로 묶여 들어온다(DB CHECK가 둘을 함께 본다)."""
    client, created, _ = cmms
    molds = _ok(
        client.get(f"{C}/assets/import-candidates", params={"source": "MES_MOLD"})
    )
    if not molds:
        pytest.skip("시드에 금형이 없다")
    assert all(m["assetType"] == "MOLD" for m in molds)
    created_rows = _ok(
        _call(
            client,
            created,
            "POST",
            "/assets/import",
            {"source": "MES_MOLD", "sourceCodes": [molds[0]["sourceCode"]]},
        ),
        201,
    )
    assert created_rows["created"] == 1
    row = _ok(client.get(f"{C}/assets", params={"source": "MES_MOLD"}))[0]
    assert row["assetType"] == "MOLD" and row["source"] == "MES_MOLD"


def test_import_needs_the_source_module(cmms):
    """원천을 꺼 두면 가져오기만 막힌다 — 직접 등록은 그대로 된다(D12)."""
    client, created, _ = cmms
    _module(client, created, "mes", False)
    blocked = client.get(f"{C}/assets/import-candidates", params={"source": "MES"})
    assert blocked.status_code == 409
    assert _reason(blocked) == "SOURCE_MODULE_DISABLED"
    assert _ok(_asset(client, created, "PRESS-01"), 201)["code"] == "PRESS-01"

    _module(client, created, "bems", False)
    hvac = client.get(f"{C}/assets/import-candidates", params={"source": "BEMS"})
    assert hvac.status_code == 409


def test_hvac_import_comes_from_bems(cmms):
    client, created, _ = cmms
    units = _ok(client.get(f"{C}/assets/import-candidates", params={"source": "BEMS"}))
    assert units and all(u["assetType"] == "HVAC" for u in units)
    _ok(
        _call(
            client,
            created,
            "POST",
            "/assets/import",
            {"source": "BEMS", "sourceCodes": [units[0]["sourceCode"]]},
        ),
        201,
    )
    row = _ok(client.get(f"{C}/assets", params={"source": "BEMS"}))[0]
    assert row["assetType"] == "HVAC" and row["location"] == units[0]["location"]


# ---------- 고장 코드 (C-09, F24) ----------


def test_failure_code_kinds_and_cause_category(cmms):
    """원인 코드만 보전 원인 분류(마모·윤활·전기·설정·외부·기타)를 갖는다. 증상·조치에 주면 막는다."""
    client, created, _ = cmms
    symptom = _ok(
        _call(
            client,
            created,
            "POST",
            "/failure-codes",
            {"kind": "SYMPTOM", "code": "NOISE", "name": "이상 소음"},
        ),
        201,
    )
    assert symptom["causeCategory"] is None

    cause = _ok(
        _call(
            client,
            created,
            "POST",
            "/failure-codes",
            {
                "kind": "CAUSE",
                "code": "BEARING",
                "name": "베어링 마모",
                "causeCategory": "WEAR",
            },
        ),
        201,
    )
    assert cause["causeCategory"] == "WEAR"

    no_category = _call(
        client,
        created,
        "POST",
        "/failure-codes",
        {"kind": "CAUSE", "code": "LOOSE", "name": "체결 풀림"},
    )
    assert no_category.status_code == 400
    assert "causeCategory" in no_category.json()["error"]["details"]["fields"]

    stray = _call(
        client,
        created,
        "POST",
        "/failure-codes",
        {
            "kind": "ACTION",
            "code": "REPLACE",
            "name": "교체",
            "causeCategory": "WEAR",
        },
    )
    assert stray.status_code == 400

    # 같은 코드라도 구분이 다르면 쓸 수 있다.
    assert (
        _call(
            client,
            created,
            "POST",
            "/failure-codes",
            {"kind": "ACTION", "code": "NOISE", "name": "소음 조치"},
        ).status_code
        == 201
    )
    same = _call(
        client,
        created,
        "POST",
        "/failure-codes",
        {"kind": "SYMPTOM", "code": "NOISE", "name": "중복"},
    )
    assert same.status_code == 400

    only_cause = _ok(client.get(f"{C}/failure-codes", params={"kind": "CAUSE"}))
    assert [r["code"] for r in only_cause] == ["BEARING"]
