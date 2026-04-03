from enum import Enum

class UserType(str, Enum):
    CANDIDATE = "candidate"
    PANELIST = "panelist"
    