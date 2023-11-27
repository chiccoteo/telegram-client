from pydantic import BaseModel
from datetime import datetime


class TokenRequest(BaseModel):
    grant_type: str | None
    username: str | None
    password: str | None
    refresh_token: str | None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    expires_in: int
    sign_up: bool = False


class TokenDetails(BaseModel):
    username: str
    user_id: int
    token_type: str


class UserDto(BaseModel):
    id: int
    username: str
    first_name: str | None
    last_name: str | None


class ClientRegistrationForm(BaseModel):
    phone_number: str


class ConfirmationCodeForm(BaseModel):
    phone_number: str
    sent_code: str


class CheckTwoStepPasswordForm(BaseModel):
    phone_number: str
    two_step_password: str


class ClientDto(BaseModel):
    username: str | None
    phone_number: str
    chat_id: str | None


class TaskForm(BaseModel):
    chat_id: str
    message_id: str | None
    reaction: str | None
    exported_chat_id: str | None
    task_type: str
    count: int | None
    interval: int = 3
    term_days: int | None
    parent_task_id: int | None


class TaskUpdateForm(BaseModel):
    count: int | None
    status: str | None


class TasksDtoRequest(BaseModel):
    task_type: list[str]
    task_status: list[str]
    start_date: datetime | None
    end_date: datetime | None


class TaskDto(BaseModel):
    id: int
    chat_id: str
    message_id: str | None
    reaction: str | None
    exported_chat_id: str | None
    task_type: str
    status: str
    count: int | None
    interval: int = 3
    term_days: int | None
    parent_task_id: int | None
    done_count: int = 0
    failed_count: int = 0


class ClientTaskDto(BaseModel):
    id: int
    client_id: int
    task_id: int
    success: bool
    date: datetime


class ClientReport(BaseModel):
    client_id: int
    count_succeed_tasks: int
    count_failed_tasks: int
