from app.api.enums import ErrorCode


class TelegramClientException(Exception):
    def __init__(self, name, code):
        self.name = name
        self.code = code

    def get_error_message(self):
        return {"code": self.code, "message": self.name}


class GeneralApiException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.GENERAL_API_EXCEPTION


class PasswordIncorrectException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.PASSWORD_INCORRECT_EXCEPTION


class CredentialsException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.CREDENTIALS_EXCEPTION


class RefreshTokenInvalidException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.REFRESH_TOKEN_INVALID_EXCEPTION


class PhoneNumberInvalidException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.PHONE_NUMBER_INVALID_EXCEPTION


class ClientAlreadyRegisteredException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.CLIENT_ALREADY_REGISTERED_EXCEPTION


class CodeIsSentException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.CODE_IS_SENT_EXCEPTION


class PhoneCodeExpiredException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.PHONE_CODE_EXPIRED_EXCEPTION


class PhoneCodeInvalidException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.PHONE_CODE_INVALID_EXCEPTION


class TwoStepPasswordNeededException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.TWO_STEP_PASSWORD_NEEDED_EXCEPTION


class TwoStepPasswordInvalidException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.TWO_STEP_PASSWORD_INVALID_EXCEPTION


class ClientNotFoundException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.CLIENT_NOT_FOUND_EXCEPTION


class TaskNotFoundException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.TASK_NOT_FOUND_EXCEPTION


class TaskCountTooManyException(TelegramClientException):
    def __init__(self, name):
        self.name = name
        self.code = ErrorCode.TASK_COUNT_TOO_MANY_EXCEPTION
