"""
Error classes for the rubric generation pipeline.
Each maps to a specific failure mode so the route handler can return
an appropriate HTTP status code and error message.
"""

from src.services.errors.base import DomainError


class RubricGenerationTimeout(DomainError):
    code = "RUBRIC_GENERATION_TIMEOUT"
    message = "AI rubric generation timed out. Please try again."
    status_code = 504


class RubricGenerationFailed(DomainError):
    code = "RUBRIC_GENERATION_FAILED"
    message = "AI failed to generate a valid rubric after multiple attempts."
    status_code = 502


class JDTooShort(DomainError):
    code = "JD_TOO_SHORT"
    message = "The extracted job description is too short to generate a meaningful rubric."
    status_code = 400


class JDNotReadable(DomainError):
    code = "JD_NOT_READABLE"
    message = "Could not extract readable text from the uploaded file."
    status_code = 400


class RubricValidationFailed(DomainError):
    code = "RUBRIC_VALIDATION_FAILED"
    message = "The generated rubric failed validation checks."
    status_code = 422


class RubricVersionConflict(DomainError):
    code = "RUBRIC_VERSION_CONFLICT"
    message = "A rubric update conflict occurred. Please refresh and try again."
    status_code = 409
