from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user_model import User
from src.utils.security import hash_password,verify_password
# from src.utils.jwt import create_jwt
from src.utils.security import hash_password
import random
from src.utils.send_otp import send_otp_email
from  configs.log_config import get_logger
from src.schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin
from src.services.errors.auth_errors import EmailAlreadyExists,OTPVerificationFailed,UserLoginFailed,UserNotFound,DomainError


from sqlalchemy import select






class UserRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.logger = get_logger("USER_REPOSITORY")

    async def get_user_by_email(self, email: str) -> User | None:
        result = await self.db.execute(
            select(User).where(User.email == email)
        )
        return result.scalar_one_or_none()

    async def create_user(
        self,
        user_data: NewUserSchema,
        hashed_password: str,
        otp: str
    ) -> User:
        user = User(
            email=user_data.email,
            name=user_data.name,
            password=hashed_password,
            email_verified=False,
            otp=otp,
        )
        self.db.add(user)
        return user

    async def update_user_password_and_otp(
        self,
        user: User,
        hashed_password: str,
        otp: str
    ) -> User:
        user.password = hashed_password
        user.otp = otp
        return user

    async def verify_user_otp(self, user: User, otp: str):
        if user.otp != otp:
            raise OTPVerificationFailed("Invalid OTP")

        user.email_verified = True
        user.otp = None
        return user        

    async def authenticate_user(self, email: str, password: str) -> User:
        user = await self.get_user_by_email(email)

        if not user:
            raise UserNotFound("User not found")

        if not user.email_verified:
            raise DomainError("Email not verified")

        if not verify_password(password, user.password):
            raise UserLoginFailed("Incorrect password")

        return user
    
    async def get_user_by_id(self, user_id: int) -> User | None:
        result = await self.db.execute(
            select(User).where(User.id == user_id)
        )
        return result.scalar_one_or_none()