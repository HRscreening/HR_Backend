from pydantic import BaseModel, EmailStr, Field,field_validator
from typing import Optional, List
from datetime import datetime, date, timezone

from pydantic import BaseModel, Field, model_validator
from typing import List,Literal
from uuid import UUID

no_show_action_enum = Literal["cancel_interview", "mark_no_show","reject_candidate"]
rescore_on_rubric_change_enum  = Literal["only_new", "all"]
auto_move_to_next_round_enum = Literal["both_panel_and_ai","panel_only","ai_only","hr_manual"]


class ReminderSettingsDTO(BaseModel):
    enabled: bool = Field(default=True)

    form_reminder_count: int = Field(..., example=3)
    form_reminder_sec: List[int] = Field(
        ..., example=[24, 12, 1],
        description="Hours AFTER form link is shared"
    )

    interview_reminder_count: int = Field(..., example=3)
    interview_reminder_sec: List[int] = Field(
        ..., example=[24, 12, 1],
        description="Hours BEFORE interview"
    )

    @model_validator(mode="after")
    def validate_reminders(self):
        if self.form_reminder_count != len(self.form_reminder_sec):
            raise ValueError("Form count must match number of timings")

        if self.interview_reminder_count != len(self.interview_reminder_sec):
            raise ValueError("Interview count must match number of timings")

        # if sorted(self.form_reminder_hours, reverse=True) != self.form_reminder_hours:
        #     raise ValueError("Form timings must be in descending order")

        # if sorted(self.interview_reminder_hours, reverse=True) != self.interview_reminder_hours:
        #     raise ValueError("Interview timings must be in descending order")

        return self
    
    

class PanelEscalationSettingsDTO(BaseModel):
    enabled: bool = Field(default=True)

    escalation_recipients: List[EmailStr] = Field(
        default_factory=list,
        description="Emails to notify on escalation"
    )
    


class ReschedulingSettingsDTO(BaseModel):
    enabled: bool = Field(default=True)

    panelist_rescheduling_allowed: bool = Field(default=True)
    candidate_rescheduling_allowed: bool = Field(default=True)

    reschedule_window_for_panelist: int = Field(default=86400, ge=0) # second
    reschedule_window_for_candidate: int = Field(default=86400, ge=0) # second

    no_show_action:no_show_action_enum  = "reject_candidate"
    no_show_grace_minutes: int = Field(default=15, ge=0)

    same_panel_on_reschedule: bool = Field(default=True)

    max_reschedule_allowed_by_panelist: int = Field(default=1, ge=0)
    max_reschedule_allowed_by_candidate: int = Field(default=1, ge=0)

    @model_validator(mode="after")
    def validate_settings(self):
        if not self.enabled:
            return self

        if not self.candidate_rescheduling_allowed and self.max_reschedule_allowed_by_candidate > 0:
            raise ValueError("Candidate rescheduling disabled but max_reschedule > 0")

        if not self.panelist_rescheduling_allowed and self.max_reschedule_allowed_by_panelist > 0:
            raise ValueError("Panelist rescheduling disabled but max_reschedule > 0")

        return self
    

class CreateJobSettingsDTO(BaseModel):
    voice_ai_enabled: bool = Field(default=False)
    manual_rounds_count: int = Field(default=0)
    is_confidential: bool = Field(default=False)

    auto_score_every_resume: bool = Field(default=False)
    auto_score_every_resume_on_manual_upload: bool = Field(default=False)
    auto_offer_enabled: bool = Field(default=False)
    ai_assessment_enabled: bool = Field(default=False)

    rescore_on_rubric_change: rescore_on_rubric_change_enum = "only_new"
    auto_move_to_next_round: auto_move_to_next_round_enum = "panel_only"

    panel_reminders: ReminderSettingsDTO = Field(default_factory=ReminderSettingsDTO)
    candidate_reminders: ReminderSettingsDTO = Field(default_factory=ReminderSettingsDTO)
    feedback_reminders: ReminderSettingsDTO = Field(default_factory=ReminderSettingsDTO)

    escalation: PanelEscalationSettingsDTO = Field(default_factory=PanelEscalationSettingsDTO)
    rescheduling: ReschedulingSettingsDTO = Field(default_factory=ReschedulingSettingsDTO)
    

class SettingsResponse(CreateJobSettingsDTO):
    id: str | UUID
    job_id: str | UUID
    created_at: datetime
    updated_at: datetime

    model_config = {
        "from_attributes": True
    }
    
class GeneralSettingsDTO(BaseModel):
    voice_ai_enabled: bool = Field(default=False)
    is_confidential: bool = Field(default=False)

    auto_score_every_resume: bool = Field(default=False)
    auto_score_every_resume_on_manual_upload: bool = Field(default=False)
    auto_offer_enabled: bool = Field(default=False)
    ai_assessment_enabled: bool = Field(default=False)
    
    rescore_on_rubric_change: rescore_on_rubric_change_enum = "only_new"
    auto_move_to_next_round: auto_move_to_next_round_enum = "panel_only"
    
    
class UpdateJobSettingsDTO(BaseModel):
    general: Optional[GeneralSettingsDTO] = None
    panel_reminders: Optional[ReminderSettingsDTO] = None
    candidate_reminders: Optional[ReminderSettingsDTO] = None
    feedback_reminders:  Optional[ReminderSettingsDTO] = None
    escalation: Optional[PanelEscalationSettingsDTO] = None
    rescheduling: Optional[ReschedulingSettingsDTO] = None
    
    
    
    @model_validator(mode="after")
    def validate_settings(self):

        # ✅ At least one field required
        if not any([
            self.general,
            self.panel_reminders,
            self.candidate_reminders,
            self.feedback_reminders,
            self.escalation,
            self.rescheduling
        ]):
            raise ValueError("At least one field must be provided for update")

        # ✅ Panel reminders
        if self.panel_reminders:
            if not self.panel_reminders.enabled and (
                self.panel_reminders.form_reminder_count > 0 or
                self.panel_reminders.interview_reminder_count > 0
            ):
                raise ValueError("Panel reminders disabled but counts > 0")

        # ✅ Candidate reminders
        if self.candidate_reminders:
            if not self.candidate_reminders.enabled and (
                self.candidate_reminders.form_reminder_count > 0 or
                self.candidate_reminders.interview_reminder_count > 0
            ):
                raise ValueError("Candidate reminders disabled but counts > 0")

        # ✅ Feedback reminders
        if self.feedback_reminders:
            if not self.feedback_reminders.enabled and (
                self.feedback_reminders.form_reminder_count > 0 or
                self.feedback_reminders.interview_reminder_count > 0
            ):
                raise ValueError("Feedback reminders disabled but counts > 0")

        return self