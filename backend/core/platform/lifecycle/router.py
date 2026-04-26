from __future__ import annotations

from fastapi import APIRouter, Depends

from core.di import service_dependency
from core.platform.lifecycle.dto import (
    HealthResponse,
    LifecycleStatusResponse,
    LivenessResponse,
    ReadinessResponse,
)
from core.platform.lifecycle.services import LifecycleService
from core.platform.service_keys import PLATFORM_LIFECYCLE_SERVICE

get_lifecycle_service = service_dependency(PLATFORM_LIFECYCLE_SERVICE)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
def get_health(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.health()


@router.get("/health/live", response_model=LivenessResponse)
def get_liveness(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.liveness()


@router.get("/health/ready", response_model=ReadinessResponse)
def get_readiness(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.readiness()


@router.get("/platform/lifecycle", response_model=LifecycleStatusResponse)
def get_lifecycle_status(
    svc: LifecycleService = Depends(get_lifecycle_service),
):
    return svc.runtime_status()
