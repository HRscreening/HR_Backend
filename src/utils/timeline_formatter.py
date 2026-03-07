"""
Timeline Formatter
==================
Converts raw interview timeline event_type + details into
human-readable strings for the HR dashboard.
"""

from datetime import datetime
from configs.log_config import get_logger


class TimelineFormatter:
    """Formats raw Interview_TimeLine_Events into HR-friendly dicts."""

    EVENT_LABELS: dict[str, str] = {
        "INTERVIEW_CREATED": "Interview round created",
        "PANELIST_AVAILABILITY_REQUESTED": "Availability request sent to panelists",
        "PANELIST_AVAILABILITY_SUBMITTED": "Panelist submitted availability",
        "SLOT_COMPUTATION_SUCCESS": "Interview slots computed successfully",
        "SLOT_COMPUTATION_FAILED": "Slot computation failed",
        "SLOT_BOOKING_LINK_SENT": "Booking link sent to candidate",
        "SLOT_BOOKED": "Candidate booked an interview slot",
        "SLOT_RELEASED": "Interview slot released back to pool",
        "INTERVIEW_RESCHEDULED": "Interview rescheduled",
        "INTERVIEW_CANCELLED": "Interview cancelled",
        "INTERVIEW_COMPLETED": "Interview marked as completed",
        "FEEDBACK_SUBMITTED": "Panelist feedback submitted",
        "STATUS_CHANGED": "Interview status changed",
    }

    def __init__(self):
        self.logger = get_logger("TimelineFormatter")
        self._summary_builders: dict[str, callable] = {
            "INTERVIEW_CREATED": self._summary_interview_created,
            "PANELIST_AVAILABILITY_REQUESTED": self._summary_availability_requested,
            "PANELIST_AVAILABILITY_SUBMITTED": self._summary_availability_submitted,
            "SLOT_COMPUTATION_SUCCESS": self._summary_computation_success,
            "SLOT_COMPUTATION_FAILED": self._summary_computation_failed,
            "SLOT_BOOKING_LINK_SENT": self._summary_booking_link_sent,
            "SLOT_BOOKED": self._summary_slot_booked,
            "SLOT_RELEASED": self._summary_slot_released,
            "INTERVIEW_CANCELLED": self._summary_interview_cancelled,
            "FEEDBACK_SUBMITTED": self._summary_feedback_submitted,
        }

    # ─── Public API ───────────────────────────────────────────────────────

    def format_event(self, event) -> dict:
        """
        Format a single Interview_TimeLine_Events model instance
        into an HR-friendly dict for the dashboard.

        Args:
            event: Interview_TimeLine_Events SQLAlchemy model instance

        Returns:
            dict with keys: id, event_type, label, actor, details, summary, created_at
        """
        event_type = event.event_type or ""
        details = event.details or {}
        actor = event.actor or "system"

        label = self.EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())
        summary = self._build_summary(event_type, details, actor)

        return {
            "id": str(event.id),
            "event_type": event_type,
            "label": label,
            "actor": actor,
            "details": details,
            "summary": summary,
            "created_at": event.created_at.isoformat() if isinstance(event.created_at, datetime) else str(event.created_at),
        }

    def format_timeline(self, events: list) -> list[dict]:
        """Format a list of timeline events."""
        return [self.format_event(e) for e in events]

    # ─── Summary builders ─────────────────────────────────────────────────

    def _build_summary(self, event_type: str, details: dict, actor: str) -> str:
        """Build a concise human-readable summary from event type and details."""
        builder = self._summary_builders.get(event_type)
        if builder:
            return builder(details, actor)
        return self.EVENT_LABELS.get(event_type, event_type.replace("_", " ").title())

    def _summary_interview_created(self, details: dict, actor: str) -> str:
        title = details.get("round_title", "")
        rn = details.get("round_number", "")
        return f"Interview created for {title} (Round {rn})" if title else "Interview created"

    def _summary_availability_requested(self, details: dict, actor: str) -> str:
        count = details.get("panelist_count", 0)
        return f"Availability request sent to {count} panelist(s)"

    def _summary_availability_submitted(self, details: dict, actor: str) -> str:
        email = details.get("panelist_email", actor)
        count = details.get("slots_count", 0)
        return f"{email} submitted {count} availability slot(s)"

    def _summary_computation_success(self, details: dict, actor: str) -> str:
        count = details.get("slot_count", 0)
        mode = details.get("panel_mode", "panel")
        return f"{count} interview slot(s) computed ({mode} mode)"

    def _summary_computation_failed(self, details: dict, actor: str) -> str:
        reason = details.get("reason", "Unknown reason")
        return f"Slot computation failed: {reason}"

    def _summary_booking_link_sent(self, details: dict, actor: str) -> str:
        email = details.get("candidate_email", "candidate")
        return f"Booking link sent to {email}"

    def _summary_slot_booked(self, details: dict, actor: str) -> str:
        start = details.get("slot_start", "")
        mode = details.get("panel_mode", "panel")
        if mode == "sequential":
            slots = details.get("slots", [])
            return f"Candidate booked {len(slots)} sequential slot(s)"
        return f"Candidate booked slot starting {start}" if start else "Candidate booked a slot"

    def _summary_slot_released(self, details: dict, actor: str) -> str:
        return f"Slot released back to pool by {actor}"

    def _summary_interview_cancelled(self, details: dict, actor: str) -> str:
        reason = details.get("reason", "")
        return f"Interview cancelled{': ' + reason if reason else ''}"

    def _summary_feedback_submitted(self, details: dict, actor: str) -> str:
        email = details.get("panelist_email", actor)
        rating = details.get("rating", "")
        return f"Feedback submitted by {email}" + (f" — {rating}" if rating else "")


# Singleton instance
timeline_formatter = TimelineFormatter()
