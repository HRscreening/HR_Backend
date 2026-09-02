# Can be used later for different types of notifications (email, sms, etc.)
from src.modules.notifications.channels.email.services import EmailFactory
from typing import Literal
from configs.log_config import get_logger
from src.dtos.notification_dto import RecipientType,NotificationChannel,Template_Keys



class NotificationService:
    """
    NotificationService is responsible for sending notifications to different recipient types (e.g., candidates, panelists) through various channels (e.g., email, SMS, in-app). It uses a factory pattern to retrieve the appropriate email service based on the recipient type and sends notifications using the specified template key.
    
    methods:
    - send_notification: Main method to send a notification based on recipient type, channel, payload
        and template key. It handles the logic for determining which service to use and how to send the notification.
    
    - _send_email_notification: Helper method to send email notifications using the appropriate email service and template.
    
    """
    
    def __init__(self,email_factory: EmailFactory):
        self.email_factory = email_factory
        self.logger = get_logger("Notification_Service")
                        
        
    async def send_notification(self, recipient_type: RecipientType,channel:NotificationChannel,payload:dict,template_key: Template_Keys ):
        """
        Sends a reminder notification to the specified recipient type.
        
        Args:
            recipient_type (RecipientType): The type of recipient (e.g., CANDIDATE, PANELIST).
            channel (Channel): The channel through which to send the notification (e.g., EMAIL, SMS, IN_APP).
            payload (dict): The data payload to be used in the notification template.
            template_key (Template_Keys): The key identifying which email template to use for the notification.
        Raises:
            ValueError: If an unknown channel is provided or if the email service for the recipient type is not implemented.
            Exception: For any other errors that occur during the notification sending process. 
        
        """
        try:
            match channel:
                case NotificationChannel.EMAIL:
                    self.logger.info(f"Sending email notification to {recipient_type} with payload: {payload} and template key: {template_key}")
                    await self._send_email_notification(recipient_type, payload, template_key)
                    
                    
                case NotificationChannel.SMS:
                    raise NotImplementedError("SMS channel is not implemented yet.")
            
                case NotificationChannel.IN_APP:
                    raise NotImplementedError("In-app channel is not implemented yet.")
            
                case NotificationChannel.ALL:
                    self.logger.info(f"Sending email notification to {recipient_type} with payload: {payload} and template key: {template_key}")
                    await self._send_email_notification(recipient_type, payload, template_key)
            
                case _:
                    raise ValueError(f"Unsupported channel: {channel}")
            
        except ValueError as e:
            self.logger.error(f"Failed to send reminder notification: {e}")
            raise e

        except Exception as e:
            self.logger.error(f"An error occurred while sending reminder notification: {e}")
            raise
            
            
            
            
    async def _send_email_notification(self, recipient_type: RecipientType, payload: dict,template_key: Template_Keys):
        """Sends an email notification to the specified recipient type.""" 
        try:
            email_service = self.email_factory.get_email_service(recipient_type)
            await email_service.send_email(template_key, payload)
        except Exception as e:
            self.logger.error(f"Failed to send email notification: {e}")
            raise e
            
    
   