class GeneralApiException(Exception):
    def __init__(self, name: str):
        self.name = name


class PasswordIncorrectException(Exception):
    def __init__(self, name: str):
        self.name = name


class CredentialsException(Exception):
    def __init__(self, name: str):
        self.name = name


class RefreshTokenInvalidException(Exception):
    def __init__(self, name: str):
        self.name = name


class PhoneNumberInvalidException(Exception):
    def __init__(self, name: str):
        self.name = name


class ClientAlreadyRegisteredException(Exception):
    def __init__(self, name: str):
        self.name = name


class CodeIsSentException(Exception):
    def __init__(self, name: str):
        self.name = name


class PhoneCodeExpiredException(Exception):
    def __init__(self, name: str):
        self.name = name


class PhoneCodeInvalidException(Exception):
    def __init__(self, name: str):
        self.name = name


class TwoStepPasswordInvalidException(Exception):
    def __init__(self, name: str):
        self.name = name


class ClientNotFoundException(Exception):
    def __init__(self, name: str):
        self.name = name


class TaskNotFoundException(Exception):
    def __init__(self, name: str):
        self.name = name


class TaskCountTooManyException(Exception):
    def __init__(self, name: str):
        self.name = name
