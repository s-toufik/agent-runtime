from enum import StrEnum


class MessageStreamType(StrEnum):
    TOKEN = "token"
    STATUS = "status"
    PROGRESS = "progress"
    FINAL = "final"
    ERROR = "error"
    COMPLETE = "complete"
