"""W2b-1g 라벨 출력(W-17) 업무 규칙 (DSN-13 F07·F13)."""

from test_wms import W, _call, _ok, _reason
from test_wms_picks import _create_lot
from test_wms_reservations import receiving_env

__all__ = ["receiving_env"]


def _print(env, **body):
    return _call(env[0], env[1], "POST", "/labels", body)


def test_location_label_reprint_voids_the_previous_one(receiving_env):
    env = receiving_env
    first = _ok(_print(env, labelKind="LOCATION", barcodeValue="R-A01", copies=2), 201)
    assert first["status"] == "VALID"
    assert first["copies"] == 2
    assert first["reprintOfId"] is None

    # 대상당 유효 라벨은 1건이다. 사유 없이 다시 찍으려 하면 막는다.
    again = _print(env, labelKind="LOCATION", barcodeValue="R-A01")
    assert again.status_code == 409 and _reason(again) == "LABEL_EXISTS"

    second = _ok(
        _print(
            env,
            labelKind="LOCATION",
            barcodeValue="R-A01",
            reprintReason="라벨 훼손",
        ),
        201,
    )
    assert second["reprintOfId"] == first["id"]
    assert second["reprintReason"] == "라벨 훼손"

    rows = _ok(env[0].get(W + "/labels"))["rows"]
    by_id = {r["id"]: r for r in rows}
    assert by_id[first["id"]]["status"] == "VOID"  # 이전 라벨은 무효가 된다
    assert by_id[second["id"]]["status"] == "VALID"


def test_label_rejects_unknown_target_and_stray_reason(receiving_env):
    env = receiving_env
    bad_loc = _print(env, labelKind="LOCATION", barcodeValue="NO-SUCH")
    assert bad_loc.status_code == 400

    bad_lot = _print(env, labelKind="MATERIAL_LOT", barcodeValue="NO-SUCH-LOT")
    assert bad_lot.status_code == 400

    stray = _print(
        env, labelKind="LOCATION", barcodeValue="R-A01", reprintReason="처음인데 사유"
    )
    assert stray.status_code == 400


def test_material_lot_label_uses_registered_lot(receiving_env):
    env = receiving_env
    _create_lot(env, "LOT-LABEL-1")
    made = _ok(_print(env, labelKind="MATERIAL_LOT", barcodeValue="LOT-LABEL-1"), 201)
    assert made["labelKind"] == "MATERIAL_LOT"
    assert made["status"] == "VALID"

    only_lots = _ok(env[0].get(W + "/labels", params={"labelKind": "MATERIAL_LOT"}))
    assert [r["barcodeValue"] for r in only_lots["rows"]] == ["LOT-LABEL-1"]
