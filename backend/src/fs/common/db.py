from __future__ import annotations

from functools import lru_cache

from sqlalchemy import Engine, create_engine

from fs.common.config import get_settings


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    return create_engine(get_settings().database_url, pool_pre_ping=True)


def reset_engine() -> None:
    if get_engine.cache_info().currsize:
        get_engine().dispose()
    get_engine.cache_clear()
