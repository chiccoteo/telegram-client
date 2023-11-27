from fastapi import Depends
from fastapi_pagination import Page, Params, add_pagination
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Request
from fastapi.responses import JSONResponse

from consts import base_url
from dtos import *
from fastapi import FastAPI
from exceptions import *

import models as models
from database import engine, SessionLocal
from services import TgService, context_refresh_event
from utils import get_current_user

models.Base.metadata.create_all(bind=engine)

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
pageable_params = Annotated[Params, Depends()]
service = TgService()


@app.post(f"{base_url}auth")
async def authenticate(form: TokenRequest, db: db_dependency):
    return await service.authenticate(form, db)


@app.get(f"{base_url}me", response_model=UserDto, dependencies=[Depends(get_current_user)])
async def get_me(current_user: Annotated[models.User, Depends(get_current_user)]):
    return current_user


@app.post(f"{base_url}client/auth", dependencies=[Depends(get_current_user)])
async def register_client(form: ClientRegistrationForm, db: db_dependency):
    phone_number = await service.register_client(form, db)
    return {"data": phone_number, "message": "Confirmation code is sent"}


@app.post(f"{base_url}client/auth/confirmation-code", dependencies=[Depends(get_current_user)],
          response_model=ClientDto)
async def confirm_code(form: ConfirmationCodeForm, db: db_dependency):
    return await service.confirm_code(form, db)


@app.post(f"{base_url}client/auth/two-step-password", dependencies=[Depends(get_current_user)],
          response_model=ClientDto)
async def check_two_step_password(form: CheckTwoStepPasswordForm, db: db_dependency):
    return await service.check_two_step_password(form, db)


@app.get(f"{base_url}client", dependencies=[Depends(get_current_user)], response_model=ClientDto)
async def get_client(phone_number: str, db: db_dependency):
    return await service.get_client(phone_number, db)


@app.post(f"{base_url}task", dependencies=[Depends(get_current_user)], response_model=TaskDto)
async def create_task(form: TaskForm, db: db_dependency):
    return await service.create_task(form, db)


@app.get(f"{base_url}task-types", dependencies=[Depends(get_current_user)])
async def get_task_types():
    return await service.get_task_types()


@app.get(f"{base_url}task-statuses", dependencies=[Depends(get_current_user)])
async def get_task_types():
    return await service.get_task_statuses()


@app.get(f"{base_url}task", dependencies=[Depends(get_current_user)], response_model=TaskDto)
async def get_task_by_id(task_id, db: db_dependency):
    return await service.get_task_by_id(task_id, db)


@app.post(f"{base_url}task-page", dependencies=[Depends(get_current_user)], response_model=Page[TaskDto])
async def get_tasks(request: TasksDtoRequest, db: db_dependency):
    return await service.get_tasks(request, db)


@app.put(f"{base_url}task", dependencies=[Depends(get_current_user)], response_model=TaskDto)
async def update_task(task_id, form: TaskUpdateForm, db: db_dependency):
    return await service.update_task(task_id, form, db)


@app.get(f"{base_url}task-clients", dependencies=[Depends(get_current_user)], response_model=Page[ClientTaskDto])
async def get_task_clients(params: pageable_params, task_id, db: db_dependency):
    return await service.get_task_clients(params, task_id, db)


@app.get(f"{base_url}client-tasks", dependencies=[Depends(get_current_user)], response_model=Page[ClientTaskDto])
async def get_client_tasks(params: pageable_params, client_id, db: db_dependency):
    return await service.get_client_tasks(params, client_id, db)


@app.on_event("startup")
async def startup():
    context_refresh_event()


add_pagination(app)


@app.exception_handler(GeneralApiException)
async def general_api_exception_handler(request: Request, ex: GeneralApiException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(PasswordIncorrectException)
async def password_incorrect_exception_handler(request: Request, ex: PasswordIncorrectException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(CredentialsException)
async def credentials_exception_handler(request: Request, ex: CredentialsException):
    return JSONResponse(
        status_code=401,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(RefreshTokenInvalidException)
async def refresh_token_invalid_exception_handler(request: Request, ex: RefreshTokenInvalidException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(PhoneNumberInvalidException)
async def phone_number_invalid_exception_handler(request: Request, ex: PhoneNumberInvalidException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(ClientAlreadyRegisteredException)
async def client_already_registered_exception_handler(request: Request,
                                                      ex: ClientAlreadyRegisteredException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(CodeIsSentException)
async def code_is_sent_exception_handler(request: Request, ex: CodeIsSentException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(PhoneCodeExpiredException)
async def phone_code_expired_exception_handler(request: Request, ex: PhoneCodeExpiredException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(PhoneCodeInvalidException)
async def phone_code_invalid_exception_handler(request: Request, ex: CodeIsSentException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(TwoStepPasswordNeededException)
async def two_step_password_needed_exception_handler(request: Request, ex: TwoStepPasswordNeededException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(TwoStepPasswordInvalidException)
async def two_step_password_invalid_exception_handler(request: Request, ex: TwoStepPasswordInvalidException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(ClientNotFoundException)
async def client_not_found_exception_handler(request: Request, ex: ClientNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(TaskNotFoundException)
async def task_not_found_exception_handler(request: Request, ex: TaskNotFoundException):
    return JSONResponse(
        status_code=404,
        content={"message": f"Oops! {ex.name}."}
    )


@app.exception_handler(TaskCountTooManyException)
async def task_count_too_many_exception_handler(request: Request, ex: TaskCountTooManyException):
    return JSONResponse(
        status_code=400,
        content={"message": f"Oops! {ex.name}."}
    )
