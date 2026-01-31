from typing import Optional,Literal
from uuid import UUID

class RequestContext:
    def __init__(
        self,
        type: Literal["personal", "org"],
        org_id: Optional[UUID] = None,
        role: Optional[str] = None,
    ):
        self.type = type
        self.org_id = org_id
        self.role = role
