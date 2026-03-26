import asyncio
import smtplib
from email.mime.text import MIMEText
from pydantic import EmailStr
from configs.env_config import SENDER_EMAIL, SENDER_MAIL_PASSWORD
from src.services.errors.base import DomainError
from fastapi_mail import FastMail, MessageSchema, ConnectionConfig

class BaseEmailService:
    def __init__(
        self,
        sender_email: EmailStr = SENDER_EMAIL,
        sender_password: str = SENDER_MAIL_PASSWORD,
        smtp_host: str = "smtp.gmail.com",
        smtp_port: int = 587,
    ):
        self.sender_email = sender_email
        self.sender_password = sender_password
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port

    def _send_email_sync(
        self,
        receiver_email: EmailStr,
        subject: str,
        body: str,
        content_type: str = "html",
    ) -> None:
        """Blocking SMTP send (runs in thread)."""

        try:
            msg = MIMEText(body, content_type, "utf-8")
            msg["Subject"] = subject
            msg["From"] = self.sender_email
            msg["To"] = receiver_email

            with smtplib.SMTP(self.smtp_host, self.smtp_port, timeout=30) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    receiver_email,
                    msg.as_string(),
                )

        except smtplib.SMTPException as e:
            raise DomainError(f"Email sending failed: {str(e)}")

    async def send_email(
        self,
        receiver_email: EmailStr,
        subject: str,
        body: str,
    ) -> None:
        """Async wrapper (non-blocking)."""

        await asyncio.to_thread(
            self._send_email_sync,
            receiver_email,
            subject,
            body,
        )