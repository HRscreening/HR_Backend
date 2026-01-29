from pydantic import BaseModel, EmailStr, Field, field_validator

class NewUserSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(max_length=100)

    # @field_validator("password")
    # @classmethod
    # def strong_password(cls, value: str) -> str:
    #     if value.islower():
    #         raise ValueError("Password must contain uppercase letters")
    #     return value


class OtpVerification(BaseModel):
    email: EmailStr
    otp: str = Field(min_length=6, max_length=6)
    
    @field_validator("otp")
    @classmethod
    def otp_must_be_digits(cls, value: str) -> str:
        if not value.isdigit():
            raise ValueError("OTP must contain only digits")
        return value
    
class UserLogin(BaseModel):
    email: EmailStr
    password: str
    
    @field_validator("password")
    @classmethod
    def password_not_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("Password cannot be empty")
        return value