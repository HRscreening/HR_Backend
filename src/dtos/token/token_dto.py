from pydantic import BaseModel, EmailStr

class PanelistTokenDto(BaseModel):
    panelist_id: str
    round_config_id: str
    interview_id: str
    token_type: str

    
class CandidateTokenDto(BaseModel):
    interview_id: str
    candidate_email: EmailStr
    token_type: str
    