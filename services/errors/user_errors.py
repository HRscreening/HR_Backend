from services.errors.base import DomainError


class OrganizationAlreadyExists(DomainError):
    code = "ORGANIZATION_ALREADY_EXISTS"
    message = "Organization already exists"
    status_code = 409
    
class JobCreationFailed(DomainError):
    code = "JOB_CREATION_FAILED"
    message = "Failed to create job"
    status_code = 500


class JDExtractionFailed(DomainError):
    code = "JD_EXTRACTION_FAILED"
    message = "Failed to extract job description"
    status_code = 500
    
class JobNotFound(DomainError):
    code = "JOB_NOT_FOUND"
    message = "Job not found"
    status_code = 404
    
class RubricNotFound(DomainError):
    code = "RUBRIC_NOT_FOUND"
    message = "Rubric not found for the job"
    status_code = 404