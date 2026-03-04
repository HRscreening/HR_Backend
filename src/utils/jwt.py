import jwt
from fastapi import HTTPException
from bson import ObjectId
from datetime import datetime, timedelta,timezone
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
            print(f"Secret: {self.secret_key}, Algorithm: {self.algorithm}")
            decoded = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
            )
            return decoded
        except jwt.ExpiredSignatureError:
            raise DomainError(
                "Token has expired. Please log in again.",
                status_code=401
            )
        except jwt.InvalidTokenError:
            raise DomainError(
                "Invalid token. Please log in again.",
                status_code=401
            )
        except Exception as e:
            raise DomainError(
                f"Token decoding failed: {str(e)}",
                status_code=401
            )

    
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

    
    def create_panelist_availability_token(
    self,
        panelist_email: str,
        interview_id: str,
        expiration_minutes: int,
        round_config_id: str,
    ) -> str:

        now = datetime.now(timezone.utc)

        payload = {
            "panelist_email": panelist_email,
            "round_config_id": round_config_id,
            "interview_id": interview_id,
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
        }

        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    
    def create_candidate_booking_token(
    self,
    interview_id: str,
        candidate_email: str,
        expiration_minutes: int,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "interview_id": interview_id,
            "candidate_email": candidate_email,
            "token_type": "candidate_booking",
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_candidate_reschedule_token(
        self,
        interview_id: str,
        candidate_email: str,
        expiration_minutes: int,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "interview_id": interview_id,
            "candidate_email": candidate_email,
            "token_type": "candidate_reschedule",
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def create_panelist_feedback_token(
        self,
        panelist_email: str,
        interview_id: str,
        expiration_minutes: int,
    ) -> str:
        now = datetime.now(timezone.utc)
        payload = {
            "panelist_email": panelist_email,
            "interview_id": interview_id,
            "token_type": "panelist_feedback",
            "iat": now,
            "exp": now + timedelta(minutes=expiration_minutes),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)
    
    
    def encode_oauth_state(self,payload: dict):
        return jwt.encode(payload, self.secret_key,)

    def decode_oauth_state(self,state: str):
        return jwt.decode(state, self.secret_key, algorithms=self.algorithm)

    
jwt_service = JWTService()