from fastapi import APIRouter,HTTPException,Depends,Request,Query,status
from fastapi.responses import JSONResponse
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from middlewares.verify_user import auth_required
from utils.verify_token import verify_token

from schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin
from services import auth_services
# from services.errors.auth_errors import EmailAlreadyExists


router = APIRouter(prefix="/api/auth", tags=["Authentication"])



@router.post("/signup")
async def create_user(user_data: NewUserSchema, db: AsyncSession = Depends(get_db)):

        print("Received user data for signup:", user_data)
        result = await auth_services.signup_user(user_data, db)
        
        return JSONResponse(
            content=result,
            status_code=status.HTTP_200_OK
        )



@router.post("/verify-otp")
async def check_otp(otp_data: OtpVerification, db: AsyncSession = Depends(get_db)):
    
    token =  await auth_services.verify_otp(otp_data, db)
    
    return JSONResponse(
        content={
            "message": "Email verified successfully",
            "access_token": token,
        },
        status_code=status.HTTP_200_OK
        )



@router.post("/login")
async def userLogin(user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    
    token =  await auth_services.login_user(user_data, db)
    
    return JSONResponse(
        content={
            "message": "Login successful",
            "access_token": token,
        },
        status_code=status.HTTP_200_OK
        )
