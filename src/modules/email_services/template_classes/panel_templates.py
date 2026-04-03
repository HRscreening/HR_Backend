from src.modules.email_services.base import EmailTemplate
from src.utils.time_helper import TimeHelper
from src.utils.templte_engine import render_template
from src.dtos.emails.panel_dto import *


class PanelistBookingTemplate(EmailTemplate):
    def __init__(
        self,
        data: PanelistBookingData,
        time_helper: TimeHelper | None = None
    ):
        self.data = data
        self.time_helper  = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Interview Scheduled: {self.data.interview_round_title}"

    def get_body(self):
        interview_date, interview_time = self.time_helper.format_interview_schedule_for_email(
            self.data.scheduled_start,
            self.data.scheduled_end
        )

        return render_template("email/panel/booking.html", {
            "panelist_name": self.data.panelist_name,
            "candidate_name": self.data.candidate_name,
            "interview_round_title": self.data.interview_round_title,
            "interview_date": interview_date,
            "interview_time": interview_time,
            "meet_link": self.data.meet_link,
            "reschedule_link": self.data.reschedule_link
        })
        
        
class PanelistAvailabilityTemplate(EmailTemplate):
    def __init__(
        self,
        data:AvailableSlotsData
        
    ):
        self.data = data

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Submit Availability: {self.data.interview_round_title}"

    def get_body(self):
        return render_template("email/panel/available_slots.html", {
            "panelist_name": self.data.panelist_name,
            "interview_round_title": self.data.interview_round_title,
            "form_link": self.data.form_link,
        })
        
        
class PanelistThankYouAvailabilityTemplate(EmailTemplate):
    def __init__(
        self,
        data:ThankYouPanelistData
    ):
        self.data = data

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Availability Submitted: {self.data.interview_round_title}"

    def get_body(self):
        return render_template("email/panel/thank_you_availability.html", {
            "panelist_name": self.data.panelist_name,
            "interview_round_title": self.data.interview_round_title,
            "edit_slots_link": self.data.edit_slots_link,
            "validity_period": self.data.validity_period,
        })
        

class PanelistSlotReleasedTemplate(EmailTemplate):
    def __init__(self, data: PanelistSlotReleasedData, time_helper: TimeHelper | None = None):
        self.data = data
        self.time_helper = time_helper or TimeHelper()
        

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Interview Slot Released: {self.data.interview_round_title}"

    def get_body(self):
        interview_date, interview_time = self.time_helper.format_interview_schedule_for_email(
            self.data.schedule_start,
            self.data.schedule_end
        )
        return render_template("email/panel/slot_released.html", {
            "panelist_name": self.data.panelist_name,
            "candidate_name": self.data.candidate_name,
            "interview_round_title": self.data.interview_round_title,
            "interview_date": interview_date,
            "interview_time": interview_time,
        })
        

class PanelistMeetingRescheduledTemplate(EmailTemplate):
    def __init__(self, data: PanelistMeetingRescheduledData,time_helper: TimeHelper | None = None):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Interview Rescheduled: {self.data.interview_round_title}"

    def get_body(self):
        old_date, old_time = self.time_helper.format_interview_schedule_for_email(
            self.data.old_scheduled_start,
            self.data.old_scheduled_end
        )
        new_date, new_time = self.time_helper.format_interview_schedule_for_email(
            self.data.new_scheduled_start,
            self.data.new_scheduled_end
        )
        return render_template(
            "email/panel/meeting_rescheduled.html",
            {
            "panelist_name": self.data.panelist_name,
            "candidate_name": self.data.candidate_name,
            "interview_round_title": self.data.interview_round_title,
            "old_date": old_date,
            "old_time": old_time,
            "new_date": new_date,
            "new_time": new_time,
            "meet_link": self.data.meet_link,
            "reschedule_link": self.data.reschedule_link,
            }
        )
        
        
class PanelistReminderAvailabilityTemplate(EmailTemplate):
    def __init__(self, data: PanelistReminderAvailabilityData):
        self.data = data

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Reminder: Submit Availability for {self.data.interview_round_title}"

    def get_body(self):
        return render_template(
            "email/panel/reminder_availability.html",
            self.data.model_dump()
        )
        

class PanelistInterviewReminderTemplate(EmailTemplate):
    def __init__(
        self,
        data: PanelistInterviewReminderData,
        time_helper: TimeHelper | None = None
    ):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Reminder: Upcoming Interview - {self.data.interview_round_title}"

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

        return render_template(
            "email/panel/interview_reminder.html",
            context
        )
        
        
        
class PanelistInterviewFeedbackTemplate(EmailTemplate):
    def __init__(
        self,
        data: PanelistFeedbackData,
        time_helper: TimeHelper | None = None
    ):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Feedback Request: {self.data.interview_round_title}"

    def get_body(self):
        valid_before = self.time_helper.convert_date_to_str(self.data.form_valid_till) if self.data.form_valid_till else None

        context = self.data.model_dump()
        
        if valid_before:
            context.update({"form_valid_till": valid_before})

        return render_template(
            "email/panel/request_feedback.html",
            context
        )
    
        
class PanelistInterviewFeedbackReminderTemplate(EmailTemplate):
    def __init__(
        self,
        data: PanelistFeedbackData,
        time_helper: TimeHelper | None = None
    ):
        self.data = data
        self.time_helper = time_helper or TimeHelper()

    def get_recipient(self):
        return self.data.panelist_email

    def get_subject(self):
        return f"Reminder: Feedback Request for {self.data.interview_round_title}"

    def get_body(self):
        valid_before = self.time_helper.convert_date_to_str(self.data.form_valid_till) if self.data.form_valid_till else None

        context = self.data.model_dump()
        
        if valid_before:
            context.update({"form_valid_till": valid_before})

        return render_template(
            "email/panel/feedback_reminder.html",
            context
        )
    