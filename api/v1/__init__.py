"""
API v1 Routes.

This package contains all v1 API endpoints.
"""

from fastapi import APIRouter

# Create v1 router
router = APIRouter()

# Import and include sub-routers
from api.v1 import auth_routes, data_routes, alert_routes

router.include_router(auth_routes.router, prefix="/auth", tags=["Authentication"])
router.include_router(data_routes.router, tags=["Data"])
router.include_router(alert_routes.router, tags=["Alerts"])

__all__ = ['router']
