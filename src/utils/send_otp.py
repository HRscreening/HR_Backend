import smtplib
from email.mime.text import MIMEText
from configs.env_config import SENDER_EMAIL, SENDER_MAIL_PASSWORD


async def send_otp_email(receiver_email: str, otp: int) -> int:
    """Send OTP to the given email and return the generated OTP."""
    
    
    print(SENDER_EMAIL, SENDER_MAIL_PASSWORD)
    # Email Content
    subject = "Your OTP Code"
    body = f"Your OTP for signup is {otp}. It is valid for 5 minutes."

    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = receiver_email

    # Send Email
    try:
        with smtplib.SMTP("smtp.gmail.com", 587) as server:
            server.starttls()
            server.login(SENDER_EMAIL, SENDER_MAIL_PASSWORD)
            server.sendmail(SENDER_EMAIL, receiver_email, msg.as_string())
        print(f"OTP {otp} sent to {receiver_email}")
        return otp
    except Exception as e:
        print(f"Error sending OTP: {e}")
        raise ValueError("Failed to send OTP email")
        # return -1
