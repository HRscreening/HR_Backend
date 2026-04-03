from src.modules.interviews.services.helpers.token_manager.base import BaseTokenManager
from src.dtos.token.token_dto import PanelistTokenDto
from src.dtos.token.token_dto import CandidateTokenDto
from src.enums.interview_token_facrory_enum import UserType
from src.utils.jwt import JWTService

class CandidateTokenManager(BaseTokenManager):
    dto_class = CandidateTokenDto

    def create_token(
        self,
        token_type: str,
        expiration_minutes: int,
        **kwargs
    ) -> str:

        payload = self.dto_class(
            token_type=token_type,
            **kwargs
        ).model_dump()

        return self._create_token(payload, expiration_minutes)

    def validate_token(self, token):
        payload = self._validate_token(token)
        return self.dto_class.model_validate(payload)
    

class PanelistTokenManager(BaseTokenManager):
    dto_class = PanelistTokenDto

    def create_token(
        self,
        token_type: str,
        expiration_minutes: int,
        **kwargs
    ) -> str:

        payload = self.dto_class(
            token_type=token_type,
            **kwargs
        ).model_dump()

        return self._create_token(payload, expiration_minutes)

    def validate_token(self, token):
        payload = self._validate_token(token)
        return self.dto_class.model_validate(payload)
    
  
class InterviewTokenManagerFactory:
    _registry = {
        UserType.CANDIDATE: CandidateTokenManager,
        UserType.PANELIST: PanelistTokenManager,
    }

    def __init__(self, jwt_service: JWTService):
        self.jwt_service = jwt_service

    def get_manager(self, user_type: UserType) -> BaseTokenManager:
        manager_cls = self._registry.get(user_type)

        if not manager_cls:
            raise ValueError(f"Invalid token manager type: {user_type}")

        return manager_cls(jwt_service=self.jwt_service)