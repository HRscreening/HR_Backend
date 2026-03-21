"""
Slot Computation Service
========================
PANEL mode  → triggered after ALL panelists submit; computes intersection of all schedules.
SEQUENTIAL  → triggered per-panelist on each submission; stores that panelist's slots immediately.

In both modes, once slots_available is set, waiting candidates get booking links.
"""

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from datetime import datetime, timedelta, timezone
from uuid import UUID
from configs.log_config import get_logger
from configs.env_config import FRONTEND_URL

from src.models.enums import PanelMode, InterviewStatus
from src.models.interview_models.interview_slots import Interview_Slot
from src.models.interview_models.interviews import Interview
from src.models.interview_models.panelist_model import Panelist
from src.repositories.interview_respositories.interview_slots_repository import InterviewSlotsRepository
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_repository import InterviewRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
from src.utils.jwt import jwt_service, JWTService
from src.services.email_services.candidate.candidate_email_service import CandidateEmailService, candidate_email_service


logger = get_logger("SlotComputationService")


# ─── Pure helpers ─────────────────────────────────────────────────────────────

def compute_intersection(
    slot_lists: list[list[tuple[datetime, datetime]]],
) -> list[tuple[datetime, datetime]]:
    """
    PANEL mode: find time ranges where ALL panelists are available.
    Each element in slot_lists is one panelist's list of (start, end) ranges.
    """
    if not slot_lists:
        return []

    result = slot_lists[0][:]
    for panelist_slots in slot_lists[1:]:
        new_result = []
        for s1, e1 in result:
            for s2, e2 in panelist_slots:
                overlap_start = max(s1, s2)
                overlap_end = min(e1, e2)
                if overlap_start < overlap_end:
                    new_result.append((overlap_start, overlap_end))
        result = new_result
        if not result:
            break
    return result


def split_into_slots(
    ranges: list[tuple[datetime, datetime]],
    duration_minutes: int,
) -> list[tuple[datetime, datetime]]:
    """Split continuous ranges into discrete N-minute interview slots."""
    slots = []
    delta = timedelta(minutes=duration_minutes)
    for start, end in ranges:
        current = start
        while current + delta <= end:
            slots.append((current, current + delta))
            current += delta
    return slots


def parse_panelist_slots(available_slots_json: list[dict]) -> list[tuple[datetime, datetime]]:
    """
    Parse the JSONB available_slots from a panelist into (start, end) datetime pairs.
    Expected format: [{"date": "2026-03-05", "time": [{"start_time": "...", "end_time": "..."}]}]
    """
    ranges = []
    if not available_slots_json:
        return ranges

    for day_entry in available_slots_json:
        for time_slot in day_entry.get("time", []):
            start_raw = time_slot.get("start_time")
            end_raw = time_slot.get("end_time")
            if start_raw and end_raw:
                start = _parse_datetime(start_raw)
                end = _parse_datetime(end_raw)
                if start and end and start < end:
                    ranges.append((start, end))
    return ranges


def _parse_datetime(val) -> datetime | None:
    """
    Parse a datetime string or pass through a datetime object.
    Rejects naive datetimes (no timezone info) — logs a warning and returns None.
    All returned datetimes are normalised to UTC.
    """
    if isinstance(val, datetime):
        if val.tzinfo is None:
            logger.warning(f"Rejecting naive datetime object: {val}")
            return None
        return val.astimezone(timezone.utc)
    if isinstance(val, str):
        # Only try formats that include timezone offset
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z"):
            try:
                dt = datetime.strptime(val, fmt)
                return dt.astimezone(timezone.utc)
            except ValueError:
                continue
        # If no tz-aware format matched, reject it
        logger.warning(f"Rejecting datetime string without timezone: {val}")
    return None


# ─── Service ──────────────────────────────────────────────────────────────────

class SlotComputationService:
    def __init__(
        self,
        slots_repo: InterviewSlotsRepository,
        round_config_repo: InterviewRoundConfigsRepository,
        interview_repo: InterviewRepository,
        event_repo: InterviewEventRepository,
        db: AsyncSession,
    ):
        self.slots_repo = slots_repo
        self.round_config_repo = round_config_repo
        self.interview_repo = interview_repo
        self.event_repo = event_repo
        self.db = db
        self.jwt_service: JWTService = jwt_service
        self.candidate_email_service: CandidateEmailService = candidate_email_service
        self.frontend_url = FRONTEND_URL

    # ─── PANEL mode entry point (called after ALL panelists submit) ─────

    async def compute_and_store_slots(
        self,
        round_config_id: UUID,
    ) -> bool:
        """
        PANEL mode entry point. Called after the LAST panelist submits.
        Computes intersection of all panelist schedules.
        Returns True if slots were successfully computed and stored.
        """
        round_config = await self.round_config_repo.get_interview_round_config_by_id(
            str(round_config_id)
        )
        if not round_config:
            logger.error(f"Round config {round_config_id} not found")
            return False

        # Load all panelist availability rows for this round config
        result = await self.db.execute(
            select(Panelist)
            .where(Panelist.round_config_id == round_config_id)
        )
        all_panelists = list(result.scalars().all())

        if not all_panelists:
            logger.error(f"No panelists found for round_config {round_config_id}")
            return False

        duration = round_config.duration_minutes
        return await self._compute_panel_mode(
            round_config, all_panelists, duration
        )

    # ─── SEQUENTIAL mode entry point (called per-panelist on each submit) ─

    async def compute_single_panelist_slots(
        self,
        round_config_id: UUID,
        panelist_id: str,
        panelist_email: str,
        available_slots_json: list[dict],
        notify_waiting_candidates: bool = True,
    ) -> bool:
        """
        SEQUENTIAL mode entry point. Called immediately when ONE panelist submits.
        Parses that panelist's availability, writes their slots to the pool,
        sets slots_available=True, and notifies waiting candidates.
        Returns True if slots were stored.
        """
        round_config = await self.round_config_repo.get_interview_round_config_by_id(
            str(round_config_id)
        )
        if not round_config:
            logger.error(f"Round config {round_config_id} not found")
            return False

        duration = round_config.duration_minutes
        parsed = parse_panelist_slots(available_slots_json)
        discrete_slots = split_into_slots(parsed, duration)

        if not discrete_slots:
            logger.warning(f"SEQUENTIAL: zero slots from {panelist_email} for round_config {round_config.id}")
            return False

        slot_models = [
            Interview_Slot(
                round_config_id=round_config.id,
                panelist_id = UUID(panelist_id),
                slot_start=start,
                slot_end=end,
            )
            for start, end in discrete_slots
        ]
        await self.slots_repo.bulk_insert_slots(slot_models)

        # Mark round as having available slots (idempotent — stays True once set)
        round_config.slots_available = True



        logger.info(
            f"SEQUENTIAL: {len(discrete_slots)} slots from {panelist_email} "
            f"written for round_config {round_config.id}"
        )

        # Notify waiting candidates so they can start booking
        # ! notify candidates in ready to book status that slots are available 
        if notify_waiting_candidates:  
            await self._send_booking_links_to_waiting_candidates(round_config)
            
        return True

    # ─── PANEL mode (intersection) ────────────────────────────────────────

    async def _compute_panel_mode(
        self,
        round_config,
        all_panelists: list[Panelist],
        duration_minutes: int,
        trigger_interview_id: UUID,
    ) -> bool:
        # Parse each panelist's available slots
        slot_lists = []
        for panelist in all_panelists:
            parsed = parse_panelist_slots(panelist.available_slots or [])
            slot_lists.append(parsed)

        if not slot_lists or any(len(s) == 0 for s in slot_lists):
            # At least one panelist has no slots
            # await self.event_repo.create_interview_event(
            #     interview_id=str(trigger_interview_id),
            #     event_type="SLOT_COMPUTATION_FAILED",
            #     actor="system",
            #     summary="Panelist with no available slots",
            #     details={"reason": "One or more panelists provided no available slots", "panel_mode": "panel"},
            # )
            logger.warning(f"Slot computation failed for round_config {round_config.id}: empty panelist slots")
            return False

        # Compute intersection
        intersected = compute_intersection(slot_lists)
        discrete_slots = split_into_slots(intersected, duration_minutes)

        if not discrete_slots:
            # await self.event_repo.create_interview_event(
            #     interview_id=str(trigger_interview_id),
            #     event_type="SLOT_COMPUTATION_FAILED",
            #     actor="system",
            #     summary="No common slots across panelists",
            #     details={"reason": "No common time slots found across all panelists", "panel_mode": "panel"},
            # )
            logger.warning(f"No intersecting slots for round_config {round_config.id}")
            return False

        # Write slots to shared pool
        slot_models = [
            Interview_Slot(
                round_config_id=round_config.id,
                panelist_email=None,  # PANEL mode: no per-panelist assignment
                slot_start=start,
                slot_end=end,
            )
            for start, end in discrete_slots
        ]
        await self.slots_repo.bulk_insert_slots(slot_models)

        # Set flag
        round_config.slots_available = True

        # # Timeline event
        # await self.event_repo.create_interview_event(
        #     interview_id=str(trigger_interview_id),
        #     event_type="SLOT_COMPUTATION_SUCCESS",
        #     actor="system",
        #     summary="Slots computed successfully",
        #     details={"slot_count": len(discrete_slots), "panel_mode": "panel"},
        # )

        logger.info(f"PANEL mode: {len(discrete_slots)} slots written for round_config {round_config.id}")

        # Notify all waiting candidates
        await self._send_booking_links_to_waiting_candidates(round_config)
        return True

    # ─── SEQUENTIAL mode (union / independent) ────────────────────────────

    async def _compute_sequential_mode(
        self,
        round_config,
        all_panelists: list[Panelist],
        duration_minutes: int,
        trigger_interview_id: UUID,
    ) -> bool:
        total_slots = 0
        failed_panelists = []

        for panelist in all_panelists:
            parsed = parse_panelist_slots(panelist.available_slots or [])
            discrete_slots = split_into_slots(parsed, duration_minutes)

            if not discrete_slots:
                failed_panelists.append(panelist.panelist_email)
                continue

            slot_models = [
                Interview_Slot(
                    round_config_id=round_config.id,
                    panelist_email=panelist.panelist_email,
                    slot_start=start,
                    slot_end=end,
                )
                for start, end in discrete_slots
            ]
            await self.slots_repo.bulk_insert_slots(slot_models)
            total_slots += len(discrete_slots)

        if total_slots == 0:
            # await self.event_repo.create_interview_event(
            #     interview_id=str(trigger_interview_id),
            #     event_type="SLOT_COMPUTATION_FAILED",
            #     actor="system",
            #     details={"reason": "No panelists had compute-able slots", "panel_mode": "sequential"},
            # )
            return False

        if failed_panelists:
            logger.warning(
                f"SEQUENTIAL: panelists with zero slots: {failed_panelists} for round_config {round_config.id}"
            )

        round_config.slots_available = True

        # await self.event_repo.create_interview_event(
        #     interview_id=str(trigger_interview_id),
        #     event_type="SLOT_COMPUTATION_SUCCESS",
        #     actor="system",
        #     details={
        #         "slot_count": total_slots,
        #         "panel_mode": "sequential",
        #         "failed_panelists": failed_panelists,
        #     },
        # )

        logger.info(f"SEQUENTIAL mode: {total_slots} slots written for round_config {round_config.id}")

        await self._send_booking_links_to_waiting_candidates(round_config)
        return True
    
    async def compute_slots_for_new_ranges(
        self,
        round_config_id: UUID,
        panelist_id: str,
        panelist_email: str,
        available_slots_json: list[dict],  # only the NEW/UPDATED ranges
    ) -> bool:
        """
        Used during editing — computes and inserts slots ONLY for the given ranges.
        Does NOT touch existing slots (caller is responsible for deleting old ones first).
        Does NOT notify candidates (slots already exist, round already active).
        Does NOT change slots_available flag.
        """
        round_config = await self.round_config_repo.get_interview_round_config_by_id(
            str(round_config_id)
        )
        if not round_config:
            logger.error(f"Round config {round_config_id} not found")
            return False

        parsed = parse_panelist_slots(available_slots_json)
        discrete_slots = split_into_slots(parsed, round_config.duration_minutes)

        if not discrete_slots:
            logger.warning(
                f"EDIT: zero slots computed from ranges for panelist {panelist_email}"
            )
            return False

        slot_models = [
            Interview_Slot(
                round_config_id=round_config.id,
                panelist_id=UUID(panelist_id),
                slot_start=start,
                slot_end=end,
            )
            for start, end in discrete_slots
        ]
        await self.slots_repo.bulk_insert_slots(slot_models)

        logger.info(
            f"EDIT: {len(discrete_slots)} new slots inserted for panelist "
            f"{panelist_email} on round_config {round_config.id}"
        )
        return True

    # ─── Notify waiting candidates ────────────────────────────────────────

    async def _send_booking_links_to_waiting_candidates(self, round_config):
        """
        Find all interviews with status=COLLECTING_AVAILABILITY for this round config
        and send them booking links.
        """
        result = await self.db.execute(
            select(Interview)
            .where(
                Interview.round_config_id == round_config.id,
                Interview.status == InterviewStatus.COLLECTING_AVAILABILITY,
            )
        )
        waiting_interviews = list(result.scalars().all())

        for interview in waiting_interviews:
            # Get candidate email from the application
            await self.db.refresh(interview, ["application"])
            application = interview.application
            if not application:
                continue

            await self.db.refresh(application, ["candidate"])
            candidate = application.candidate
            if not candidate:
                continue

            candidate_email = candidate.email

            # Calculate token expiry
            remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()
            token_expiry_min = max(60, int(remaining_seconds // 60))  # At least 1 hour

            # Generate booking token
            booking_token = self.jwt_service.create_candidate_booking_token(
                interview_id=str(interview.id),
                candidate_email=candidate_email,
                expiration_minutes=token_expiry_min,
            )
            interview.booking_token = booking_token
            interview.booking_token_expires_at = datetime.now(timezone.utc) + timedelta(minutes=token_expiry_min)
            interview.status = InterviewStatus.READY_TO_BOOK

            # Send booking email
            booking_link = f"{self.frontend_url}/interview/book?token={booking_token}"
            try:
                await self.candidate_email_service.send_booking_link_email(
                    candidate_email=candidate_email,
                    candidate_name=candidate.full_name or candidate_email,
                    interview_round_title=round_config.title,
                    booking_link=booking_link,
                )
            except Exception as e:
                logger.error(f"Failed to send booking email to {candidate_email}: {e}")

            # await self.event_repo.create_interview_event(
            #     interview_id=str(interview.id),
            #     event_type="SLOT_BOOKING_LINK_SENT",
            #     actor="system",
            #     details={"candidate_email": candidate_email},
            # )

        await self.db.flush()
