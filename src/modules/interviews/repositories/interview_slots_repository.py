from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete,update
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from collections import defaultdict

from src.modules.interviews.models import Interview_Slot

def utc_now():
    return datetime.now(timezone.utc)

class InterviewSlotsRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ─── Reads ────────────────────────────────────────────────────────────

    async def get_available_slots(self, round_config_id: UUID) -> list[Interview_Slot]:
        """All unbooked slots for a round config (PANEL mode — panelist_email is NULL)."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,
                Interview_Slot.slot_start > utc_now(),  # only show future slots as available
            )
            .order_by(Interview_Slot.slot_start)
        )
        return list(result.scalars().all())
    
    

    # async def get_slots_grouped_by_panelist(
    #     self, round_config_id: UUID
    # ) -> dict[str, list[Interview_Slot]]:
    #     """SEQUENTIAL mode: returns {panelist_email: [unbooked slots]} grouped."""
    #     result = await self.db.execute(
    #         select(Interview_Slot)
    #         .where(
    #             Interview_Slot.round_config_id == round_config_id,
    #             Interview_Slot.is_booked == False,
    #             Interview_Slot.panelist_id.isnot(None),
    #             Interview_Slot.slot_start > utc_now(),  # only show future slots as available
    #         )
    #         .order_by(Interview_Slot.panelist_id, Interview_Slot.slot_start)
    #     )
    #     grouped: dict[str, list[Interview_Slot]] = defaultdict(list)
    #     for slot in result.scalars().all():
    #         grouped[slot.panelist_id].append(slot)
    #     return dict(grouped)
    
    async def get_slots_grouped_by_panelist(
        self, round_config_id: UUID
    ) -> dict[UUID, list[Interview_Slot]]:

        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,
                Interview_Slot.panelist_id.isnot(None),
                Interview_Slot.slot_start > now,
            )
            .order_by(Interview_Slot.panelist_id, Interview_Slot.slot_start)
        )

        slots = result.scalars().all()

        grouped: dict[UUID, list[Interview_Slot]] = defaultdict(list)

        for slot in slots:
            grouped[slot.panelist_id].append(slot)

        return dict(grouped)


    async def get_slots_by_panelist_id(self, round_config_id: UUID, panelist_id: str)-> list[Interview_Slot]:
        """All unbooked and unexpired slots for a round config and panelist (SEQUENTIAL mode)."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.panelist_id == panelist_id,
                Interview_Slot.slot_start > utc_now(),  # only show future slots as available, past slots are not relevant for booking and can be ignored even if unbooked (stale availability)
            )
            .order_by(Interview_Slot.slot_start)
        )
        return list(result.scalars().all())
    
    
    async def get_slots_by_ids(self, slot_ids: list[UUID], panelist_id: UUID) -> list[Interview_Slot]:
        """Get slots by a list of ids, with an ownership guard to ensure panelists can only access their own slots for edits/deletes."""
        
        result = await self.db.execute(
            select(Interview_Slot).where(
                Interview_Slot.id.in_(slot_ids),
                Interview_Slot.panelist_id == panelist_id,  # ownership guard
            )
        )
        return list(result.scalars().all())
    
    async def get_editable_slots_by_panelist_id(self, round_config_id: UUID, panelist_id: str)-> list[Interview_Slot]:
        """All unbooked slots for a round config and panelist,  that can be deleted/edited."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,
                Interview_Slot.panelist_id == panelist_id,
                Interview_Slot.slot_start < utc_now(),  # include past slots for editing purposes, even if they can't be booked
            )
            .order_by(Interview_Slot.slot_start)
        )
        return list(result.scalars().all())
    
    
    async def get_booked_slots_by_panelist_id(self, round_config_id: UUID, panelist_id: str)-> list[Interview_Slot]:
        """All booked slots for a round config and panelist (used for checking if panelist has any booked slots before allowing edits)."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == True,
                Interview_Slot.panelist_id == panelist_id,
                Interview_Slot.slot_start > utc_now(),  # only consider future booked slots for edit restrictions 
            )
            .order_by(Interview_Slot.slot_start)
        )
        
        return list(result.scalars().all())
    
    
    
    async def get_slot_by_interview_id_with_round_config_id_with_panelist_id(self, interview_id: UUID,round_config_id,panelist_id) -> Interview_Slot:
        result = await self.db.execute(
            select(Interview_Slot).where(
                Interview_Slot.booked_interview_id == interview_id,
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.panelist_id == panelist_id,
                )
        )
        return result.scalar_one_or_none()

    
    
    async def get_slot_by_id(self, slot_id: UUID) -> Optional[Interview_Slot]:
        result = await self.db.execute(
            select(Interview_Slot).where(Interview_Slot.id == slot_id)
        )
        return result.scalar_one_or_none()

    async def count_remaining(self, round_config_id: UUID) -> int:
        """Count unbooked slots in the shared pool. Used to auto-reset slots_available."""
        result = await self.db.execute(
            select(func.count(Interview_Slot.id))
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,
            )
        )
        return result.scalar_one()

    async def all_panelists_booked_for_interview(
        self, interview_id: UUID, panelist_emails: list[str]
    ) -> bool:
        """SEQUENTIAL mode: check if every panelist has a slot booked for this interview."""
        result = await self.db.execute(
            select(func.count(func.distinct(Interview_Slot.panelist_email)))
            .where(
                Interview_Slot.booked_interview_id == interview_id,
                Interview_Slot.is_booked == True,
                Interview_Slot.panelist_email.in_(panelist_emails),
            )
        )
        booked_count = result.scalar_one()
        return booked_count >= len(panelist_emails)

    # ─── Writes ───────────────────────────────────────────────────────────

    async def bulk_insert_slots(self, slots: list[Interview_Slot]) -> list[Interview_Slot]:
        """Bulk insert computed slots into the pool."""
        self.db.add_all(slots)
        await self.db.flush()
        return slots

    async def book_slot_atomic(
        self, slot_id: UUID, interview_id: UUID
    ) -> Optional[Interview_Slot]:
        """
        Atomically claim a slot from the shared pool.
        Uses SELECT FOR UPDATE SKIP LOCKED to handle race conditions.
        Returns None if slot was already taken.
        """
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.id == slot_id,
                Interview_Slot.is_booked == False,
            )
            .with_for_update(skip_locked=True)
        )
        slot = result.scalar_one_or_none()
        if slot is None:
            return None  # Already taken by another candidate

        slot.is_booked = True
        slot.booked_interview_id = interview_id
        slot.booked_at = utc_now()
        await self.db.flush()
        return slot
    
    
    async def update_slot_time(self, slot_id: UUID, slot_start: datetime, slot_end: datetime) -> None:
        await self.db.execute(
            update(Interview_Slot)
            .where(
                Interview_Slot.id == slot_id,
                Interview_Slot.is_booked == False,  # safety guard
            )
            .values(slot_start=slot_start, slot_end=slot_end)
        )
        await self.db.flush()
        
    async def release_slot(self, slot_id: UUID) -> Optional[Interview_Slot]:
        """Release a booked slot back to the pool (used for reschedule / cancel)."""
        result = await self.db.execute(
            select(Interview_Slot).where(Interview_Slot.id == slot_id)
        )
        slot = result.scalar_one_or_none()
        if slot is None:
            return None

        slot.is_booked = False
        slot.booked_interview_id = None
        slot.booked_at = None
        
        if slot.slot_start < utc_now():
            slot.is_expired = True  # mark as expired if past start time, to prevent re-booking of stale slots
        
        await self.db.flush()
        return slot

    async def delete_pool(self, round_config_id: UUID) -> int:
        """Wipe entire slot pool for a round config (used on reschedule/reopen)."""
        result = await self.db.execute(
            delete(Interview_Slot)
            .where(Interview_Slot.round_config_id == round_config_id)
        )
        await self.db.flush()
        return result.rowcount


    # Useful for one-to-one interview-slot relationships, and for checking if an interview has a booked slot and its details.
    async def get_booked_slot_for_interview(self, interview_id: UUID) -> Interview_Slot:
        """Get a single slots booked by a specific interview."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.booked_interview_id == interview_id,
                Interview_Slot.is_booked == True,
            )
            .order_by(Interview_Slot.slot_start)
        )
        return result.scalar_one_or_none()
    
    
    # useful if multiple slots can be booked for an interview (e.g. SEQUENTIAL mode with multiple panelists), otherwise get_booked_slot_for_interview is sufficient to return the single booked slot.
    async def get_booked_slots_for_interview(self, interview_id: UUID) -> list[Interview_Slot]:
        """Get all slots booked by a specific interview."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.booked_interview_id == interview_id,
                Interview_Slot.is_booked == True,
            )
            .order_by(Interview_Slot.slot_start)
        )
        return list(result.scalars().all())
    
    
    async def get_booked_slot_by_interview_id(self, interview_id: UUID) -> Optional[Interview_Slot]:
        """Get the slot booked for a specific interview."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.booked_interview_id == interview_id,
                Interview_Slot.is_booked == True,
            )
            .order_by(Interview_Slot.slot_start)
        )
        return result.scalar_one_or_none()
    
    
    async def delete_unbooked_slots_by_panelist_id(self, round_config_id: UUID, panelist_id: str) -> int:
        """Delete unbooked slots for a specific panelist (used when a panelist edits availability in SEQUENTIAL mode)."""
        result = await self.db.execute(
            delete(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.panelist_id == panelist_id,
                Interview_Slot.is_booked == False,
                Interview_Slot.slot_start < utc_now(),  # also delete past slots to prevent stale availability
            )
        )
        await self.db.flush()
        return result.rowcount
    
    async def delete_slots_by_ids(self,panelist_id:str,round_config_id:str,slot_ids: list[UUID]) -> None:
        await self.db.execute(
            delete(Interview_Slot).where(
                Interview_Slot.id.in_(slot_ids),
                Interview_Slot.panelist_id == panelist_id,
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,  # safety guard
            )
        )
        
        await self.db.flush()
