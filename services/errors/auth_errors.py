from services.errors.base import DomainError

class EmailAlreadyExists(DomainError):
    code = "EMAIL_ALREADY_EXISTS"
    message = "Email already exists"
    status_code = 409


class InvalidCredentials(DomainError):
    code = "INVALID_CREDENTIALS"
    message = "Invalid credentials"
    status_code = 401
    
class OTPVerificationFailed(DomainError):
    code = "OTP_VERIFICATION_FAILED"
    message = "OTP verification failed"
    status_code = 400
    
class UserNotFound(DomainError):
    code = "USER_NOT_FOUND"
    message = "User not found"
    status_code = 404
    
    
class UserLoginFailed(DomainError):
    code = "USER_LOGIN_FAILED"
    message = "User login failed"
    status_code = 401