from fastapi import APIRouter,HTTPException,Depends,Request,Query,status
from configs.postgress_db import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from middlewares.verify_user import auth_required
from utils.verify_token import verify_token

from schemas.auth_schemas import NewUserSchema
from services import auth_services
from services.errors.auth_errors import EmailAlreadyExists


router = APIRouter(prefix="/api/auth", tags=["Authentication"])



@router.post("/signup")
async def create_user(user_data: NewUserSchema, db: AsyncSession = Depends(get_db)):
    try:
        print("Received user data for signup:", user_data)
        return await auth_services.signup_user(user_data, db)
    
    except EmailAlreadyExists as e:
        raise HTTPException(status_code=409, detail=str(e))
    
    except Exception as e:
        print(f"Error during user signup: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal Server Error")
        


# @router.post("/verify-otp")
# async def check_otp(otp_data: OtpVerification, db: AsyncIOMotorDatabase = Depends(get_database)):
#     try:
#         print("Received OTP verification data:", otp_data)
#         return await verify_otp(otp_data, db)
#     except Exception as e:
#         print(f"Error during OTP verification: {e}")
#         raise HTTPException(status_code=500, detail=str(e))



# @router.post("/login")
# async def userLogin(user_data: UserLogin, db: AsyncIOMotorDatabase = Depends(get_database)):
#     try:
#         return await login_user(user_data, db)
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=str(e))
    
