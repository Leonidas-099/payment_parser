from fastapi import APIRouter

from app.api.v1.ops import router as ops_router
from app.api.v1.payments import router as payments_router

router = APIRouter()
router.include_router(payments_router)
router.include_router(ops_router)
