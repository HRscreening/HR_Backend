from services.errors.base import DomainError

class EmailAlreadyExists(DomainError):
    code = "EMAIL_ALREADY_EXISTS"
    message = "Email already exists"
    status_code = 409


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid credentials"
    status_code = 401