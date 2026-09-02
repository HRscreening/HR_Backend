from workers_async.producers.email_tasks_producer import EmailProducer
from workers_async.producers.notification_producer import NotificationProducer
from workers_async.producers.assessment_task_producer import AssessmentTaskProducer
from src.dtos.async_producers_dtos import Async_Producer_Keys


class AsyncProducerFactory:
    def __init__(
        self,
        Email_Producer: EmailProducer,
        Notification_Producer: NotificationProducer,
        AssessmentTask_Producer: AssessmentTaskProducer,
    ):
        self.PRODUCER_MAP = {
            Async_Producer_Keys.EMAIL_PRODUCER: Email_Producer,
            Async_Producer_Keys.NOTIFICATION_PRODUCER: Notification_Producer,
            Async_Producer_Keys.ASSESSMENT_TASK_PRODUCER: AssessmentTask_Producer
        }
        
    def get_producer(self, producer_type: Async_Producer_Keys):
        producer_instance = self.PRODUCER_MAP.get(producer_type)
        if not producer_instance:
            raise ValueError(f"Unknown producer type: {producer_type}")
        return producer_instance
            

