import jwt
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime, timedelta
from configs.env_config import SECRET_KEY, ALGORITHM, EXPIRATION_MINUTES
from src.services.errors.base import DomainError

class JWTService:
    def __init__(
        self,
        secret_key: str = SECRET_KEY,
        algorithm: str = ALGORITHM,
        expiration_minutes: int = EXPIRATION_MINUTES,
    ):
        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expiration_minutes = expiration_minutes

    def create_token(self, user_id: int, role: str) -> str:
        payload = {
            "user_id": user_id,
            "role": role,
            "iat": datetime.utcnow(),
            "exp": datetime.utcnow() + timedelta(minutes=self.expiration_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> dict | None:
        try:
            decoded = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return decoded
        except jwt.ExpiredSignatureError:
            return None
        except jwt.InvalidTokenError:
            return None

    
    async def verify_token(self,token: str):
        pass
        # if not token:
        #     raise DomainError("Missing or invalid token",401)
        
        # payload = self.decode_jwt(token)

        # if not payload or "user_id" not in payload:
        #     raise 
        
        

        # user = await db["users"].find_one({"_id": ObjectId(payload["user_id"])})

        # if not user:
        #     raise HTTPException(status_code=404, detail="User not found")

        # # print(f"Authenticated user: {user}")
        
        # return user
