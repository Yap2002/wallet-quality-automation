from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(prefix="/health", tags=["health"])


class LivenessResponse(BaseModel):
    status: Literal["ok"]


@router.get("/live", response_model=LivenessResponse)
def liveness() -> LivenessResponse:
    """Report whether the API process is running."""
    return LivenessResponse(status="ok")
