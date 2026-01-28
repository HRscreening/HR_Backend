from pydantic import BaseModel, EmailStr, Field, field_validator

class NewUserSchema(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    name: str = Field(max_length=100)

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        if value.islower():
            raise ValueError("Password must contain uppercase letters")
        return value
