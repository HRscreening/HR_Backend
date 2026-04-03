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


class TimeHelper:
    @staticmethod
 
    
    @staticmethod
    def to_timezone(dt: datetime, timezone: str = "Asia/Kolkata") -> datetime:
        tz = ZoneInfo(timezone)

        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=ZoneInfo("UTC"))

        return dt.astimezone(tz)
    
    
    @staticmethod
    def format_time(dt: datetime, timezone: str = "Asia/Kolkata") -> str:
        """Format a datetime into a human-readable string in the specified timezone.
           Example: 2024-03-21 08:00:00 IST
        """
        local_dt = TimeHelper.to_timezone(dt, timezone)
        return local_dt.strftime("%Y-%m-%d %H:%M:%S %Z")
    
    

    @staticmethod
    def format_email_datetime(dt: datetime, timezone: str = "Asia/Kolkata") -> str:
        """Format a datetime for email content, e.g., 'Mar 21, 2024 at 08:00 AM IST'"""
        local_dt = TimeHelper.to_timezone(dt, timezone)
        return local_dt.strftime("%b %d, %Y at %I:%M %p %Z")


    @staticmethod
    def format_interview_schedule_for_email(
        start: datetime,
        end: datetime,
        timezone: str = "Asia/Kolkata"
    ) -> tuple[str, str]:

        if not start or not end:
            raise ValueError("Start and end time required")

        start_local = TimeHelper.to_timezone(start, timezone)
        end_local = TimeHelper.to_timezone(end, timezone)

        if end_local < start_local:
            raise ValueError("End time cannot be before start time")

        # Date
        if start_local.date() == end_local.date():
            date = start_local.strftime("%b %d, %Y")
        else:
            date = f"{start_local.strftime('%b %d')} – {end_local.strftime('%b %d, %Y')}"

        # Time
        start_time = start_local.strftime("%I:%M %p")
        end_time = end_local.strftime("%I:%M %p")

        time = start_time if start_local == end_local else f"{start_time} – {end_time}"

        return date, time
    
    def format_time_for_transcript(self,seconds: int) -> str:
        hrs = seconds // 3600
        mins = (seconds % 3600) // 60
        secs = seconds % 60
        
        if hrs > 0:
            return f"{hrs:02}:{mins:02}:{secs:02}"
        
        return f"{mins:02}:{secs:02}"
    
    def convert_date_to_str(self, dt: datetime, timezone: str = "Asia/Kolkata") -> str:
        local_dt = self.to_timezone(dt, timezone)
        return local_dt.strftime("%d %B %Y")
    
    
time_helper = TimeHelper()