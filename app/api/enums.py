import enum


class GrantType(enum.StrEnum):
    PASSWORD = "PASSWORD"
    REFRESH_TOKEN = "REFRESH_TOKEN"


class TaskType(enum.Enum):
    JOIN_CHAT = "Join chat"
    EXPORT_CHAT_MEMBERS = "Export chat members"
    TERMLY_READ_MESSAGES = "Termly read messages"
    READ_MESSAGE = "Read message"
    REACT_MESSAGE = "React message"
    COMMENT_MESSAGE = "Comment message"


class TaskStatus(enum.Enum):
    CREATED = "Created"
    PENDING = "Pending"
    PAUSING = "Pausing"
    NOT_COMPLETED = "Not completed"
    ILLEGAL = "Illegal"
    INVALID = "Invalid"
    COMPLETED = "Completed"
