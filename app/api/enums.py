import enum


class GrantType(enum.StrEnum):
    PASSWORD = "PASSWORD"
    REFRESH_TOKEN = "REFRESH_TOKEN"


class TaskType(enum.StrEnum):
    JOIN_CHAT = "Join chat"
    EXPORT_CHAT_MEMBERS = "Export chat members"
    TERMLY_READ_MESSAGES = "Termly read messages"
    READ_MESSAGE = "Read message"
    REACT_MESSAGE = "React message"
    COMMENT_MESSAGE = "Comment message"


class TaskStatus(enum.StrEnum):
    CREATED = "Created"
    PENDING = "Pending"
    PAUSING = "Pausing"
    NOT_COMPLETED = "Not completed"
    ILLEGAL = "Illegal"
    INVALID = "Invalid"
    COMPLETED = "Completed"


class ErrorCode(enum.IntEnum):
    GENERAL_API_EXCEPTION = 101
    PASSWORD_INCORRECT_EXCEPTION = 102
    CREDENTIALS_EXCEPTION = 103
    REFRESH_TOKEN_INVALID_EXCEPTION = 104
    PHONE_NUMBER_INVALID_EXCEPTION = 105
    CLIENT_ALREADY_REGISTERED_EXCEPTION = 106
    CODE_IS_SENT_EXCEPTION = 107
    PHONE_CODE_EXPIRED_EXCEPTION = 108
    PHONE_CODE_INVALID_EXCEPTION = 109
    TWO_STEP_PASSWORD_NEEDED_EXCEPTION = 110
    TWO_STEP_PASSWORD_INVALID_EXCEPTION = 111
    CLIENT_NOT_FOUND_EXCEPTION = 112
    TASK_NOT_FOUND_EXCEPTION = 113
    TASK_COUNT_TOO_MANY_EXCEPTION = 114
