"""업무 기준일. 테스트가 실제 날짜에 흔들리지 않게 하는 FS_TODAY 규칙(FS-018j)."""

from datetime import date, datetime
from zoneinfo import ZoneInfo

import pytest
from fs.common.clock import business_today, guest_expires_at


def test_fs_today_overrides_business_date(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("FS_TODAY", "2026-09-24")
    assert business_today() == date(2026, 9, 24)


def test_without_override_business_date_is_kst_today(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.delenv("FS_TODAY", raising=False)
    assert business_today() == datetime.now(ZoneInfo("Asia/Seoul")).date()


def test_guest_expiry_follows_real_clock_not_fs_today(monkeypatch: pytest.MonkeyPatch):
    # 데이터 기준일을 과거로 고정해도 새 게스트가 만들자마자 만료되면 안 된다.
    monkeypatch.setenv("FS_TODAY", "2020-01-01")
    assert guest_expires_at() > datetime.now(ZoneInfo("Asia/Seoul"))
