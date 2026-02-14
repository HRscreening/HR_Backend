import smtplib
from email.mime.text import MIMEText
from configs.env_config import SENDER_EMAIL, SENDER_MAIL_PASSWORD
from src.services.errors.base import DomainError 

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

    def send_otp_email(self, receiver_email: str, otp: int) -> None:
        subject = "Your OTP Code"
        body = f"Your OTP for signup is {otp}. It is valid for 5 minutes."

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self.sender_email
        msg["To"] = receiver_email

        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.sendmail(
                    self.sender_email,
                    receiver_email,
                    msg.as_string(),
                )
        except Exception as e:
            raise DomainError("Failed to send OTP email",500) from e


emailService = EmailService()