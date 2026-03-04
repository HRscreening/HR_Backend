from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload
from datetime import datetime, timezone
from typing import Optional, List
from uuid import UUID
from collections import defaultdict

from src.models.interview_models.interview_slots import Interview_Slot


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
            )
            .order_by(Interview_Slot.slot_start)
        )
        return list(result.scalars().all())

    async def get_slots_grouped_by_panelist(
        self, round_config_id: UUID
    ) -> dict[str, list[Interview_Slot]]:
        """SEQUENTIAL mode: returns {panelist_email: [unbooked slots]} grouped."""
        result = await self.db.execute(
            select(Interview_Slot)
            .where(
                Interview_Slot.round_config_id == round_config_id,
                Interview_Slot.is_booked == False,
                Interview_Slot.panelist_email.isnot(None),
            )
            .order_by(Interview_Slot.panelist_email, Interview_Slot.slot_start)
        )
        grouped: dict[str, list[Interview_Slot]] = defaultdict(list)
        for slot in result.scalars().all():
            grouped[slot.panelist_email].append(slot)
        return dict(grouped)

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
        slot.booked_at = datetime.now(timezone.utc)
        await self.db.flush()
        return slot

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
