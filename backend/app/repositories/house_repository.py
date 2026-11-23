from uuid import UUID

from sqlalchemy.orm import Session

from app.models.house import House


class HouseRepository:
    def get_by_id(self, db: Session, house_id: UUID) -> House | None:
        return db.query(House).filter(House.id == house_id).first()

    def get_by_area_id(
        self,
        db: Session,
        area_id: UUID,
        skip: int = 0,
        limit: int = 1000,
        source_type: str | None = None,
    ) -> tuple[list[House], int]:
        query = db.query(House).filter(House.area_id == area_id)
        if source_type:
            query = query.filter(House.source_type == source_type)
        total = query.count()
        items = (
            query.order_by(
                House.house_number, House.building_reference, House.created_at
            )
            .offset(skip)
            .limit(limit)
            .all()
        )
        return items, total

    def count_by_area(self, db: Session, area_id: UUID) -> int:
        return db.query(House).filter(House.area_id == area_id).count()

    def create(self, db: Session, house_obj: House) -> House:
        db.add(house_obj)
        db.commit()
        db.refresh(house_obj)
        return house_obj

    def delete(self, db: Session, house_id: UUID) -> bool:
        house = self.get_by_id(db, house_id)
        if house:
            db.delete(house)
            db.commit()
            return True
        return False


house_repository = HouseRepository()
