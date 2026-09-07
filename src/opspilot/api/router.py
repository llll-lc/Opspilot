"""注册由 OpsPilot 自主管理的 API 路由。"""

from fastapi import APIRouter

from opspilot.api.routes.cases import router as cases_router
from opspilot.api.routes.health import router as health_router

api_router = APIRouter()
api_router.include_router(health_router, tags=["system"])
api_router.include_router(cases_router, tags=["cases"])
