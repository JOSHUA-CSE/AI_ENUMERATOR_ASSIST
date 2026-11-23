from fastapi import APIRouter

from app.api.endpoints import (
    areas,
    auth,
    counters,
    deputy,
    enumerators,
    gps,
    hlbs,
    layouts,
    route,
    supervisors,
    sync,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(areas.router, prefix="/areas", tags=["Administrative Areas"])
api_router.include_router(layouts.router, prefix="/layouts", tags=["Layouts & HLBs"])
api_router.include_router(hlbs.router, prefix="/hlbs", tags=["Houselisting Blocks"])
api_router.include_router(
    supervisors.router, prefix="/supervisors", tags=["Supervisors"]
)
api_router.include_router(
    supervisors.supervisor_router,
    prefix="/supervisor",
    tags=["Supervisor Dashboard"],
)
api_router.include_router(
    deputy.deputy_router,
    prefix="/deputy",
    tags=["Deputy Tahsildar Dashboard"],
)
api_router.include_router(
    enumerators.router, prefix="/enumerators", tags=["Enumerators"]
)
api_router.include_router(
    enumerators.enumerator_router,
    prefix="/enumerator",
    tags=["Enumerator Dashboard"],
)
api_router.include_router(
    route.router,
    prefix="/enumerator",
    tags=["Route Optimization"],
)
api_router.include_router(
    route.router,
    prefix="/routes",
    tags=["Routes"],
)
api_router.include_router(
    route.router,
    tags=["Route Optimization Direct"],
)
api_router.include_router(
    gps.router,
    prefix="/enumerator",
    tags=["GPS & Boundary Monitoring"],
)
api_router.include_router(
    gps.router,
    tags=["GPS & Boundary Monitoring Direct"],
)
api_router.include_router(
    sync.router,
    prefix="/sync",
    tags=["Synchronization"],
)
api_router.include_router(
    counters.router,
    prefix="/counters",
    tags=["Sequence Allocation Counters"],
)
