from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.appointments import router as appointments_router
from app.api.v1.auth import router as auth_router
from app.api.v1.customers import router as customers_router
from app.api.v1.dispatch import router as dispatch_router
from app.api.v1.integrations import router as integrations_router
from app.api.v1.ml import router as ml_router
from app.api.v1.technicians import router as technicians_router
from app.api.v1.webhooks import router as webhooks_router
from app.api.v1.work_orders import router as work_orders_router

api_v1_router = APIRouter()

api_v1_router.include_router(auth_router)
api_v1_router.include_router(customers_router)
api_v1_router.include_router(technicians_router)
api_v1_router.include_router(work_orders_router)
api_v1_router.include_router(appointments_router)
api_v1_router.include_router(dispatch_router)
api_v1_router.include_router(integrations_router)
api_v1_router.include_router(webhooks_router)
api_v1_router.include_router(agent_router)
api_v1_router.include_router(ml_router)
