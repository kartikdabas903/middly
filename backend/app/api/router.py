from fastapi import APIRouter

from app.api.v1 import (
    admin,
    applications,
    audit_logs,
    auth,
    citizens,
    connectors,
    consents,
    data_quality,
    demo,
    events,
    grievances,
    notifications,
    services,
    workflows,
)

api_router = APIRouter(prefix="/api/v1")
for module in (auth, services, applications, grievances, consents, citizens, connectors, workflows, audit_logs, events,
               notifications, data_quality, admin, demo):
    api_router.include_router(module.router)
