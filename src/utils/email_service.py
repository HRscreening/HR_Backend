import asyncio
import smtplib
from email.mime.text import MIMEText
from configs.env_config import SENDER_EMAIL, SENDER_MAIL_PASSWORD
from src.services.errors.base import DomainError


def _send_otp_sync(sender_email: str, sender_password: str, smtp_host: str, smtp_port: int, receiver_email: str, otp: str) -> None:
    """Blocking SMTP send (run in thread)."""
    body = f"Your OTP for signup is {otp}. It is valid for 5 minutes."
    msg = MIMEText(body)
    msg["Subject"] = "Your OTP Code"
    msg["From"] = sender_email
    msg["To"] = receiver_email
    with smtplib.SMTP(smtp_host, smtp_port) as server:
        server.starttls()
        server.login(sender_email, sender_password)
        server.sendmail(sender_email, receiver_email, msg.as_string())


class EmailService:
    def __init__(
        self,
        sender_email: str = SENDER_EMAIL,
        sender_password: str = SENDER_MAIL_PASSWORD,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
    ):
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    async def send_otp_email(self, receiver_email: str, otp: str | int) -> None:
        """Send OTP email asynchronously (blocking SMTP runs in thread pool)."""
        otp_str = str(otp)
        try:
            await asyncio.to_thread(
                _send_otp_sync,
                self.sender_email,
                self.sender_password,
                self.smtp_host,
                self.smtp_port,
                receiver_email,
                otp_str,
            )
        except Exception as e:
            raise DomainError("Failed to send OTP email", 500) from e


emailService = EmailService()