from src.modules.notifications.channels.email.base import BaseEmailService
from src.services.errors.base import DomainError


class EmailService(BaseEmailService):
    def __init__(self):
        super().__init__()

    async def send_otp_email(self, receiver_email: str, otp: str | int) -> None:
        """Send OTP email asynchronously using Resend."""
        otp_str = str(otp)
        subject = "Your OTP Code"
        body = f"Your OTP for signup is {otp_str}. It is valid for 5 minutes."
        
        try:
            await self.send_email(
                receiver_email=receiver_email,
                subject=subject,
                body=body,
                content_type="text"
            )
        except Exception as e:
            self.logger.error(f"Failed to send OTP email: {str(e)}")
            raise DomainError("Failed to send OTP email", 500) from e


