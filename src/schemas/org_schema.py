from pydantic import BaseModel, EmailStr, Field, field_validator
from typing import Dict, Optional, Any, List
from dataclasses import dataclass


class NewOrgSchema(BaseModel):
    name: str = Field(max_length=100)
    email: EmailStr
    address: str | None = None

