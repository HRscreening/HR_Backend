from fastapi import Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from models.user_model import *
from utils.security import hash_password,verify_password
from utils.jwt import create_jwt
from utils.security import hash_password
import random
from utils.send_otp import send_otp_email
from  configs.log_config import get_logger
from schemas.auth_schemas import NewUserSchema
from services.errors.auth_errors import EmailAlreadyExists


from sqlalchemy import select


def generate_otp() -> str:
    return str(random.randint(100000, 999999))


logger = get_logger("AUTH_SERVICE")

async def signup_user(user_data, db: AsyncSession):
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

# async def verify_otp(otp_data: OtpVerification, db: AsyncSession):
#     try:
#         print("OTP verification data =", otp_data)
#         users_collection = db.get_collection("users")

#         # Find user with the given email and OTP
#         existing_user = await users_collection.find_one({
#             "email": otp_data.email,
#             "otp": otp_data.otp
#         })

#         if not existing_user:
#             return JSONResponse(
#                 content={"message": "Invalid OTP or user not found"},
#                 status_code=status.HTTP_400_BAD_REQUEST
#             )

#         # Update user to mark email as verified and remove OTP
#         update_result = await users_collection.update_one(
#             {"_id": existing_user["_id"]},
#             {"$set": {"email_verified": True}, "$unset": {"otp": ""}}
#         )

#         if update_result.modified_count == 0:
#             return JSONResponse(
#                 content={"message": "Failed to verify email"},
#                 status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#             )

#         # Generate JWT
#         token = create_jwt(user_id=str(existing_user["_id"]), role="user")
#         if not token:
#             raise Exception("Failed to generate JWT token")

#         return JSONResponse(
#             content={
#                 "message": "Email verified successfully",
#                 "access_token": token,
#                 "role": "user"
#             },
#             status_code=status.HTTP_200_OK
#         )

#     except Exception as e:
#         print(f"Error during OTP verification: {e}")
#         return JSONResponse(
#             content={"message": f"An error occurred: {str(e)}"},
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )


# async def login_user(user_data: UserLogin, db: AsyncIOMotorDatabase):
#     try:
#         users_collection = db.get_collection("users")

#         # Find user by email
#         user = await users_collection.find_one({"email": user_data.email, "email_verified": True})

#         if not user:
#             return JSONResponse(
#                 content={"message": "User not found.SignUp please"},
#                 status_code=status.HTTP_401_UNAUTHORIZED
#             )

#         # Check password
#         if not verify_password(user_data.password, user["password"]):
#             return JSONResponse(
#                 content={"message": "Invalid username or password"},
#                 status_code=status.HTTP_401_UNAUTHORIZED
#             )

#         # Generate JWT
#         token = create_jwt(user_id=str(user["_id"]), role="user")
#         if not token:
#             raise Exception("Failed to generate JWT token")

#         return JSONResponse(
#             content={"message": "Login successful", "access_token": token, "role": "user"},
#             status_code=status.HTTP_200_OK
#         )

#     except Exception as e:
#         return JSONResponse(
#             content={"message": f"An error occurred: {str(e)}"},
#             status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
#         )
