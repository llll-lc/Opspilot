"""OpsPilot FastAPI 应用组合根。"""

from fastapi import FastAPI

from opspilot.api.router import api_router
from opspilot.config.settings import get_settings
from opspilot.db.session import create_database_engine, create_session_factory
from opspilot.security.auth import HmacBearerAuthenticator


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
    if settings.database_url is not None:
        engine = create_database_engine(settings.database_url.get_secret_value())
        app.state.session_factory = create_session_factory(engine)
    if settings.auth_token_secret is not None:
        app.state.authenticator = HmacBearerAuthenticator(
            settings.auth_token_secret.get_secret_value(),
            issuer=settings.auth_token_issuer,
            audience=settings.auth_token_audience,
        )
    app.include_router(api_router, prefix=settings.api_v1_prefix)
    return app


app = create_app()
