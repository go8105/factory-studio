from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class LoginRequest(ApiModel):
    login_id: str = Field(alias="loginId", min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class GuestCreate(ApiModel):
    # 길이는 서비스가 앞뒤 공백을 지운 뒤 검사한다(FS-027 D33). 여기서는 상한만 둔다.
    nickname: str | None = Field(None, max_length=100)


class ModuleUpdate(ApiModel):
    enabled: bool
