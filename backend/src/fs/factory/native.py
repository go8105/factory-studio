"""Bounded, shell-free native inspection adapter. No database writes."""

import asyncio
import os
from pathlib import Path
from threading import BoundedSemaphore
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from fs.common.errors import ApiError

Integer = Annotated[int, Field(strict=True, ge=0, le=16000)]
_slots = BoundedSemaphore(4)
TIMEOUT = 2.0
LIMIT = 1024 * 1024


class Closed(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Recipe(Closed):
    threshold: Annotated[int, Field(strict=True, ge=0, le=255)]
    minArea: Annotated[int, Field(strict=True, ge=1, le=16000)]
    roi: Literal["full", "center"]


class Inspection(Closed):
    version: Annotated[int, Field(strict=True, ge=1, le=1)]
    sample: Literal["normal", "foreign", "lighting"]
    recipe: Recipe


class NativeRequest(Closed):
    requestId: Annotated[
        str, Field(min_length=1, max_length=100, pattern=r"^[a-zA-Z0-9:_-]+$")
    ]
    request: Inspection


class Region(Closed):
    x: Annotated[int, Field(strict=True, ge=0, lt=160)]
    y: Annotated[int, Field(strict=True, ge=0, lt=100)]
    width: Annotated[int, Field(strict=True, ge=1, le=160)]
    height: Annotated[int, Field(strict=True, ge=1, le=100)]
    area: Annotated[int, Field(strict=True, ge=1, le=16000)]

    @model_validator(mode="after")
    def bounds(self):
        if (
            self.x + self.width > 160
            or self.y + self.height > 100
            or self.area > self.width * self.height
        ):
            raise ValueError("Region bounds")
        return self


class Result(Closed):
    version: Annotated[int, Field(strict=True, ge=1, le=1)]
    source: Literal["synthetic-opencv-cpp-v1"]
    status: Literal["OK", "NG"]
    regions: Annotated[list[Region], Field(max_length=16000)]
    falsePixels: Integer
    missedPixels: Integer
    excludedPixels: Integer

    @model_validator(mode="after")
    def consistent(self):
        if (self.status == "NG") != bool(self.regions) or sum(
            r.area for r in self.regions
        ) > 16000:
            raise ValueError("Inconsistent result")
        return self


class TimedResult(Closed):
    result: Result
    inspectionMs: Annotated[
        float, Field(strict=True, ge=0, le=2000, allow_inf_nan=False)
    ]


async def _read(stream):
    chunks = bytearray()
    while data := await stream.read(16384):
        chunks.extend(data)
        if len(chunks) > LIMIT:
            raise ValueError("Native output exceeded limit")
    return bytes(chunks)


async def inspect_native(body: NativeRequest) -> dict:
    executable = os.environ.get("VISION_CORE_EXECUTABLE", "")
    if (
        not executable
        or not Path(executable).is_absolute()
        or not os.access(executable, os.X_OK)
        or not Path(executable).is_file()
    ):
        raise ApiError(
            503,
            "NATIVE_UNAVAILABLE",
            "C++ 검사 엔진이 설정되지 않았습니다. 운영자에게 확인하세요.",
        )
    if not _slots.acquire(blocking=False):
        raise ApiError(
            429, "NATIVE_BUSY", "검사 요청이 많습니다. 잠시 후 다시 시도하세요."
        )
    process = None
    try:
        async with asyncio.timeout(TIMEOUT):
            process = await asyncio.create_subprocess_exec(
                executable,
                "--timed",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            process.stdin.write(body.request.model_dump_json().encode())
            await process.stdin.drain()
            process.stdin.close()
            stdout, _stderr = await asyncio.gather(
                _read(process.stdout), _read(process.stderr)
            )
            code = await process.wait()
            if code != 0:
                raise ValueError("Native exit failure")
            output = TimedResult.model_validate_json(stdout)
            return {"requestId": body.requestId, **output.model_dump()}
    except TimeoutError as exc:
        raise ApiError(
            504, "NATIVE_TIMEOUT", "C++ 검사 응답 제한 시간을 초과했습니다."
        ) from exc
    except (ValueError, OSError) as exc:
        raise ApiError(
            502,
            "NATIVE_FAILED",
            "C++ 검사 결과를 확인하지 못했습니다. 다시 검사하세요.",
        ) from exc
    finally:
        if process is not None and process.returncode is None:
            try:
                process.kill()
            except ProcessLookupError:
                pass
            await process.wait()
        _slots.release()
