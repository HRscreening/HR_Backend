from src.utils.jwt import JWTService
from datetime import datetime, timedelta, timezone
from abc import ABC, abstractmethod
from src.services.errors.base import DomainError
from pydantic import BaseModel

class BaseTokenManager(ABC):
    def __init__(self, jwt_service=None):
        self.jwt_service = jwt_service or JWTService()

    def _create_token(self, payload: dict, expiration_minutes: int):
        now = datetime.now(timezone.utc)
        payload.update({
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
        })
        return self.jwt_service.encode_token(payload)

    def _validate_token(self, token: str):
        return self.jwt_service.decode_token(token)


    @property
    @abstractmethod
    def dto_class(self) -> type[BaseModel]:
        """Each manager defines its DTO"""
        pass

    @abstractmethod
    def create_token(self, *args, **kwargs) -> str:
        pass

    def validate_token(self, token: str):
        payload = self._validate_token(token)

        # ✅ validate via DTO
        try:
            return self.dto_class.model_validate(payload)
        except Exception as e:
            raise DomainError(f"Invalid token payload: {str(e)}")