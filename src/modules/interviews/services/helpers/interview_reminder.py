"""Pure helper functions for building reminder and notification payloads. No DB or queue dependencies."""
from datetime import datetime, timedelta, timezone
from src.dtos.job_settings_dto import ReminderSettingsDTO
from src.dtos.emails.panel_dto import (
    PanelistReminderAvailabilityData,
    PanelistInterviewReminderData,
    AvailableSlotsData,
    PanelistBookingData,
    PanelistSlotReleasedData,
    PanelistMeetingRescheduledData,
    ThankYouPanelistData,
    PanelistFeedbackData,
)
from src.dtos.emails.candidate_dto import (
    CandidateBookingLinkReminderData,
    CandidateInterviewReminderData,
    CandidateBookingLinkData,
    CandidateBookingConfirmationData,
    CandidateRescheduleNewSlotsData,
)
from src.modules.reminders.reminder_dtos import CreateReminderDTO
from src.modules.reminders.model.reminder_enum import EntityType, RecipientType, ReminderType
from src.dtos.notification_dto import CreateNotificationDTO, Email_Template_Keys
from src.modules.notifications.model.notification_enum import (
    EntityType as NotificationEntityType,
    RecipientType as NotificationRecipientType,
    NotificationChannel,
)
from src.utils.time_helper import serialize_datetime

def build_panelist_form_reminder_payloads(
    panelists: list,
    config,
    reminder_settings: ReminderSettingsDTO,
) -> list[CreateReminderDTO]:
    """Build form reminder DTOs for panelists."""
    reminders_payload = []
    for panelist in panelists:
        for reminder_sec in set(reminder_settings.form_reminder_sec):
            reminders_payload.append(CreateReminderDTO(
                entity_id=str(config.id),
                entity_type=EntityType.INTERVIEW,
                payload=PanelistReminderAvailabilityData(
                    panelist_email=panelist.email,
                    panelist_name=panelist.name,
                    interview_round_title=config.title,
                    form_link=f"/panelist/availability?token={panelist.availability_token}"
                ).model_dump(),
                recipient_id=str(panelist.id),
                recipient_type=RecipientType.PANELIST,
                reminder_type=ReminderType.BOOKING_LINK,
                template_key=Email_Template_Keys.FORM_REMINDER,
                next_run_at=datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)
            ))
    return reminders_payload


def build_candidate_form_reminder_payloads(
    candidate,
    round_config,
    reminder_settings: ReminderSettingsDTO,
    booking_link: str,
    application_id: str,
) -> list[CreateReminderDTO]:
    """Build form reminder DTOs for candidates."""
    reminders_payload = []
    if reminder_settings and reminder_settings.enabled and reminder_settings.form_reminder_sec:
        for reminder_sec in reminder_settings.form_reminder_sec:
            reminders_payload.append(CreateReminderDTO(
                entity_id=str(round_config.id),
                entity_type=EntityType.INTERVIEW,
                payload=CandidateBookingLinkReminderData(
                    candidate_email=candidate.email,
                    candidate_name=candidate.full_name or candidate.email,
                    interview_round_title=round_config.title,
                    booking_link=booking_link
                ).model_dump(),
                recipient_id=str(application_id),
                recipient_type=RecipientType.CANDIDATE,
                reminder_type=ReminderType.BOOKING_LINK,
                template_key=Email_Template_Keys.Candidate_BOOKING_LINK_REMINDER,
                next_run_at=datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)
            ))
    return reminders_payload


def build_panelist_interview_reminder_payloads(
    panelist,
    interview,
    config,
    slot,
    meet_link: str,
    candidate_display: str,
    panelist_reschedule_link: str,
    reminder_settings: ReminderSettingsDTO,
) -> list[CreateReminderDTO]:
    """Build interview reminder DTOs for panelists."""
    reminders_payload = []
    for reminder_sec in reminder_settings.interview_reminder_sec:
        reminders_payload.append(CreateReminderDTO(
            entity_id=str(interview.id),
            entity_type=EntityType.INTERVIEW,
            payload=PanelistInterviewReminderData(
                candidate_name=candidate_display,
                panelist_name=panelist.name,
                panelist_email=panelist.email,
                interview_round_title=config.title,
                scheduled_start=serialize_datetime(slot.slot_start),
                scheduled_end=serialize_datetime(slot.slot_end),
                meet_link=meet_link,
                reschedule_link=panelist_reschedule_link
            ).model_dump(mode="json"),
            recipient_id=str(panelist.id),
            recipient_type=RecipientType.PANELIST,
            reminder_type=ReminderType.INTERVIEW_UPCOMING,
            template_key=Email_Template_Keys.PANELIST_INTERVIEW_REMINDER,
            next_run_at=datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)
        ))
    return reminders_payload


def build_candidate_interview_reminder_payloads(
    candidate,
    interview,
    config,
    slot,
    meet_link: str,
    candidate_display: str,
    cand_reschedule_link: str,
    reminder_settings: ReminderSettingsDTO,
) -> list[CreateReminderDTO]:
    """Build interview reminder DTOs for candidates."""
    reminders_payload = []
    for reminder_sec in reminder_settings.interview_reminder_sec:
        reminders_payload.append(CreateReminderDTO(
            entity_id=str(interview.id),
            entity_type=EntityType.INTERVIEW,
            payload=CandidateInterviewReminderData(
                candidate_name=candidate_display,
                candidate_email=candidate.email,
                interview_round_title=config.title,
                scheduled_start=serialize_datetime(slot.slot_start),
                scheduled_end=serialize_datetime(slot.slot_end),
                meet_link=meet_link,
                reschedule_link=cand_reschedule_link
            ).model_dump(mode="json"),
            recipient_id=str(candidate.id or candidate.email),
            recipient_type=RecipientType.CANDIDATE,
            reminder_type=ReminderType.INTERVIEW_UPCOMING,
            template_key=Email_Template_Keys.INTERVIEW_UPCOMING,
            next_run_at=datetime.now(timezone.utc) + timedelta(seconds=reminder_sec)
        ))
    return reminders_payload


# ─────────────────────────────────────────────────────────────────────────────
# Notification builders (instant email sends routed through notification queue)
# ─────────────────────────────────────────────────────────────────────────────

def build_panelist_slot_availability_notifications(
    panelists: list,
    config,
    frontend_url: str,
) -> list[CreateNotificationDTO]:
    """Build SLOT_AVAILABILITY notifications for panelists."""
    return [
        CreateNotificationDTO(
            entity_type=NotificationEntityType.INTERVIEW,
            entity_id=str(config.id),
            recipient_type=NotificationRecipientType.PANELIST,
            recipient_id=str(p.id),
            channel=NotificationChannel.EMAIL,
            template_key=Email_Template_Keys.SLOT_AVAILABILITY,
            payload=AvailableSlotsData(
                panelist_email=p.email,
                panelist_name=p.name,
                interview_round_title=config.title,
                form_link=f"{frontend_url}/panelist/availability?token={p.availability_token}",
            ).model_dump(),
        )
        for p in panelists
    ]


def build_panelist_booking_confirmation_notification(
    panelist,
    interview,
    config,
    slot,
    candidate_display: str,
    meet_link: str | None,
    panelist_reschedule_link: str | None,
) -> CreateNotificationDTO:
    """Build BOOKING_CONFIRMATION notification for a panelist."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.PANELIST,
        recipient_id=str(panelist.id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.BOOKING_CONFIRMATION,
        payload=PanelistBookingData(
            panelist_email=panelist.email,
            panelist_name=panelist.name,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            scheduled_start=serialize_datetime(slot.slot_start),
            scheduled_end=serialize_datetime(slot.slot_end),
            meet_link=meet_link,
            reschedule_link=panelist_reschedule_link,
        ).model_dump(mode="json"),
    )


def build_panelist_slot_released_notification(
    panelist,
    interview,
    config,
    slot,
    candidate_display: str,
) -> CreateNotificationDTO:
    """Build SLOT_RELEASED notification for a panelist."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.PANELIST,
        recipient_id=str(panelist.id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.SLOT_RELEASED,
        payload=PanelistSlotReleasedData(
            panelist_email=panelist.email,
            panelist_name=panelist.name,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            schedule_start=serialize_datetime(slot.slot_start),
            schedule_end=serialize_datetime(slot.slot_end),
        ).model_dump(mode="json"),
    )


def build_panelist_meeting_rescheduled_notification(
    panelist,
    interview,
    config,
    old_slot,
    new_slot,
    candidate_display: str,
    meet_link: str | None,
    panelist_reschedule_link: str | None,
) -> CreateNotificationDTO:
    """Build MEETING_RESCHEDULED notification for a panelist."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.PANELIST,
        recipient_id=str(panelist.id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.MEETING_RESCHEDULED,
        payload=PanelistMeetingRescheduledData(
            panelist_email=panelist.email,
            panelist_name=panelist.name,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            old_scheduled_start=serialize_datetime(old_slot.slot_start),
            old_scheduled_end=serialize_datetime(old_slot.slot_end),
            new_scheduled_start=serialize_datetime(new_slot.slot_start),
            new_scheduled_end=serialize_datetime(new_slot.slot_end),
            meet_link=meet_link,
            reschedule_link=panelist_reschedule_link,
        ).model_dump(mode="json"),
    )


def build_panelist_thanks_for_availability_notification(
    panelist,
    config,
    edit_slots_link: str,
    validity_period: str | None = None,
) -> CreateNotificationDTO:
    """Build THANK_YOU_FOR_SUBMITTING_AVAILABILITY notification for a panelist."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(config.id),
        recipient_type=NotificationRecipientType.PANELIST,
        recipient_id=str(panelist.id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.THANK_YOU_FOR_SUBMITTING_AVAILABILITY,
        payload=ThankYouPanelistData(
            panelist_email=panelist.email,
            panelist_name=panelist.name,
            interview_round_title=config.title,
            edit_slots_link=edit_slots_link,
            validity_period=validity_period,
        ).model_dump(),
    )


def build_panelist_feedback_request_notification(
    panelist,
    interview,
    config,
    candidate_display: str,
    form_link: str,
    form_valid_till=None,
) -> CreateNotificationDTO:
    """Build PANELIST_FEEDBACK_REQUEST notification for a panelist."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.PANELIST,
        recipient_id=str(panelist.id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.PANELIST_FEEDBACK_REQUEST,
        payload=PanelistFeedbackData(
            panelist_email=panelist.email,
            panelist_name=panelist.name,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            form_link=form_link,
            form_valid_till=form_valid_till,
        ).model_dump(mode="json"),
    )


def build_candidate_booking_link_notification(
    candidate,
    config,
    booking_link: str,
    application_id: str,
) -> CreateNotificationDTO:
    """Build Candidate_BOOKING_LINK notification for a candidate."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(config.id),
        recipient_type=NotificationRecipientType.CANDIDATE,
        recipient_id=str(application_id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.Candidate_BOOKING_LINK,
        payload=CandidateBookingLinkData(
            candidate_email=candidate.email,
            candidate_name=candidate.full_name or candidate.email,
            interview_round_title=config.title,
            booking_link=booking_link,
        ).model_dump(),
    )


def build_candidate_booking_confirmation_notification(
    candidate,
    interview,
    config,
    slot,
    candidate_display: str,
    meet_link: str | None,
    cand_reschedule_link: str | None,
    application_id: str,
) -> CreateNotificationDTO:
    """Build Candidate_Interview_Booking_Confirmation notification for a candidate."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.CANDIDATE,
        recipient_id=str(application_id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.Candidate_Interview_Booking_Confirmation,
        payload=CandidateBookingConfirmationData(
            candidate_email=candidate.email,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            scheduled_start=serialize_datetime(slot.slot_start),
            scheduled_end=serialize_datetime(slot.slot_end),
            meet_link=meet_link,
            reschedule_link=cand_reschedule_link,
        ).model_dump(mode="json"),
    )


def build_candidate_reschedule_notification(
    candidate,
    interview,
    config,
    new_slot,
    candidate_display: str,
    cand_reschedule_link: str,
    application_id: str,
    reason: str | None = None,
) -> CreateNotificationDTO:
    """Build RESCHEDULE notification for a candidate."""
    return CreateNotificationDTO(
        entity_type=NotificationEntityType.INTERVIEW,
        entity_id=str(interview.id),
        recipient_type=NotificationRecipientType.CANDIDATE,
        recipient_id=str(application_id),
        channel=NotificationChannel.EMAIL,
        template_key=Email_Template_Keys.RESCHEDULE,
        payload=CandidateRescheduleNewSlotsData(
            candidate_email=candidate.email,
            candidate_name=candidate_display,
            interview_round_title=config.title,
            scheduled_start=serialize_datetime(new_slot.slot_start),
            scheduled_end=serialize_datetime(new_slot.slot_end),
            reschedule_link=cand_reschedule_link,
            reason=reason,
        ).model_dump(mode="json"),
    )
