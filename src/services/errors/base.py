from fastapi import status

class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = status.HTTP_400_BAD_REQUEST
    message = "Domain error"

    def __init__(self, message: str | None = None, status_code: int = 400):
        if message is not None:
            self.message = message
            self.status_code = status_code
        super().__init__(self.message)

class EmailAlreadyExists(DomainError):
    pass

class WeakPassword(DomainError):
    pass
