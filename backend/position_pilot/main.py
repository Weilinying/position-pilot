"""FastAPI 应用入口。"""

from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    """应用存活检查的稳定响应。"""

    status: str


app = FastAPI(title="PositionPilot")


@app.get("/health", response_model=HealthResponse)
def get_health() -> HealthResponse:
    """返回应用进程的存活状态，不检查外部依赖。"""

    return HealthResponse(status="ok")
