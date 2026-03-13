from datetime import datetime
from zoneinfo import ZoneInfo


def format_interview_time(dt: datetime, timezone: str = "Asia/Kolkata") -> str:
    """
    Convert datetime to a readable timezone-aware format
    Example: 21 March, 8:00 AM IST
    """

    tz = ZoneInfo(timezone)

    # Convert to timezone
    local_dt = dt.astimezone(tz)

    return local_dt.strftime("%d %B, %I:%M %p %Z")



def format_interview_schedule(start: datetime, end: datetime, timezone: str = "Asia/Kolkata") -> str:
    tz = ZoneInfo(timezone)

    start_local = start.astimezone(tz)
    end_local = end.astimezone(tz)

    date = start_local.strftime("%d %B")
    start_time = start_local.strftime("%I:%M %p")
    end_time = end_local.strftime("%I:%M %p")
    zone = start_local.strftime("%Z")

    return f"{date}, {start_time} – {end_time} {zone}"