"""
API 路由
"""

from fastapi import APIRouter

from backend.api import endpoints
from backend.api import endpoints_intent

router = APIRouter()

# 包含所有端点
router.include_router(endpoints.router)
router.include_router(endpoints_intent.router)

