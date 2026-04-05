import asyncio
import resend
from typing import List, Optional
from pydantic import EmailStr
from configs.env_config import SENDER_EMAIL, RESEND_API_KEY
from src.services.errors.base import DomainError
from configs.log_config import get_logger
from abc import ABC, abstractmethod

# Configure Resend
resend.api_key = RESEND_API_KEY

class EmailTemplate(ABC):

    @abstractmethod
    def get_subject(self) -> str:
        pass

    @abstractmethod
    def get_body(self) -> str:
        pass

    @abstractmethod
    def get_recipient(self) -> str:
        pass


class BaseEmailService:
    def __init__(self):
        self.logger = get_logger("BaseEmailService")
        self.sender_email = SENDER_EMAIL

    async def send_email(
        self,
        receiver_email: EmailStr,
        subject: str,
        body: str,
        content_type: str = "html",
        attachments: Optional[List[str]] = None, # file paths for attachments
    ) -> None:
        try:
            params = {
                "from": self.sender_email,
                "to": [receiver_email],
                "subject": subject,
                "html": body if content_type == "html" else None,
                "text": body if content_type == "text" else None,
            }
            
            if attachments:
                # Resend expects attachments as a list of dicts with content or path
                # For simplicity, we'll assume they are paths and let resend handle it if possible
                # or we might need to read them. Resend docs say:
                # attachments=[{"filename": "invoice.pdf", "path": "https://..."}] or content
                # Since these are local paths, we should read them.
                resend_attachments = []
                for path in attachments:
                    import os
                    filename = os.path.basename(path)
                    with open(path, "rb") as f:
                        content = list(f.read()) # Resend python lib expects list of bytes or similar? 
                        # Actually Resend's python sdk expects a dict.
                        # Referencing Resend docs: r.Emails.send({"from":..., "attachments": [{"filename": "...", "content": bytes}]})
                        resend_attachments.append({
                            "filename": filename,
                            "content": content
                        })
                params["attachments"] = resend_attachments

            await asyncio.to_thread(resend.Emails.send, params)

        except Exception as e:
            self.logger.error(f"Resend Error: {str(e)}")
            raise DomainError(f"Email sending failed: {str(e)}")
        
    
    async def send_email_template(self, template: EmailTemplate) -> None:
        try:
            self.logger.info(f"Sending email to {template.get_recipient()} with subject '{template.get_subject()}'")
            await self.send_email(
                receiver_email=template.get_recipient(),
                subject=template.get_subject(),
                body=template.get_body(),
            )
        except Exception as e:
            self.logger.error(f"Failed to send email to {template.get_recipient()}: {str(e)}")
