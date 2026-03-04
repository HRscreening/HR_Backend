from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from configs.env_config import FRONTEND_URL
from src.services.errors.base import DomainError
from src.repositories.interview_respositories.interview_round_configs_repository import InterviewRoundConfigsRepository
from src.repositories.interview_respositories.interview_event_repository import InterviewEventRepository
from src.repositories.interview_respositories.panelist_repository import PanelistRepository
from src.repositories.interview_respositories.interview_repository import InterviewRepository
from src.repositories.interview_respositories.interview_slots_repository import InterviewSlotsRepository
from src.services.email_services.candidate.candidate_email_service import CandidateEmailService, candidate_email_service
from src.services.email_services.panel.panel_email_service import PanelEmailService, panel_email_service
from src.utils.jwt import jwt_service, JWTService
from src.models.enums import InterviewStatus, PanelMode
from src.utils.timeline_formatter import TimelineFormatter, timeline_formatter
from datetime import datetime, timezone, timedelta
from src.services.interview_services.calendar_service import CalendarService
from src.dtos.interviews_dtos.interviews_dto import MeetingDetails, Reminders






class InterviewService:
    def __init__(
        self,
        interview_round_config_repository: InterviewRoundConfigsRepository,
        interview_event_repository: InterviewEventRepository,
        interview_repository: InterviewRepository,
        panelist_repository: PanelistRepository,
        slots_repository: InterviewSlotsRepository,
        calendar_service: CalendarService,
        db: AsyncSession,
    ):
        self.db = db
        self.interview_event_repository = interview_event_repository
        self.interview_round_config_repository = interview_round_config_repository
        self.interview_repository = interview_repository
        self.panelist_repository = panelist_repository
        self.slots_repository = slots_repository
        self.jwt_service: JWTService = jwt_service
        self.calendar_service = calendar_service
        self.candidate_email_service: CandidateEmailService = candidate_email_service
        self.panel_email_service: PanelEmailService = panel_email_service
        self.timeline_formatter: TimelineFormatter = timeline_formatter
        self.frontend_url = FRONTEND_URL

        self.logger = get_logger("InterviewService")

    # ─── Timeline ─────────────────────────────────────────────────────────

    async def get_timeline(self, interview_id: str) -> list[dict]:
        """
        Fetch all timeline events for an interview and return them
        formatted for the HR dashboard.
        """
        interview = await self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise DomainError("Interview not found", status_code=404)

        events = await self.interview_event_repository.get_events_by_interview_id(interview_id)
        return self.timeline_formatter.format_timeline(events)

    # ─── Helpers ──────────────────────────────────────────────────────────

    def _validate_booking_token(self, token: str) -> dict:
        """Decode and validate a candidate booking JWT."""
        payload = self.jwt_service.decode_token(token)
        interview_id = payload.get("interview_id")
        candidate_email = payload.get("candidate_email")
        if not interview_id or not candidate_email:
            raise DomainError("Invalid booking token payload", status_code=400)
        return payload

    async def _load_interview_and_config(self, interview_id: str):
        """Load interview + round config, raise if missing or wrong status."""
        interview = await self.interview_repository.get_interview_by_id(interview_id)
        if not interview:
            raise DomainError("Interview not found", status_code=404)

        round_config = await self.interview_round_config_repository.get_interview_round_config_by_id(
            str(interview.round_config_id)
        )
        if not round_config:
            raise DomainError("Interview round configuration not found", status_code=404)

        return interview, round_config

    # ─── GET booking form ─────────────────────────────────────────────────

    async def get_booking_form(self, token: str):
        """
        Validate token, return available slots for the candidate to pick.
        PANEL mode  → flat list of slots (panelist_email=null)
        SEQUENTIAL  → grouped by panelist {email: [slots]}
        """
        token = token.replace("Bearer ", "")
        payload = self._validate_booking_token(token)
        interview_id = payload["interview_id"]

        interview, round_config = await self._load_interview_and_config(interview_id)

        # Token match check
        if interview.booking_token != token:
            raise DomainError("Invalid or outdated booking link", status_code=400)

        # Already booked?
        if interview.status == InterviewStatus.SCHEDULED:
            return {
                "status": "already_booked",
                "message": "Your interview is already scheduled.",
                "scheduled_start": interview.scheduled_start.isoformat() if interview.scheduled_start else None,
                "scheduled_end": interview.scheduled_end.isoformat() if interview.scheduled_end else None,
            }

        # Token expired?
        if interview.booking_token_expires_at and interview.booking_token_expires_at < datetime.now(timezone.utc):
            return {
                "status": "expired",
                "message": "Your booking link has expired. Please contact HR for a new link.",
            }

        # Must be in READY_TO_BOOK
        if interview.status != InterviewStatus.READY_TO_BOOK:
            return {
                "status": "unavailable",
                "message": "Slots are not yet available for booking. Please wait for confirmation.",
            }

        # Build response based on panel mode
        if round_config.panel_mode == PanelMode.PANEL:
            slots = await self.slots_repository.get_available_slots(round_config.id)
            return {
                "status": "open",
                "panel_mode": "panel",
                "data": {
                    "title": round_config.title,
                    "interview_type": round_config.interview_type.value if round_config.interview_type else None,
                    "duration_minutes": round_config.duration_minutes,
                    "slots": [
                        {
                            "id": str(s.id),
                            "slot_start": s.slot_start.isoformat(),
                            "slot_end": s.slot_end.isoformat(),
                        }
                        for s in slots
                    ],
                },
            }
        else:
            # SEQUENTIAL mode — grouped by panelist
            grouped = await self.slots_repository.get_slots_grouped_by_panelist(round_config.id)
            panelist_slots = {}
            for email, slot_list in grouped.items():
                panelist_slots[email] = [
                    {
                        "id": str(s.id),
                        "slot_start": s.slot_start.isoformat(),
                        "slot_end": s.slot_end.isoformat(),
                    }
                    for s in slot_list
                ]
            return {
                "status": "open",
                "panel_mode": "sequential",
                "data": {
                    "title": round_config.title,
                    "interview_type": round_config.interview_type.value if round_config.interview_type else None,
                    "duration_minutes": round_config.duration_minutes,
                    "panelist_slots": panelist_slots,
                },
            }

    # ─── PANEL mode: book one slot ────────────────────────────────────────

    async def book_slot(self, token: str, slot_id: str):
        """
        PANEL mode: candidate claims one slot from the shared pool.
        Atomic via SELECT FOR UPDATE SKIP LOCKED.
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_booking_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)

            if interview.booking_token != token:
                raise DomainError("Invalid or outdated booking link", status_code=400)

            if interview.status == InterviewStatus.SCHEDULED:
                raise DomainError("Interview is already scheduled", status_code=400)

            if interview.status != InterviewStatus.READY_TO_BOOK:
                raise DomainError("Booking is not available for this interview", status_code=400)

            if round_config.panel_mode != PanelMode.PANEL:
                raise DomainError("This interview requires sequential booking", status_code=400)

            # Atomically claim the slot
            slot = await self.slots_repository.book_slot_atomic(
                slot_id=slot_id,
                interview_id=interview.id,
            )
            if not slot:
                raise DomainError(
                    "This slot is no longer available. Please pick another.",
                    status_code=409,
                )

            # Update interview
            interview.scheduled_start = slot.slot_start
            interview.scheduled_end = slot.slot_end
            interview.status = InterviewStatus.SCHEDULED
            interview.booking_token = ""  # Invalidate token

            # Check pool exhaustion → update round_config.slots_available
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False

            meeting_details = MeetingDetails(
                summary=round_config.title,
                description=f"Interview for {round_config.title}",
                location=round_config.interview_type.value if round_config.interview_type else "Online",
                start_time=slot.slot_start.isoformat(),
                end_time=slot.slot_end.isoformat(),
                timezone=round_config.timezone or "UTC",
                attendees_emails=None, #TODO : Will add later
                application_id=str(interview.application_id) if interview.application_id else None,
                reminders=[
                    Reminders(method="email", minutes_before=30),
                    Reminders(method="popup", minutes_before=10),
                ],
                visibility="public",
            )
            
            # ! currently using deskzero's calendar will need to update later on to hr or panel we calendar connection table to store those credential
            meet_link = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)

            # Timeline event
            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type="SLOT_BOOKED",
                actor=payload.get("candidate_email", "candidate"),
                details={
                    "slot_id": str(slot.id),
                    "slot_start": slot.slot_start.isoformat(),
                    "slot_end": slot.slot_end.isoformat(),
                    "panel_mode": "panel",
                },
            )
            round_config.meet_link = meet_link
            
            await self.db.commit()

            # Send confirmation email (best-effort, after commit)
            try:
                await self.db.refresh(interview, ["application"])
                application = interview.application
                if application:
                    await self.db.refresh(application, ["candidate"])
                    candidate = application.candidate
                    if candidate:
                        reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                            interview_id=str(interview.id),
                            candidate_email=candidate.email,
                            expiration_minutes=60 * 24 * 7,  # 7 days
                        )
                        reschedule_link = f"{self.frontend_url}/interview/reschedule?token={reschedule_token}"
                        await self.candidate_email_service.send_booking_confirmation_email(
                            candidate_email=candidate.email,
                            candidate_name=candidate.full_name or candidate.email,
                            interview_round_title=round_config.title,
                            scheduled_start=slot.slot_start,
                            scheduled_end=slot.slot_end,
                            meet_link=meet_link,
                            reschedule_link=reschedule_link,
                        )
            except Exception as e:
                self.logger.error(f"Failed to send booking confirmation email: {e}")

            # Notify panelists about the booking (best-effort)
            try:
                candidate_display = "Candidate"
                try:
                    await self.db.refresh(interview, ["application"])
                    app = interview.application
                    if app:
                        await self.db.refresh(app, ["candidate"])
                        if app.candidate:
                            candidate_display = app.candidate.full_name or app.candidate.email
                except Exception:
                    pass

                for panelist in (round_config.panelists or []):
                    p_email = panelist.get("email")
                    if not p_email:
                        continue
                    await self.panel_email_service.send_booking_confirmation_to_panelist(
                        panelist_email=p_email,
                        panelist_name=panelist.get("name"),
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        scheduled_start=slot.slot_start,
                        scheduled_end=slot.slot_end,
                        meet_link=meet_link,
                    )
            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notification: {e}")

            return {
                "status": "booked",
                "scheduled_start": slot.slot_start.isoformat(),
                "scheduled_end": slot.slot_end.isoformat(),
                "meet_link": meet_link,
            }

        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error booking slot: {e}")
            raise DomainError("An error occurred while booking your slot. Please try again.")

    # ─── SEQUENTIAL mode: book one slot per panelist ──────────────────────

    async def book_sequential_slots(self, token: str, bookings: list[dict]):
        """
        SEQUENTIAL mode: candidate picks one slot per panelist.
        bookings = [{"panelist_email": "...", "slot_id": "..."}, ...]
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_booking_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)

            if interview.booking_token != token:
                raise DomainError("Invalid or outdated booking link", status_code=400)

            if interview.status == InterviewStatus.SCHEDULED:
                raise DomainError("Interview is already scheduled", status_code=400)

            if interview.status != InterviewStatus.READY_TO_BOOK:
                raise DomainError("Booking is not available for this interview", status_code=400)

            if round_config.panel_mode != PanelMode.SEQUENTIAL:
                raise DomainError("This interview requires single-slot booking", status_code=400)

            # Validate that we have one slot per panelist
            panelist_emails = [p["email"] for p in (round_config.panelists or []) if p.get("email")]
            booking_emails = {b["panelist_email"] for b in bookings}

            missing = set(panelist_emails) - booking_emails
            if missing:
                raise DomainError(
                    f"Missing slot selection for panelists: {', '.join(missing)}",
                    status_code=400,
                )

            # Atomically claim each slot
            booked_slots = []
            for booking in bookings:
                slot = await self.slots_repository.book_slot_atomic(
                    slot_id=booking["slot_id"],
                    interview_id=interview.id,
                )
                if not slot:
                    raise DomainError(
                        f"Slot for {booking['panelist_email']} is no longer available. Please pick another.",
                        status_code=409,
                    )
                # Verify this slot actually belongs to the right panelist
                if slot.panelist_email != booking["panelist_email"]:
                    # Release it back
                    await self.slots_repository.release_slot(slot.id)
                    raise DomainError(
                        f"Selected slot does not belong to panelist {booking['panelist_email']}",
                        status_code=400,
                    )
                booked_slots.append(slot)

            # Use the earliest slot as the scheduled_start, latest as scheduled_end
            earliest = min(s.slot_start for s in booked_slots)
            latest = max(s.slot_end for s in booked_slots)

            interview.scheduled_start = earliest
            interview.scheduled_end = latest
            interview.status = InterviewStatus.SCHEDULED
            interview.booking_token = ""  # Invalidate

            # Check pool exhaustion
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False
                
                
            meeting_details = MeetingDetails(
                summary=round_config.title,
                description=f"Interview for {round_config.title}",
                location=round_config.interview_type.value if round_config.interview_type else "Online",
                start_time=slot.slot_start.isoformat(),
                end_time=slot.slot_end.isoformat(),
                timezone=round_config.timezone or "UTC",
                attendees_emails=None, #TODO : Will add later
                application_id=str(interview.application_id) if interview.application_id else None,
                reminders=[
                    Reminders(method="email", minutes_before=30),
                    Reminders(method="popup", minutes_before=10),
                ],
                visibility="public",
            )
            
            # ! currently using deskzero's calendar will need to update later on to hr or panel we calendar connection table to store those credential
            meet_link = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)


            # Timeline event
            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type="SLOT_BOOKED",
                actor=payload.get("candidate_email", "candidate"),
                details={
                    "slots": [
                        {
                            "slot_id": str(s.id),
                            "panelist_email": s.panelist_email,
                            "slot_start": s.slot_start.isoformat(),
                            "slot_end": s.slot_end.isoformat(),
                        }
                        for s in booked_slots
                    ],
                    "panel_mode": "sequential",
                },
            )
            round_config.meet_link = meet_link
            await self.db.commit()

            # Send confirmation email (best-effort, after commit)
            try:
                await self.db.refresh(interview, ["application"])
                application = interview.application
                if application:
                    await self.db.refresh(application, ["candidate"])
                    candidate = application.candidate
                    if candidate:
                        reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                            interview_id=str(interview.id),
                            candidate_email=candidate.email,
                            expiration_minutes=60 * 24 * 7,
                        )
                        reschedule_link = f"{self.frontend_url}/interview/reschedule?token={reschedule_token}"
                        await self.candidate_email_service.send_booking_confirmation_email(
                            candidate_email=candidate.email,
                            candidate_name=candidate.full_name or candidate.email,
                            interview_round_title=round_config.title,
                            scheduled_start=earliest,
                            scheduled_end=latest,
                            meet_link=meet_link,
                            reschedule_link=reschedule_link,
                        )
            except Exception as e:
                self.logger.error(f"Failed to send booking confirmation email: {e}")

            # Notify each panelist about their specific booked slot (best-effort)
            try:
                candidate_display = "Candidate"
                try:
                    await self.db.refresh(interview, ["application"])
                    app = interview.application
                    if app:
                        await self.db.refresh(app, ["candidate"])
                        if app.candidate:
                            candidate_display = app.candidate.full_name or app.candidate.email
                except Exception:
                    pass

                # Build a lookup: panelist_email → slot
                slot_by_panelist = {s.panelist_email: s for s in booked_slots}

                # Also build name lookup from round_config.panelists JSONB
                name_by_email = {
                    p["email"]: p.get("name")
                    for p in (round_config.panelists or [])
                    if p.get("email")
                }

                for p_email, slot in slot_by_panelist.items():
                    await self.panel_email_service.send_booking_confirmation_to_panelist(
                        panelist_email=p_email,
                        panelist_name=name_by_email.get(p_email),
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        scheduled_start=slot.slot_start,
                        scheduled_end=slot.slot_end,
                        meet_link=meet_link,
                    )
            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notifications: {e}")

            return {
                "status": "booked",
                "scheduled_start": earliest.isoformat(),
                "scheduled_end": latest.isoformat(),
                "meet_link": meet_link,
                "slots": [
                    {
                        "panelist_email": s.panelist_email,
                        "slot_start": s.slot_start.isoformat(),
                        "slot_end": s.slot_end.isoformat(),
                    }
                    for s in booked_slots
                ],
            }

        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error booking sequential slots: {e}")
            raise DomainError("An error occurred while booking your slots. Please try again.")