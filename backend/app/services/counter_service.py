from datetime import UTC, datetime
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models.hlb import HouselistingBlock
from app.models.hlb_counter import HlbCounter


class HlbCounterService:
    """
    Synchronized HLB numbering sequence allocation service.
    Enforces collision-free building and census house numbering within HLB scopes.
    Uses pessimistic locking (with_for_update) to protect concurrent allocations.
    """

    def get_or_create_counter(self, db: Session, hlb_id: UUID) -> HlbCounter:
        counter = db.query(HlbCounter).filter(HlbCounter.hlb_id == hlb_id).first()
        if not counter:
            # Verify HLB exists
            hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
            if not hlb:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Houselisting Block '{hlb_id}' not found.",
                )
            counter = HlbCounter(
                hlb_id=hlb_id,
                next_building_no=1,
                next_census_house_no=1,
                version=1,
                updated_at=datetime.now(UTC),
            )
            db.add(counter)
            db.commit()
            db.refresh(counter)
        return counter

    def allocate_numbers(
        self,
        db: Session,
        hlb_id: UUID,
        building_count: int = 0,
        census_house_count: int = 0,
    ) -> dict:
        """
        Atomically allocates a contiguous block of unique numbers for an HLB.
        Supports offline batch reservation and device recovery.
        """
        if building_count < 0 or census_house_count < 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Allocation counts cannot be negative.",
            )

        # Ensure HLB exists
        hlb = db.query(HouselistingBlock).filter(HouselistingBlock.id == hlb_id).first()
        if not hlb:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Houselisting Block '{hlb_id}' not found.",
            )

        # Use with_for_update if dialect supports row locks, fallback safely
        query = db.query(HlbCounter).filter(HlbCounter.hlb_id == hlb_id)
        if db.bind and db.bind.dialect.name != "sqlite":
            query = query.with_for_update()

        counter = query.first()
        if not counter:
            counter = HlbCounter(
                hlb_id=hlb_id,
                next_building_no=1,
                next_census_house_no=1,
                version=1,
                updated_at=datetime.now(UTC),
            )
            db.add(counter)
            db.flush()

        allocated_buildings: list[int] = []
        if building_count > 0:
            start_b = counter.next_building_no
            allocated_buildings = list(range(start_b, start_b + building_count))
            counter.next_building_no += building_count

        allocated_census_houses: list[int] = []
        if census_house_count > 0:
            start_ch = counter.next_census_house_no
            allocated_census_houses = list(range(start_ch, start_ch + census_house_count))
            counter.next_census_house_no += census_house_count

        counter.version += 1
        counter.updated_at = datetime.now(UTC)
        db.commit()
        db.refresh(counter)

        return {
            "hlb_id": hlb_id,
            "allocated_building_numbers": allocated_buildings,
            "allocated_census_house_numbers": allocated_census_houses,
            "next_building_no": counter.next_building_no,
            "next_census_house_no": counter.next_census_house_no,
            "version": counter.version,
            "updated_at": counter.updated_at,
        }


counter_service = HlbCounterService()

