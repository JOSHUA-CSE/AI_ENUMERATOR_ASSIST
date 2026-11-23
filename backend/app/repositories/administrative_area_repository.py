from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.administrative_area import AdministrativeArea, AreaType
from app.models.house import House


class AdministrativeAreaRepository:
    def get_by_id(self, db: Session, area_id: UUID) -> AdministrativeArea | None:
        return (
            db.query(AdministrativeArea)
            .filter(AdministrativeArea.id == area_id)
            .first()
        )

    def get_by_code(self, db: Session, code: str) -> AdministrativeArea | None:
        return (
            db.query(AdministrativeArea).filter(AdministrativeArea.code == code).first()
        )

    def get_multi(
        self,
        db: Session,
        skip: int = 0,
        limit: int = 100,
        area_type: AreaType | None = None,
        parent_id: UUID | None = None,
    ) -> tuple[list[AdministrativeArea], int]:
        query = db.query(AdministrativeArea)

        if area_type:
            query = query.filter(AdministrativeArea.type == area_type)
        if parent_id:
            query = query.filter(AdministrativeArea.parent_id == parent_id)

        total = query.count()
        items = query.order_by(AdministrativeArea.name).offset(skip).limit(limit).all()
        return items, total

    def get_house_count(self, db: Session, area_id: UUID) -> int:
        return (
            db.query(func.count(House.id)).filter(House.area_id == area_id).scalar()
            or 0
        )

    def create(
        self,
        db: Session,
        area_obj: AdministrativeArea,
    ) -> AdministrativeArea:
        db.add(area_obj)
        db.commit()
        db.refresh(area_obj)
        return area_obj

    def delete(self, db: Session, area_id: UUID) -> bool:
        area = self.get_by_id(db, area_id)
        if area:
            db.delete(area)
            db.commit()
            return True
        return False


administrative_area_repository = AdministrativeAreaRepository()
