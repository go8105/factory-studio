from __future__ import annotations

from dataclasses import dataclass

from fs.common.errors import ApiError


@dataclass(frozen=True)
class Page:
    offset: int = 0
    limit: int = 50

    def checked(self) -> Page:
        if self.offset < 0 or not 1 <= self.limit <= 200:
            raise ApiError(400, "VALIDATION_FAILED", "페이지 범위가 올바르지 않습니다.")
        return self
