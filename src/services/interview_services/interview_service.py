from sqlalchemy.ext.asyncio import AsyncSession
from  configs.log_config import get_logger
from configs.env_config import FRONTEND_URL,FireFlies_Bot,COMPANY_EMAIL
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
from typing import Optional
from src.models.enums import PanelistResponseStatus
from src.dtos.interviews_dtos.panel_dto import CreatePanelDTO
import asyncio


# TODO:  most of the methods doing same things and can be optimized skipping for future refactor for now to focus on feature development, also need to add more logs for better observability and debugging
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

    def _validate_token(self, token: str) -> dict:
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

    async def get_booking_form(self, token: str,is_reschedule: bool = False):
        """
        Validate token, return available slots for the candidate to pick.
        PANEL mode  → flat list of slots (panelist_email=null)
        SEQUENTIAL  → grouped by panelist {email: [slots]}
        """
        token = token.replace("Bearer ", "")
        payload = self._validate_token(token)
        interview_id = payload["interview_id"]

        interview, round_config = await self._load_interview_and_config(interview_id)

        # Token match check
        if is_reschedule == False and interview.booking_token != token:
            raise DomainError("Invalid or outdated booking link", status_code=400)
        
        
        if is_reschedule == True and interview.rescheduling_token != token:
            raise DomainError("Invalid or outdated rescheduling link", status_code=400)
        
        booked_slot = await self.slots_repository.get_booked_slot_by_interview_id(interview_id=interview_id)
        

        # Already booked?
        if not is_reschedule and interview.status == InterviewStatus.SCHEDULED:
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
        if not is_reschedule and interview.status != InterviewStatus.READY_TO_BOOK:
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
                "current_slot":{
                "id:": str(booked_slot.id) if booked_slot else None,
                "slot_start": booked_slot.slot_start.isoformat() if booked_slot else None,
                "slot_end": booked_slot.slot_end.isoformat() if booked_slot else None,
                },
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
                "current_slot":{
                "id:": str(booked_slot.id) if booked_slot else None,
                "slot_start": booked_slot.slot_start.isoformat() if booked_slot else None,
                "slot_end": booked_slot.slot_end.isoformat() if booked_slot else None,
                },
                "data": {
                    "title": round_config.title,
                    "interview_type": round_config.interview_type.value if round_config.interview_type else None,
                    "duration_minutes": round_config.duration_minutes,
                    "panelist_slots": panelist_slots,
                },
            }

    # ─── PANEL mode: book one slot ────────────────────────────────────────
    # Todo: need some fixes  for reschduling 
    async def book_slot(self, token: str, slot_id: str):
        """
        PANEL mode: candidate claims one slot from the shared pool.
        Atomic via SELECT FOR UPDATE SKIP LOCKED.
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
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
                
            attendees_emails = [COMPANY_EMAIL,FireFlies_Bot,payload.get("candidate_email", "")] + [panelist.get("email") for panelist in (round_config.panelists or []) if panelist.get("email")]

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
    # TODO: change bokings only one slot over all the panelist 
    async def book_sequential_slot(self, token: str, slot_id:str):
        """
        SEQUENTIAL mode: candidate picks one slot over all panelist.
        bookings = [{"panelist_email": "...", "slot_id": "..."}, ...]
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)
            
            slot = await self.slots_repository.get_slot_by_id(slot_id)

            if interview.booking_token != token:
                raise DomainError("Invalid or outdated booking link", status_code=400)

            if interview.status == InterviewStatus.SCHEDULED:
                raise DomainError("Interview is already scheduled", status_code=400)

            if interview.status != InterviewStatus.READY_TO_BOOK:
                raise DomainError("Booking is not available for this interview", status_code=400)

            if round_config.panel_mode != PanelMode.SEQUENTIAL:
                raise DomainError("This interview requires single-slot booking", status_code=400)
            
            pannelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config.id, slot.panelist_id)
            
            if not pannelist:
                raise DomainError(f"Panelist not found for selected slot", status_code=404)


            slot = await self.slots_repository.book_slot_atomic(
                slot_id=slot_id,
                interview_id=interview.id,
            )
            if not slot:
                raise DomainError(
                    f"Slot for {pannelist.email} is no longer available. Please pick another.",
                    status_code=409,
                )


            interview.scheduled_start = slot.slot_start
            interview.scheduled_end = slot.slot_end
            interview.status = InterviewStatus.SCHEDULED
            interview.booking_token = ""  # Invalidate
            interview.booking_token_expires_at = None

            # Check pool exhaustion
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False
            
            attendees_emails = [COMPANY_EMAIL,FireFlies_Bot,payload.get("candidate_email", "")] + [pannelist.email]  
                
            meeting_details = MeetingDetails(
                summary=round_config.title,
                description=f"Interview for {round_config.title}",
                location=round_config.interview_type.value if round_config.interview_type else "Online",
                start_time=slot.slot_start.isoformat(),
                end_time=slot.slot_end.isoformat(),
                timezone=round_config.timezone or "UTC",
                attendees_emails= attendees_emails,
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
                            "panelist_id": str(slot.panelist_id),
                            "slot_start": slot.slot_start.isoformat(),
                            "slot_end": slot.slot_end.isoformat(),
                    "panel_mode": "sequential",
                        }
            )
            
            expiry_time = slot.slot_start - timedelta(minutes=10)
            remaining_time = int(
                (expiry_time - datetime.now(timezone.utc)).total_seconds() / 60
            )
            reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                candidate_email=payload.get("candidate_email", ""),
                expiration_minutes=remaining_time,
                interview_id=str(interview.id)
            )

            interview.rescheduling_token_expires_at = expiry_time
            interview.meet_link = meet_link
            interview.rescheduling_token = reschedule_token
            await self.db.commit()

            # Send confirmation email (best-effort, after commit)
            try:
                await self.db.refresh(interview, ["application"])
                application = interview.application
                if application:
                    await self.db.refresh(application, ["candidate"])
                    candidate = application.candidate
                    if candidate:
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


                await self.panel_email_service.send_booking_confirmation_to_panelist(
                    panelist_email=pannelist.email,
                    panelist_name=pannelist.name,
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
                "scheduled_start": slot.slot_start.isoformat(),
                "scheduled_end": slot.slot_end.isoformat(),
                "meet_link": meet_link,
                "panelist_email": str(slot.panelist_id),
            }

        except DomainError:
            raise
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error booking sequential slots: {e}")
            raise DomainError("An error occurred while booking your slots. Please try again.")


   
    async def reschedule_to_new_slot(self, token: str, new_slot_id: str):
        """
        Reschedule an already booked interview to a new slot.
        This can be used for both PANEL and SEQUENTIAL modes, but the new slot must be valid for the interview's round config.
        """
        
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)
            
            if datetime.now(timezone.utc) > interview.scheduled_start:
                raise DomainError("Interview Has Already Started,Can't Reschdule", status_code=400)

            if datetime.now(timezone.utc) > interview.rescheduling_token_expires_at:
                raise DomainError("Rescheduling token has expired, can't reschedule", status_code=400)
            
            if interview.rescheduling_token != token:
                raise DomainError("Invalid or outdated rescheduling link", status_code=400)
            
            if interview.status != InterviewStatus.SCHEDULED:
                raise DomainError("Only scheduled interviews can be rescheduled", status_code=400)
            
            booked_slot = await self.slots_repository.get_booked_slot_for_interview(interview_id)
            
            if not booked_slot:
                raise DomainError("No booked slot found for this interview, cannot reschedule", status_code=404)
            
            await self.slots_repository.release_slot(booked_slot.id)
            
            new_slot = await self.slots_repository.get_slot_by_id(new_slot_id)
            
            if new_slot.is_booked:
                raise DomainError("Selected new slot is already booked, please choose another", status_code=409)
            
            # Attempt to book the new slot atomically
            await self.slots_repository.book_slot_atomic(
                slot_id=new_slot_id,
                interview_id=interview.id,
            )
            
            expiry_time = new_slot.slot_start - timedelta(minutes=10)
            remaining_time = int(
                (expiry_time - datetime.now(timezone.utc)).total_seconds() / 60
            )
            reschedule_token = self.jwt_service.create_candidate_reschedule_token(
                candidate_email=payload.get("candidate_email", ""),
                expiration_minutes=remaining_time,
                interview_id=str(interview.id)
            )
            
            interview.scheduled_start = new_slot.slot_start
            interview.scheduled_end = new_slot.slot_end
            interview.meet_link = None  # Clear existing meet link, will be regenerated after rescheduling
            interview.rescheduling_token = reschedule_token
            interview.rescheduling_token_expires_at = expiry_time
            
            
            # TODO: also delete event from calendar
            # TODO : cancel all Reminders and events related to the old slot and create new ones for the new slot

            
            remaining = await self.slots_repository.count_remaining(round_config.id)
            if remaining == 0:
                round_config.slots_available = False
        
            
            
            old_panelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config_id=round_config.id,panelist_id=booked_slot.panelist_id)
            
            if not old_panelist:
                self.logger.error(f"Old panelist with email {booked_slot.id} not found for round config {round_config.id}")
                raise DomainError("Original panelist not found, cannot reschedule", status_code=404)
 

            new_panelist =  await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config.id,new_slot.panelist_id) 
            
            if not new_panelist:
                raise DomainError(f"Panelist with id {new_slot.panelist_id} not found", status_code=404)
            
            # new slot panelist is different from old slot panelist then send email to new panelist and old panelist about the reschedule
            attendees_emails = [COMPANY_EMAIL,FireFlies_Bot,payload.get("candidate_email", "")] + [new_panelist.email]  
                
            meeting_details = MeetingDetails(
                summary=round_config.title,
                description=f"Interview for {round_config.title}",
                location=round_config.interview_type.value if round_config.interview_type else "Online",
                start_time=new_slot.slot_start.isoformat(),
                end_time=new_slot.slot_end.isoformat(),
                timezone=round_config.timezone or "UTC",
                attendees_emails= attendees_emails,
                application_id=str(interview.application_id) if interview.application_id else None,
                reminders=[
                    Reminders(method="email", minutes_before=30),
                    Reminders(method="popup", minutes_before=10),
                ],
                visibility="public",
            )
            
            # ! currently using deskzero's calendar will need to update later on to hr or panel we calendar connection table to store those credential
            meet_link = await self.calendar_service.create_google_calendar_event_owner_deskzero(meeting_details)

            
            # Send confirmation email (best-effort, after commit)
            try:
                await self.db.refresh(interview, ["application"])
                application = interview.application
                if application:
                    await self.db.refresh(application, ["candidate"])
                    candidate = application.candidate
                    if candidate:
                        reschedule_link = f"{self.frontend_url}/interview/reschedule?token={reschedule_token}"
                        await self.candidate_email_service.send_booking_confirmation_email(
                            candidate_email=candidate.email,
                            candidate_name=candidate.full_name or candidate.email,
                            interview_round_title=round_config.title,
                            scheduled_start=new_slot.slot_start,
                            scheduled_end=new_slot.slot_end,
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
                
                
                if old_panelist.email != new_panelist.email:
                    self.logger.info(f"Panelist changed from {old_panelist.email} to {new_panelist.email}, sending notifications to both panelists about the reschedule.")
                    
                    
                    # Notify old panelist about the reschedule
                    await self.panel_email_service.send_slot_released_to_panelist(
                        panelist_email=old_panelist.email,
                        panelist_name=old_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        old_scheduled_start=booked_slot.slot_start,
                        old_scheduled_end=booked_slot.slot_end,
                    )
                    
                    await self.interview_event_repository.create_interview_event(
                        interview_id=str(interview.id),
                        event_type="SLOT_RESCHEDULED",
                        actor=payload.get("candidate_email", "candidate"),
                        details={
                            "old_slot_id": str(booked_slot.id),
                            "new_slot_id": str(new_slot.id),
                            "old_slot_start": booked_slot.slot_start.isoformat(),
                            "old_slot_end": booked_slot.slot_end.isoformat(),
                            "old_panelist_email": old_panelist.email,
                            "new_slot_start": new_slot.slot_start.isoformat(),
                            "new_slot_end": new_slot.slot_end.isoformat(),
                            "new_panelist_email": new_panelist.email,
                        },
                    )
                                            
                    # Notify new panelist about the reschedule and new booking
                    await self.panel_email_service.send_booking_confirmation_to_panelist(
                        panelist_email=new_panelist.email,
                        panelist_name=new_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        scheduled_start=new_slot.slot_start,
                        scheduled_end=new_slot.slot_end,
                        meet_link=meet_link,
                    )
                else:                     
                    await self.interview_event_repository.create_interview_event(
                        interview_id=str(interview.id),
                        event_type="SLOT_RESCHEDULED",
                        actor=payload.get("candidate_email", "candidate"),
                        details={
                            "old_slot_id": str(booked_slot.id),
                            "new_slot_id": str(new_slot.id),
                            "old_slot_start": booked_slot.slot_start.isoformat(),
                            "old_slot_end": booked_slot.slot_end.isoformat(),
                            "new_slot_start": new_slot.slot_start.isoformat(),
                            "new_slot_end": new_slot.slot_end.isoformat(),
                        },
                    )
                    
                    # sending reschuduled email to the same panelist if the panelist is same for old slot and new slot because of the time change 
                    await self.panel_email_service.send_meeting_rescheduled_email_to_panelist(
                        panelist_email=new_panelist.email,
                        panelist_name=new_panelist.name,
                        candidate_name=candidate_display,
                        interview_round_title=round_config.title,
                        old_scheduled_start=booked_slot.slot_start,
                        old_scheduled_end=booked_slot.slot_end,
                        new_scheduled_start=new_slot.slot_start,
                        new_scheduled_end=new_slot.slot_end,
                        new_meet_link=meet_link,
                    )

            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notifications: {e}")
                
            await self.db.commit()

            return {
                "status": "booked",
                "scheduled_start": new_slot.slot_start.isoformat(),
                "scheduled_end": new_slot.slot_end.isoformat(),
                "meet_link": meet_link,
                "panelist_email": new_panelist.email,
            }
        
        except DomainError:
            raise
        
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error rescheduling to new slot: {e}")
            raise DomainError("An error occurred while rescheduling your slot. Please try again.")
        
        
    async def cancel_interview(self, token: str, cancellation_reason: Optional[str] = None):
        """
        Cancel a scheduled interview triggered by candidate. This will release the booked slot and notify panelists and candidates.
        Reschdule token can also be used to cancel the interview, as cancellation and reschdule share the same token and expiration logic.
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)
                        

            if datetime.now(timezone.utc) > interview.scheduled_start:
                raise DomainError("Interview Has Already Started,Can't Cancel", status_code=400)

                raise DomainError("Cancellation token has expired, can't cancel", status_code=400)
            
            if interview.status != InterviewStatus.SCHEDULED:
                raise DomainError("Only scheduled interviews can be canceled", status_code=400)
            
            booked_slot = await self.slots_repository.get_booked_slot_for_interview(interview_id)
            
            if not booked_slot:
                raise DomainError("No booked slot found for this interview, cannot cancel", status_code=404)
            
            pannelist = await self.panelist_repository.get_panelist_by_round_config_and_panelist_id(round_config_id=round_config.id,panelist_id=booked_slot.panelist_id)
                        
            if not pannelist:
                self.logger.error(f"Panelist with email {booked_slot.panelist_id} not found for round config {round_config.id}")
                raise DomainError("Panelist not found, cannot cancel", status_code=404)
            
            
            await self.slots_repository.release_slot(booked_slot.id)
            
            interview.status = InterviewStatus.CANCELED
            interview.cancellation_reason = cancellation_reason
            interview.scheduled_start = None
            interview.scheduled_end = None
            interview.meet_link = None  # Clear meet link, as the interview is cancelled
            
            remaining_slots = await self.slots_repository.count_remaining(round_config.id)
            
            if remaining_slots == 1:
                round_config.slots_available = True

            #Todo : delete event from calendar
            #Todo : cancel all Reminders and events related to the old slot
            
            # Notify panelist about the cancellation (best-effort, after commit)
             # Send confirmation email (best-effort, after commit)
            try:
                await self.db.refresh(interview, ["application"])
                application = interview.application
                if application:
                    await self.db.refresh(application, ["candidate"])
                    candidate = application.candidate  
                    await self.candidate_email_service.send_meeting_cancelled_mail_to_candidate(
                        candidate_email=candidate.email,
                        candidate_name=candidate.full_name or candidate.email,
                        interview_round_title=round_config.title,
                        scheduled_start=booked_slot.slot_start,
                        scheduled_end=booked_slot.slot_end,
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


                await self.panel_email_service.send_meeting_cancelled_email__to_panelist(
                    panelist_email=pannelist.email,
                    panelist_name=pannelist.name,
                    candidate_name=candidate_display,
                    interview_round_title=round_config.title,
                    scheduled_start=booked_slot.slot_start,
                    scheduled_end=booked_slot.slot_end,
                )
            except Exception as e:
                self.logger.error(f"Failed to send panelist booking notifications: {e}")

            
        except DomainError:
            raise
        
        except Exception as e:
            await self.db.rollback()
            self.logger.error(f"Error cancelling interview: {e}")
            raise DomainError("An error occurred while cancelling your interview. Please try again.")


    async def request_for_slots(self, token: str):
        """
        Allow candidate to request for new slots if they are not happy with the currently available slots. This will notify the recruiter to add more slots or make necessary changes.
        """
        try:
            token = token.replace("Bearer ", "")
            payload = self._validate_token(token)
            interview_id = payload["interview_id"]

            interview, round_config = await self._load_interview_and_config(interview_id)

            if interview.booking_token != token:
                raise DomainError("Invalid or outdated booking link", status_code=400)

            # if interview.status == InterviewStatus.SCHEDULED:
            #     raise DomainError("Interview is already scheduled", status_code=400)


            # if interview.status != InterviewStatus.READY_TO_BOOK:
            #     raise DomainError("Requesting new slots is not available for this interview", status_code=400)

            interview.status = InterviewStatus.COLLECTING_AVAILABILITY
                
            # Ask Panelist for new slots 
            remaining_seconds = (round_config.end_date - datetime.now(timezone.utc)).total_seconds()

            if remaining_seconds <= 0:
                raise DomainError("Round already expired")

            token_expiry_in_min = max(1, int(remaining_seconds // 60))
            
            
            panelist_not_requested = await self.panelist_repository.get_panelists_not_pending(round_config.id)

            if not panelist_not_requested:
                raise DomainError(
                    "All panelists have already been requested for availability, wait for them to respond or contact your recruiter for assistance."
                )
                
            await self.interview_event_repository.create_interview_event(
                interview_id=str(interview.id),
                event_type="Candidate Requested for new slots",
                actor="Candiate",
                details={
                    "panelist_emails": [p.email for p in panelist_not_requested],
                    "info":"Thsese panelist are requested for availability as candidate requested for new slots",
                },
            )
            
            panelists = []
            
            for p in panelist_not_requested:
                p.response_status = PanelistResponseStatus.PENDING
                p.availability_token = self.jwt_service.create_panelist_availability_token(
                    round_config_id=str(round_config.id),
                    expiration_minutes=token_expiry_in_min,
                    interview_id=str(interview.id),
                    panelist_email=p.email
                    )
                panelists.append(p)
            

            await self.db.commit()
            
                
            # TODO: Enque email sending task if many panelists to avoid delays in response
            tasks = [
                self.panel_email_service.send_slot_availability_email(
                    panelist_email=panelist.email,
                    panelist_name=panelist.name,
                    interview_round_title=round_config.title,
                    form_link=f"{self.frontend_url}/panelist/availability?token={panelist.availability_token}",
                )
                for panelist in panelists
            ]

            await asyncio.gather(*tasks, return_exceptions=True)

            
            return 
        except DomainError:
            raise

        except Exception as e:
            self.logger.error(f"Error requesting new slots: {e}")
            raise DomainError("An error occurred while requesting new slots. Please try again.")


