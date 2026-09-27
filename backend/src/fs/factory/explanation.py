"""Read-only, finite demo explanations. No client text, business rows or secrets sent."""

from __future__ import annotations

import json
import os
import time
from importlib.resources import files
from threading import Lock
from urllib.error import URLError
from urllib.request import Request, urlopen

from pydantic import BaseModel, ConfigDict, Field

SCENARIOS = json.loads(files("fs.factory").joinpath("scenarios.json").read_text())
MODEL = "gpt-6-astra"
PROMPT_VERSION = "vision-v1"


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    summary: str = Field(min_length=1, max_length=500)
    hypotheses: list[str] = Field(min_length=1, max_length=3)
    checks: list[str] = Field(min_length=1, max_length=3)


def evidence(scenario: str) -> list[str]:
    data = SCENARIOS[scenario]
    previous, current = data["previous"], data["current"]
    before = previous["rejected"] / previous["inspected"] * 100
    after = current["rejected"] / current["inspected"] * 100
    return [
        f"직전 10분: 검사 {previous['inspected']}개 / 불합격 {previous['rejected']}개 / 불합격률 {before:g}%",
        f"최근 10분: 검사 {current['inspected']}개 / 불합격 {current['rejected']}개 / 불합격률 {after:g}%",
        f"불합격률 변화: {after - before:+g}%p",
        data["event"],
    ]


def demo_result(scenario: str, reason: str) -> dict:
    data = SCENARIOS[scenario]
    return {
        "scenario": scenario,
        "mode": "demo",
        "reason": reason,
        "model": None,
        "evidence": evidence(scenario),
        "narrative": {key: data[key] for key in ("summary", "hypotheses", "checks")},
    }


def generate(scenario: str, key: str) -> dict:
    schema = Narrative.model_json_schema()
    body = {
        "model": MODEL,
        "store": False,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 1800,
        "instructions": (
            "제조 포트폴리오의 합성 비전검사 시나리오를 한국어로 짧게 설명한다. "
            "입력은 고정된 직전/최근 10분 비교 자료이며 현재 애니메이션 누계가 아니다. "
            "summary에는 확인된 상태, hypotheses에는 근거로 확정할 수 없는 가능성, "
            "checks에는 추가로 확인할 자료를 쓴다. 원인을 단정하지 않는다. "
            "제공되지 않은 수치·검사 이미지·실제 센서·MES 접근을 주장하지 않는다. "
            "수치 계산은 이미 제공된 evidence를 따른다. 설비 조작이나 자동 재가동을 지시하지 않는다."
        ),
        "input": json.dumps(
            {
                "scenario": scenario,
                "label": SCENARIOS[scenario]["label"],
                "evidence": evidence(scenario),
            },
            ensure_ascii=False,
        ),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "vision_explanation",
                "strict": True,
                "schema": schema,
            }
        },
    }
    request = Request(
        "https://api.openai.com/v1/responses",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=25) as response:
        raw = json.loads(response.read(131073))
    if not isinstance(raw, dict) or raw.get("status") != "completed":
        raise ValueError("Incomplete response")
    output = "".join(
        part.get("text", "")
        for item in raw.get("output", [])
        if isinstance(item, dict) and item.get("type") == "message"
        for part in item.get("content", [])
        if isinstance(part, dict) and part.get("type") == "output_text"
    )
    narrative = Narrative.model_validate_json(output)
    if any(len(text) > 500 for text in narrative.hypotheses + narrative.checks):
        raise ValueError("Response too long")
    return {
        "scenario": scenario,
        "mode": "ai",
        "reason": None,
        "model": MODEL,
        "evidence": evidence(scenario),
        "narrative": narrative.model_dump(),
    }


# All inputs are the same public synthetic fixtures. Successful responses are shared
# for this worker's lifetime: at most three paid successes per worker/start/version.
# One request at a time and a failure cooldown avoid repeated guest clicks billing.
_cache: dict[tuple[str, str, str], dict] = {}
_lock = Lock()
_retry_at = 0.0


def explain(scenario: str) -> dict:
    global _retry_at
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        return demo_result(scenario, "not_configured")
    cache_key = (MODEL, PROMPT_VERSION, scenario)
    if cache_key in _cache:
        return _cache[cache_key]
    if time.monotonic() < _retry_at or not _lock.acquire(blocking=False):
        return demo_result(scenario, "busy")
    try:
        if cache_key in _cache:
            return _cache[cache_key]
        value = generate(scenario, key)
        _cache[cache_key] = value
        return value
    except URLError, TimeoutError, ValueError, KeyError, TypeError, OSError:
        _retry_at = time.monotonic() + 60
        return demo_result(scenario, "unavailable")
    finally:
        _lock.release()
