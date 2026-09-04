"""OpsPilot FastAPI 应用组合根。"""

from fastapi import FastAPI

from opspilot.api.router import api_router
from opspilot.config.settings import get_settings


def create_app() -> FastAPI:
    """创建 API，但不连接目标系统或数据存储。"""
    settings = get_settings()
    app = FastAPI(
        title=settings.application_name,
        version=settings.application_version,
        docs_url="/docs" if settings.docs_enabled else None,
        redoc_url=None,
        openapi_url="/openapi.json" if settings.docs_enabled else None,
    )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
