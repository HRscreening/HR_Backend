from src.modules.email_services.base import BaseEmailService

async def send_otp_email(receiver_email: str, otp: int) -> int:
    """Send OTP to the given email using Resend."""
    
    email_service = BaseEmailService()
    subject = "Your OTP Code"
    body = f"Your OTP for signup is {otp}. It is valid for 5 minutes."

    try:
        await email_service.send_email(
            receiver_email=receiver_email,
            subject=subject,
            body=body,
            content_type="text"
        )
        print(f"OTP {otp} sent to {receiver_email}")
        return otp
    except Exception as e:
        print(f"Error sending OTP: {e}")
        raise ValueError("Failed to send OTP email")
