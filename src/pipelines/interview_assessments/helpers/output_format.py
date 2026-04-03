from pydantic import BaseModel
from typing import Literal,List

class CriteriaRating(BaseModel):
    criteria: str
    score: int
    reason: str
    
class ChunkAnalysisOutput(BaseModel):
    criteria_evaluation: List[CriteriaRating]
    skills_detected: List[str]
    strengths: List[str]
    weaknesses: List[str]
    overall_chunk_score: int
    summary: str


class CriteriaFeedback(BaseModel):
    criteria: str
    rating: int
    comment: str
    
class FinalFeedbackOutput(BaseModel):
    criteria_ratings : list[CriteriaFeedback]
    interview_summary: str
    final_recommendation: Literal ["Hire", "No Hire"]
    justification: str