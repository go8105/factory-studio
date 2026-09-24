from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class ApiModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class LoginRequest(ApiModel):
    login_id: str = Field(alias="loginId", min_length=1, max_length=100)
    password: str = Field(min_length=1, max_length=200)


class ModuleUpdate(ApiModel):
    enabled: bool
