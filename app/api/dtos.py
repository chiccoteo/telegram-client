from typing import Optional

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
    id: int
    username: str | None
    phone_number: str
    chat_id: str | None
    banned: bool


class TaskForm(BaseModel):
    chat_id: str
    message_id: str | None
    reaction: str | None
    exported_chat_id: str | None
    task_type: str
    count: str
    interval: str | None
    term_days: int | None
    parent_task_id: int | None


class TaskUpdateForm(BaseModel):
    count: str | None
    interval: str | None
    status: str | None


class TasksDtoRequest(BaseModel):
    task_type: list[str]
    task_status: list[str]
    start_date: datetime | None
    end_date: datetime | None


class TaskDto(BaseModel):
    id: int
    chat_id: str
    message_id: Optional[str] = None
    reaction: Optional[str] = None
    exported_chat_id: Optional[str] = None
    task_type: dict
    status: str
    count: int
    interval: Optional[int] = None
    term_days: Optional[int] = None
    parent_task_id: Optional[int] = None
    done_count: Optional[int] = None
    failed_count: Optional[int] = None


class BasePageResponse(BaseModel):
    items: list
    total: int = 0
    page: int
    size: int
    pages: int = 0


class ClientTaskDto(BaseModel):
    id: int
    client_phone_number: str
    client_chat_id: str
    task_id: int
    task_type: Optional[str] = None
    count: int
    success: bool
    reason: Optional[str] = None
    interval: Optional[int] = None
    task_data: list
    date: datetime


class ClientTaskDetails(BaseModel):
    success: bool = True
    reason: Optional[str] = None
    task_data: list = None
