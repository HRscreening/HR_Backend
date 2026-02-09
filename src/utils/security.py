import hashlib
from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def hash_password(password: str) -> str:
    digest = hashlib.sha256(password.encode("utf-8")).hexdigest()
    return pwd_context.hash(digest)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    digest = hashlib.sha256(plain_password.encode("utf-8")).hexdigest()
    return pwd_context.verify(digest, hashed_password)



class PasswordService:
    def __init__(self):
        self._pwd_context = CryptContext(
            schemes=["bcrypt"],
            deprecated="auto"
        )

    def hash_password(self, password: str) -> str:
        """
        Hash a plain-text password using SHA-256 + bcrypt.
        """
        digest = self._sha256(password)
        return self._pwd_context.hash(digest)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """
        Verify a plain-text password against a stored hash.
        """
        digest = self._sha256(plain_password)
        return self._pwd_context.verify(digest, hashed_password)

    @staticmethod
    def _sha256(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()
