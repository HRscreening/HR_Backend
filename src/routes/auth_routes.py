from fastapi import APIRouter,Depends,Request,Query,status
from fastapi.responses import JSONResponse

from src.schemas.auth_schemas import NewUserSchema,OtpVerification,UserLogin
from src.dependency import get_auth_service,AuthService



router = APIRouter(prefix="/api/auth", tags=["Authentication"])



@router.post("/signup",status_code=status.HTTP_201_CREATED)
async def create_user(user_data: NewUserSchema, auth_service: AuthService = Depends(get_auth_service)):

        print("Received user data for signup:", user_data)
        result = await auth_service.signup_user(user_data)
        
        return {
            "status": "success",
            "message": result["message"]
        }



@router.post("/verify-otp")
async def check_otp(otp_data: OtpVerification,auth_service: AuthService = Depends(get_auth_service)):
    
    token =  await auth_service.verify_otp(otp_data)
    
    return JSONResponse(
        content={
            "message": "Email verified successfully",
            "access_token": token,
        },
        status_code=status.HTTP_200_OK
        )



@router.post("/login")
async def userLogin(user_data: UserLogin,auth_service: AuthService = Depends(get_auth_service)):
    
    token =  await auth_service.login_user(user_data)
    
    return JSONResponse(
        content={
            "message": "Login successful",
            "access_token": token,
        },
        status_code=status.HTTP_200_OK
        )
