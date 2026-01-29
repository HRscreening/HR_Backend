from pydantic import BaseModel, EmailStr, Field, field_validator

class NewOrgSchema(BaseModel):
    name: str = Field(max_length=100)
    email: EmailStr
    address: str | None = None


class NewJobSchema(BaseModel):  
    title: str = Field(max_length=200)
    description: str | None = None
    location: str | None = None
    target_headcount: int
    
    voice_ai_enabled: bool = False
    manual_rounds_count: int = 0
    is_confidential: bool = False

    @field_validator('target_headcount')
    def validate_target_headcount(cls, value):
        if value <= 0:
            raise ValueError('target_headcount must be a positive integer')
        return value
    
from pydantic import BaseModel, field_validator
from typing import Dict, Any




class RubricSchema(BaseModel):
    threshold_score: int
    criteria: Dict[str, Dict[str, Any]]

    @field_validator("threshold_score")
    @classmethod
    def validate_threshold_score(cls, v):
        if v < 0:
            raise ValueError("threshold_score must be non-negative")
        return v

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, criteria):
        for skill, data in criteria.items():
            if "score" not in data:
                raise ValueError(f"{skill} must have a score")

            if data["score"] < 0:
                raise ValueError(f"{skill} score must be non-negative")

            sub = data.get("sub_criteria")
            if sub:
                if not isinstance(sub, dict):
                    raise ValueError(f"{skill}.sub_criteria must be a dict")

                for k, v in sub.items():
                    if v < 0:
                        raise ValueError(f"{skill}.{k} must be non-negative")

                # optional consistency check
                if sum(sub.values()) != data["score"]:
                    raise ValueError(
                        f"{skill} score must equal sum of sub_criteria"
                    )

        return criteria
