import enum


class Role(str, enum.Enum):
    ADMIN = "ADMIN"
    ADVISOR = "ADVISOR"
    READ_ONLY = "READ_ONLY"