from pydantic import BaseModel, EmailStr,model_validator,field_validator


class CandidateInfoSchema(BaseModel):
    full_name: str
    email: EmailStr
    phone: str | None = None

    @model_validator(mode='after')
    def check_at_least_one_field(self):
        if not any([self.full_name, self.email, self.phone]):
            raise ValueError('At least one field must be provided')
        return self
    