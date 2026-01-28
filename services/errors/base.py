class DomainError(Exception):
    code = "DOMAIN_ERROR"
    status_code = 400
    message = "Domain error"

    def __init__(self, message: str | None = None):
        if message is not None:
            self.message = message
        super().__init__(self.message)

class EmailAlreadyExists(DomainError):
    pass

class WeakPassword(DomainError):
    pass
