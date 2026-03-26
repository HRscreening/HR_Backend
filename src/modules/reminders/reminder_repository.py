from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update, delete
from sqlalchemy.orm import selectinload,  aliased


from typing import Optional, List

from src.modules.reminders.model.reminder_model import Reminder 
from src.modules.reminders.model.reminder_enum import ReminderType, ReminderStatus,RecipientType,EntityType 
from configs.log_config import get_logger
from src.modules.reminders.reminder_dtos import CreateReminderDTO
class ReminderRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("Reminder_Repository")
        
    async def create_reminders(
        self, reminders: List[CreateReminderDTO]
    ) -> List[Reminder]:

        reminder_objs = [
            Reminder(
                entity_id=dto.entity_id,
                entity_type=dto.entity_type,
                recipient_id=dto.recipient_id,
                recipient_type=dto.recipient_type,
                reminder_type=dto.reminder_type,
                next_run_at=dto.next_run_at,
                worker_job_id=dto.worker_job_id,
                payload=dto.payload,
                status=ReminderStatus.PENDING
            )
            for dto in reminders
        ]

        self.db.add_all(reminder_objs)
        await self.db.flush()  # Flush to get IDs assigned by the database

        return reminder_objs
    
    async def change_reminder_status(self, reminder_id: UUID, new_status: ReminderStatus) -> Optional[Reminder]:
        result = await self.db.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status=new_status)
            .returning(Reminder)
        )
        updated_reminder = result.fetchone()
        if updated_reminder:
            return updated_reminder[0]
        return None
    
    async def get_reminder_by_id(self, reminder_id: UUID) -> Optional[Reminder]:
        result = await self.db.execute(
            select(Reminder).where(Reminder.id == reminder_id)
        )
        reminder = result.scalar_one_or_none()
        return reminder
    
    async def get_reminder_by_worker_job_id(self, worker_job_id: str) -> Optional[Reminder]:
        result = await self.db.execute(
            select(Reminder).where(Reminder.worker_job_id == worker_job_id)
        )
        reminder = result.scalar_one_or_none()
        return reminder
    
    async def mark_reminder_as_failed(self, reminder_id: UUID, error_message: str) -> Optional[Reminder]:
        result = await self.db.execute(
            update(Reminder)
            .where(Reminder.id == reminder_id)
            .values(status=ReminderStatus.FAILED) # TODO: add error_message column to store the failure reason
            .returning(Reminder)
        )
        updated_reminder = result.fetchone()
        if updated_reminder:
            return updated_reminder[0]
        return None
    
    
    async def get_all_reminders_by_recipient_id_and_type(self, recipient_id: str, recipient_type: RecipientType,status:ReminderStatus | None = None,reminder_type:ReminderType | None = None) -> List[Reminder]:
        
        stmt = select(Reminder).where(
                Reminder.recipient_id == recipient_id,
                Reminder.recipient_type == recipient_type
            ).order_by(Reminder.next_run_at.asc())
        
        if status:
            stmt = stmt.where(Reminder.status == status)
            
        if reminder_type:
            stmt = stmt.where(Reminder.reminder_type == reminder_type)
        
        result = await self.db.execute(stmt)
        reminders = result.scalars().all()
        return reminders
    
    async def get_all_reminders_by_entity_id_and_type(self, entity_id: str, entity_type: EntityType,status:ReminderStatus | None = None,reminder_type:ReminderType | None = None,recipent_type:RecipientType | None = None) -> List[Reminder]:
        
        stmt = select(Reminder).where(
                Reminder.entity_id == entity_id,
                Reminder.entity_type == entity_type
            ).order_by(Reminder.next_run_at.asc())
        
        if status:
            stmt = stmt.where(Reminder.status == status)
            
        if reminder_type:
            stmt = stmt.where(Reminder.reminder_type == reminder_type)
            
        if recipent_type:
            stmt = stmt.where(Reminder.recipient_type == recipent_type)
    
        
        result = await self.db.execute(stmt)
        reminders = result.scalars().all()
        return reminders
    
    async def delete_reminder_by_id(self, reminder_id: UUID) -> bool:
        result = await self.db.execute(
            delete(Reminder).where(Reminder.id == reminder_id)
        )
        await self.db.commit()
        return result.rowcount > 0
    
    async def change_reminder_status_multi(
        self,
        reminder_ids: List[UUID | str],
        new_status: ReminderStatus
    ) -> List[Reminder]:

        if not reminder_ids:
            return []

        result = await self.db.execute(
            update(Reminder)
            .where(Reminder.id.in_(reminder_ids))  
            .values(status=new_status)
            .returning(Reminder)
        )

        updated_reminders = result.fetchall()

        return [row[0] for row in updated_reminders] if updated_reminders else []
