from src.models import Score
from sqlalchemy.ext.asyncio import AsyncSession
from src.schemas.score_schemas import ScoreRecordSchema


class ScoreRepository:
    def __init__(self, db: AsyncSession):
        self.db = db
    
    async def add_score(self,application_id, score:ScoreRecordSchema,rubric_id:str,threshold_score:int,criteria:dict,model_name:str = "Gemini-2.5-Flash-lite",scored_by:str = "AI") -> Score:
        score = Score(
                        application_id=application_id,
                        rubric_id=rubric_id,
                        overall_score=score.overall_score,
                        ai_confidence=score.ai_confidence,
                        breakdown=score.breakdown.model_dump(),
                        grounding_data={},  #TODO: To be removed in future, not needed as of now b'coz breakdown have  this already
                        scored_by=scored_by,
                        threshold_score=threshold_score,
                        criteria=criteria,
                        ai_model = model_name
                    )
        self.db.add(score)
        await self.db.flush() 
        return score