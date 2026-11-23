from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_any_role, require_role
from app.models.administrative_area import AreaType
from app.models.user import User, UserRole
from app.schemas.administrative_area import (
    AdministrativeAreaBoundaryResponse,
    AdministrativeAreaCreate,
    AdministrativeAreaListResponse,
    AdministrativeAreaResponse,
)
from app.schemas.house import (
    BuildingEstimationResponse,
    HouseCreate,
    HouseListResponse,
    HouseResponse,
)
from app.services.administrative_area_service import administrative_area_service

router = APIRouter()


@router.get("", response_model=AdministrativeAreaListResponse)
def list_administrative_areas(
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=100, ge=1, le=1000, description="Limit for pagination"),
    type: AreaType | None = Query(default=None, description="Filter by area type"),
    parent_id: UUID | None = Query(
        default=None, description="Filter by parent area ID"
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    List administrative areas with pagination and optional filtering by type or parent.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return administrative_area_service.list_areas(
        db=db, skip=skip, limit=limit, area_type=type, parent_id=parent_id
    )


@router.get("/{id}", response_model=AdministrativeAreaResponse)
def get_administrative_area(
    id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve details and house count for a specific administrative area.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return administrative_area_service.get_area_by_id(db=db, area_id=id)


@router.get("/{id}/boundary", response_model=AdministrativeAreaBoundaryResponse)
def get_administrative_area_boundary(
    id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve standard GeoJSON polygon boundary for an administrative area.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return administrative_area_service.get_area_boundary(db=db, area_id=id)


@router.get("/{id}/estimation", response_model=BuildingEstimationResponse)
def get_building_estimation(
    id: UUID,
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve building estimation summary, density clusters, and data source label.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return administrative_area_service.get_building_estimation(db=db, area_id=id)


@router.post("/{id}/detect-buildings", response_model=BuildingEstimationResponse)
def detect_buildings(
    id: UUID,
    imagery_source: str = Query(
        default="Google Open Buildings V3",
        description="Satellite imagery provider identifier",
    ),
    confidence_threshold: float | None = Query(
        default=None, ge=0.0, le=1.0, description="Optional minimum confidence score"
    ),
    allow_development_fallback: bool = Query(
        default=False,
        description="Allow development test fallback if satellite is unavailable",
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Execute satellite building detection pipeline for an administrative area.
    Restricted strictly to Deputy Tahsildar.
    """
    return administrative_area_service.detect_buildings(
        db=db,
        area_id=id,
        imagery_source=imagery_source,
        confidence_threshold=confidence_threshold,
        allow_development_fallback=allow_development_fallback,
    )


@router.get("/{id}/houses", response_model=HouseListResponse)
def get_houses_in_administrative_area(
    id: UUID,
    skip: int = Query(default=0, ge=0, description="Offset for pagination"),
    limit: int = Query(default=1000, ge=1, le=5000, description="Limit for pagination"),
    source_type: str | None = Query(
        default=None, description="Filter by data source type"
    ),
    db: Session = Depends(get_db),
    _current_user: User = Depends(
        require_any_role([UserRole.DEPUTY_TAHSILDAR, UserRole.SUPERVISOR])
    ),
):
    """
    Retrieve houses and buildings belonging to a specific administrative area.
    Accessible by Deputy Tahsildar and Supervisor.
    """
    return administrative_area_service.list_houses_in_area(
        db=db, area_id=id, skip=skip, limit=limit, source_type=source_type
    )


@router.post(
    "",
    response_model=AdministrativeAreaResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_administrative_area(
    area_in: AdministrativeAreaCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Create a new administrative area with validated PostGIS boundary.
    Restricted strictly to Deputy Tahsildar.
    """
    return administrative_area_service.create_area(db=db, area_in=area_in)


@router.post(
    "/{id}/houses",
    response_model=HouseResponse,
    status_code=status.HTTP_201_CREATED,
)
def add_house_to_administrative_area(
    id: UUID,
    house_in: HouseCreate,
    db: Session = Depends(get_db),
    _current_user: User = Depends(require_role(UserRole.DEPUTY_TAHSILDAR)),
):
    """
    Add a new house/building point to an administrative area with validated coordinates.
    Restricted strictly to Deputy Tahsildar.
    """
    return administrative_area_service.add_house(db=db, area_id=id, house_in=house_in)
