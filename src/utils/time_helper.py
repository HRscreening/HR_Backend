from datetime import datetime, timezone
from zoneinfo import ZoneInfo

def format_time_according_to_timezone(dt: datetime, timezone: str = "Asia/Kolkata") -> str:
    """
    Convert datetime to a readable timezone-aware format
    Example: 
    """

    tz = ZoneInfo(timezone)
    local_dt = dt.astimezone(tz)
    return local_dt.isoformat()

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


def serialize_datetime(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()



def deserialize_datetime(dt) -> datetime:
    if isinstance(dt, datetime):
        return dt.astimezone(timezone.utc)

    if isinstance(dt, str):
        return datetime.fromisoformat(dt).astimezone(timezone.utc)

    raise ValueError(f"Invalid datetime input: {dt}")