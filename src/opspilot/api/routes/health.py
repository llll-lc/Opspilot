"""不包含业务含义的进程元数据端点。"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel, ConfigDict

from opspilot.config.settings import get_settings

router = APIRouter()


class ProcessHealth(BaseModel):
    """API 进程可达；此结果不代表任何依赖服务健康。"""

    model_config = ConfigDict(frozen=True)

    status: Literal["ok"]
    application: str
    version: str


@router.get("/healthz", response_model=ProcessHealth, include_in_schema=False)
def read_process_health() -> ProcessHealth:
    """仅报告当前进程标识，不探测依赖服务。"""
    settings = get_settings()
    return ProcessHealth(
        status="ok",
        application=settings.application_name,
        version=settings.application_version,
    )
