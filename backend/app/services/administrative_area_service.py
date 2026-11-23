from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.gis.spatial import (
    InvalidGeometryError,
    geometry_to_geojson_dict,
    validate_and_convert_geojson_polygon,
    validate_and_convert_point,
)
from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.house import House
from app.repositories.administrative_area_repository import (
    administrative_area_repository,
)
from app.repositories.house_repository import house_repository
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


class AdministrativeAreaService:
    def list_areas(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        area_type: AreaType | None = None,
        parent_id: UUID | None = None,
    ) -> AdministrativeAreaListResponse:
        items, total = administrative_area_repository.get_multi(
            db, skip=skip, limit=limit, area_type=area_type, parent_id=parent_id
        )

        responses: list[AdministrativeAreaResponse] = []
        for area in items:
            house_count = administrative_area_repository.get_house_count(db, area.id)
            boundary_geojson = geometry_to_geojson_dict(area.boundary)
            responses.append(
                AdministrativeAreaResponse(
                    id=area.id,
                    name=area.name,
                    type=area.type,
                    code=area.code,
                    parent_id=area.parent_id,
                    status=area.status,
                    house_count=house_count,
                    boundary=boundary_geojson,
                    created_at=area.created_at,
                    updated_at=area.updated_at,
                )
            )

        return AdministrativeAreaListResponse(
            items=responses, total=total, skip=skip, limit=limit
        )

    def get_area_by_id(self, db: Session, area_id: UUID) -> AdministrativeAreaResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        house_count = administrative_area_repository.get_house_count(db, area.id)
        boundary_geojson = geometry_to_geojson_dict(area.boundary)

        return AdministrativeAreaResponse(
            id=area.id,
            name=area.name,
            type=area.type,
            code=area.code,
            parent_id=area.parent_id,
            status=area.status,
            house_count=house_count,
            boundary=boundary_geojson,
            created_at=area.created_at,
            updated_at=area.updated_at,
        )

    def get_area_boundary(
        self, db: Session, area_id: UUID
    ) -> AdministrativeAreaBoundaryResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        boundary_geojson = geometry_to_geojson_dict(area.boundary)
        if not boundary_geojson:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to serialize boundary geometry",
            )

        return AdministrativeAreaBoundaryResponse(
            id=area.id,
            name=area.name,
            code=area.code,
            type=area.type,
            boundary=boundary_geojson,
        )

    def create_area(
        self, db: Session, area_in: AdministrativeAreaCreate
    ) -> AdministrativeAreaResponse:
        existing = administrative_area_repository.get_by_code(db, area_in.code)
        if existing:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Administrative area with code '{area_in.code}' already exists",
            )

        # Validate and convert geometry
        try:
            geom_wkb = validate_and_convert_geojson_polygon(area_in.boundary)
        except InvalidGeometryError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid geographic boundary: {e}",
            ) from e

        area_obj = AdministrativeArea(
            name=area_in.name,
            type=area_in.type,
            code=area_in.code,
            parent_id=area_in.parent_id,
            boundary=geom_wkb,
            status="ACTIVE",
        )

        saved = administrative_area_repository.create(db, area_obj)
        boundary_geojson = geometry_to_geojson_dict(saved.boundary)

        return AdministrativeAreaResponse(
            id=saved.id,
            name=saved.name,
            type=saved.type,
            code=saved.code,
            parent_id=saved.parent_id,
            status=saved.status,
            house_count=0,
            boundary=boundary_geojson,
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )

    def list_houses_in_area(
        self,
        db: Session,
        area_id: UUID,
        skip: int = 0,
        limit: int = 1000,
        source_type: str | None = None,
    ) -> HouseListResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        items, total = house_repository.get_by_area_id(
            db, area_id=area_id, skip=skip, limit=limit, source_type=source_type
        )

        house_responses = [
            HouseResponse(
                id=h.id,
                area_id=h.area_id,
                building_reference=h.building_reference,
                house_number=h.house_number,
                latitude=h.latitude,
                longitude=h.longitude,
                source_type=h.source_type,
                detection_confidence=h.detection_confidence,
                detected_at=h.detected_at,
                imagery_source=h.imagery_source,
                imagery_date=h.imagery_date,
                footprint=geometry_to_geojson_dict(h.footprint),
                created_at=h.created_at,
                updated_at=h.updated_at,
            )
            for h in items
        ]

        return HouseListResponse(
            items=house_responses, total=total, skip=skip, limit=limit
        )

    def get_building_estimation(
        self, db: Session, area_id: UUID
    ) -> BuildingEstimationResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        from app.gis.building_detection import building_detection_service

        summary = building_detection_service.get_building_estimation_summary(db, area)
        return BuildingEstimationResponse(**summary)

    def detect_buildings(
        self,
        db: Session,
        area_id: UUID,
        imagery_source: str = "Google Open Buildings V3",
        confidence_threshold: float | None = None,
        allow_development_fallback: bool = False,
    ) -> BuildingEstimationResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        from app.gis.building_detection import building_detection_service

        try:
            building_detection_service.run_building_detection(
                db=db,
                area=area,
                imagery_source=imagery_source,
                confidence_threshold=confidence_threshold,
                allow_development_fallback=allow_development_fallback,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(e),
            ) from e

        summary = building_detection_service.get_building_estimation_summary(db, area)
        return BuildingEstimationResponse(**summary)

    def add_house(
        self, db: Session, area_id: UUID, house_in: HouseCreate
    ) -> HouseResponse:
        area = administrative_area_repository.get_by_id(db, area_id)
        if not area:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Administrative area with ID {area_id} not found",
            )

        try:
            point_wkb = validate_and_convert_point(
                latitude=house_in.latitude, longitude=house_in.longitude
            )
        except InvalidGeometryError as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid coordinates: {e}",
            ) from e

        house_obj = House(
            area_id=area_id,
            building_reference=house_in.building_reference,
            house_number=house_in.house_number,
            latitude=house_in.latitude,
            longitude=house_in.longitude,
            location=point_wkb,
            source_type=house_in.source_type,
            detection_confidence=house_in.detection_confidence,
            imagery_source=house_in.imagery_source,
            imagery_date=house_in.imagery_date,
        )

        saved = house_repository.create(db, house_obj)
        return HouseResponse(
            id=saved.id,
            area_id=saved.area_id,
            building_reference=saved.building_reference,
            house_number=saved.house_number,
            latitude=saved.latitude,
            longitude=saved.longitude,
            source_type=saved.source_type,
            detection_confidence=saved.detection_confidence,
            detected_at=saved.detected_at,
            imagery_source=saved.imagery_source,
            imagery_date=saved.imagery_date,
            footprint=geometry_to_geojson_dict(saved.footprint),
            created_at=saved.created_at,
            updated_at=saved.updated_at,
        )


administrative_area_service = AdministrativeAreaService()
