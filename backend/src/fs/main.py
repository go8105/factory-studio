"""앱 조립 자리. 업무 API와 인증은 후속 작업에서 등록한다."""

from fastapi import FastAPI

app = FastAPI(title="Factory Studio", docs_url=None, redoc_url=None, openapi_url=None)
