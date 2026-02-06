from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from src.models.user_model import User
from src.utils.security import hash_password,verify_password
from src.utils.jwt import create_jwt
from src.utils.security import hash_password
import random
from src.utils.send_otp import send_otp_email
from  configs.log_config import get_logger
from src.schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin
from src.services.errors.auth_errors import EmailAlreadyExists,OTPVerificationFailed,UserLoginFailed,UserNotFound,DomainError


from sqlalchemy import select


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


logger = get_logger("AUTH_SERVICE")


async def signup_user(user_data :NewUserSchema , db: AsyncSession):
    
    try:
        # 1️⃣ Check if user already exists
        result = await db.execute(
            select(User).where(User.email == user_data.email)
        )
        existing_user = result.scalar_one_or_none()

        # 2️⃣ If verified user exists → error
        if existing_user and existing_user.email_verified:
            raise EmailAlreadyExists("Email already exists")

        # 3️⃣ Generate OTP & hash password
        hashed_password = hash_password(user_data.password)
        otp = generate_otp()

        # 4️⃣ If user exists but not verified → update
        if existing_user and not existing_user.email_verified:
            existing_user.password = hashed_password
            existing_user.otp = otp

            await send_otp_email(existing_user.email, otp)

            await db.commit()
            return {"message": "OTP sent to your email"}

        # 5️⃣ Create new user
        new_user = User(
            email=user_data.email,
            name=user_data.name,
            password=hashed_password,
            email_verified=False,
            otp=otp,
        )

        db.add(new_user)
        await send_otp_email(new_user.email, otp)

        await db.commit()
        await db.refresh(new_user)

        return {"message": "OTP sent to your email"}

    except Exception:
        await db.rollback()
        raise


async def verify_otp(otp_data: OtpVerification, db: AsyncSession):
    try:
        result = await db.execute(
            select(User).where(User.email == otp_data.email)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise UserNotFound("User not found", 404)

        if not user.otp:
            raise OTPVerificationFailed("OTP expired or used", 400)

        if user.otp != otp_data.otp:
            raise OTPVerificationFailed("Invalid OTP", 400)

        # # Generate JWT Token
        # role = user.role
        # if isinstance(role, str):
        #     role_value = role
        # elif hasattr(role, "value"):
        #     role_value = role.value
        # else:
        #     role_value = str(role)

        token = create_jwt(
            user_id=str(user.id),
            role=user.role.value
        )
        
        user.email_verified = True
        user.otp = None

        await db.commit()
        await db.refresh(user)

        return token

    except Exception:
        await db.rollback()
        raise



async def login_user(user_data: UserLogin, db: AsyncSession):
    result = await db.execute(
        select(User).where(User.email == user_data.email)
        )
    
    user = result.scalar_one_or_none()
    
    if not user:
        raise UserNotFound("User Not Found", status_code=status.HTTP_404_NOT_FOUND)

    # Check password
    if not verify_password(user_data.password, user.password):
        raise UserLoginFailed("Invalid Credentials", status_code=status.HTTP_401_UNAUTHORIZED)

    # Generate JWT
    token = create_jwt(user_id=str(user.id), role=user.role.value)
    if not token:
        raise UserLoginFailed("Failed to generate JWT token")

    return token

   
