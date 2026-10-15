"""API v1 route exports for ExitLens."""

from app.api.v1.routes.analyses import router as analyses_router
from app.api.v1.routes.capsules import router as capsules_router
from app.api.v1.routes.dependencies import router as dependencies_router
from app.api.v1.routes.health import router as health_router
from app.api.v1.routes.recommendations import router as recommendations_router
from app.api.v1.routes.verification import router as verification_router

__all__ = [
    "analyses_router",
    "capsules_router",
    "dependencies_router",
    "health_router",
    "recommendations_router",
    "verification_router",
]
