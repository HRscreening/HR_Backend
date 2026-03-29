from src.modules.email_services.base import EmailTemplate
from src.utils.time_helper import TimeHelper
from src.utils.templte_engine import render_template
from src.dtos.emails.candidate_dto import (
    CandidateBookingLinkData,
    CandidateBookingConfirmationData,
    CandidateRescheduleNewSlotsData,
    CandidateBookingLinkReminderData,
    CandidateInterviewReminderData
)

class CandidateBookingLinkTemplate(EmailTemplate):
    def __init__(self, data: CandidateBookingLinkData):
        self.data = data

    def get_recipient(self):
        return self.data.candidate_email

    def get_subject(self):
        return f"Your Interview Slots Are Ready — {self.data.interview_round_title}"

    def get_body(self):
        return render_template("email/candidate/booking_link.html", self.data.model_dump())

class CandidateBookingConfirmationTemplate(EmailTemplate):
    def __init__(self, data: CandidateBookingConfirmationData, time_helper: TimeHelper | None = None):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.candidate_email

    def get_subject(self):
        return f"Interview Confirmed — {self.data.interview_round_title}"

    def get_body(self):
        interview_date, interview_time = self.time_helper.format_interview_schedule_for_email(
            self.data.scheduled_start,
            self.data.scheduled_end
        )
        context = self.data.model_dump()
        context.update({
            "interview_date": interview_date,
            "interview_time": interview_time,
        })
        return render_template("email/candidate/booking_confirmation.html", context)

class CandidateRescheduleNewSlotsTemplate(EmailTemplate):
    def __init__(self, data: CandidateRescheduleNewSlotsData, time_helper: TimeHelper | None = None):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.candidate_email

    def get_subject(self):
        return f"Interview Schedule Updated — {self.data.interview_round_title}"

    def get_body(self):
        interview_date, interview_time = self.time_helper.format_interview_schedule_for_email(
            self.data.scheduled_start,
            self.data.scheduled_end
        )
        context = self.data.model_dump()
        context.update({
            "interview_date": interview_date,
            "interview_time": interview_time,
        })
        return render_template("email/candidate/reschedule_new_slots.html", context)

class CandidateBookingLinkReminderTemplate(EmailTemplate):
    def __init__(self, data: CandidateBookingLinkReminderData):
        self.data = data

    def get_recipient(self):
        return self.data.candidate_email

    def get_subject(self):
        return f"Reminder: Book Your Interview Slot — {self.data.interview_round_title}"

    def get_body(self):
        return render_template("email/candidate/booking_link_reminder.html", self.data.model_dump())

class CandidateInterviewReminderTemplate(EmailTemplate):
    def __init__(self, data: CandidateInterviewReminderData, time_helper: TimeHelper | None = None):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.candidate_email

    def get_subject(self):
        return f"Reminder: Upcoming Interview — {self.data.interview_round_title}"

    def get_body(self):
        interview_date, interview_time = self.time_helper.format_interview_schedule_for_email(
            self.data.scheduled_start,
            self.data.scheduled_end
        )
        context = self.data.model_dump()
        context.update({
            "interview_date": interview_date,
            "interview_time": interview_time,
        })
        return render_template("email/candidate/interview_reminder.html", context)
