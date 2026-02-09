from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from src.utils.security import hash_password,verify_password

import random
from src.utils.send_otp import send_otp_email
from  configs.log_config import get_logger
from src.schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin

from src.services.errors.auth_errors import EmailAlreadyExists,OTPVerificationFailed,UserLoginFailed,UserNotFound,DomainError
from src.repositories.user_repository import UserRepository

from src.utils.jwt import JWTService



class AuthService:
    def __init__(self, auth_repository: UserRepository, db: AsyncSession):
        self.auth_repository = auth_repository
        self.db = db
        self.logger = get_logger("AUTH_SERVICE")
        self.jwt_service = JWTService()

    @staticmethod
    def generate_otp() -> str:
        return str(random.randint(100000, 999999))

    async def signup_user(self, user_data: NewUserSchema):
        try:
            # 1️⃣ Check existing user
            existing_user = await self.auth_repository.get_user_by_email(
                user_data.email
            )

            if existing_user and existing_user.email_verified:
                raise EmailAlreadyExists("Email already exists")

            # 2️⃣ Prepare data
            hashed_password = hash_password(user_data.password)
            otp = self.generate_otp()

            # 3️⃣ Update unverified user
            if existing_user and not existing_user.email_verified:
                await self.auth_repository.update_user_passwd_otp(
                    existing_user,
                    hashed_password,
                    otp
                )

                await self.db.commit()
                await send_otp_email(existing_user.email, otp)

                return {"message": "OTP sent to your email"}

            # 4️⃣ Create new user
            new_user = await self.auth_repository.create_user(
                user_data,
                hashed_password,
                otp
            )

            await self.db.commit()
            await self.db.refresh(new_user)

            await send_otp_email(new_user.email, otp)

            return {"message": "OTP sent to your email"}

        except Exception as e:
            await self.db.rollback()
            self.logger.exception("Signup failed")
            raise
    
    async def verify_otp(self, otp_data: OtpVerification):
        try:
            user = await self.auth_repository.get_user_by_email(otp_data.email)

            if not user:
                raise UserNotFound("User not found", 404)

            if not user.otp:
                raise OTPVerificationFailed("OTP expired or used", 400)

            if user.otp != otp_data.otp:
                raise OTPVerificationFailed("Invalid OTP", 400)

            token = self.jwt_service.create_token(
                user_id=str(user.id),
                role=user.role.value
            )

            await self.auth_repository.verify_user_otp(user,otp_data.otp)
            await self.db.commit()
            await self.db.refresh(user)

            return token

        except Exception as e:
            await self.db.rollback()
            self.logger.exception(f"OTP verification failed , {e}")
            raise
        
    async def login_user(self, user_data: UserLogin):
        try:
            user = await self.auth_repository.get_user_by_email(user_data.email)

            if not user:
                raise UserNotFound("User Not Found", status_code=status.HTTP_404_NOT_FOUND)

            if not verify_password(user_data.password, user.password):
                raise UserLoginFailed("Invalid Credentials", status_code=status.HTTP_401_UNAUTHORIZED)

            token = self.jwt_service.create_token(
                user_id=str(user.id),
                role=user.role.value
            )

            if not token:
                raise UserLoginFailed("Failed to generate JWT token")

            return token

        except Exception as e:
            self.logger.exception(f"Login failed , {e}")
            raise