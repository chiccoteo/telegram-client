from contextlib import asynccontextmanager
from fastapi import Depends
from fastapi_pagination import Page, Params, add_pagination
from sqlalchemy.orm import Session
from typing import Annotated
from fastapi import Request
from fastapi.responses import JSONResponse

from .consts import base_url
from .dtos import *
from fastapi import FastAPI
from .exceptions import *

import app.api.models as models
from app.api.database import engine, SessionLocal
from .services import TelegramClientService, context_refresh_event
from .utils import get_current_user

models.Base.metadata.create_all(bind=engine)


@asynccontextmanager
async def lifespan(app_fast_api: FastAPI):
    context_refresh_event()
    yield


app = FastAPI(lifespan=lifespan)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


db_dependency = Annotated[Session, Depends(get_db)]
pageable_params = Annotated[Params, Depends()]
service = TelegramClientService()


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


@app.post(f"{base_url}clear-session", dependencies=[Depends(get_current_user)])
async def clear_session(form: ClientRegistrationForm, db: db_dependency):
    await service.clear_session(form.phone_number, db)


@app.get(f"{base_url}clients-page", dependencies=[Depends(get_current_user)], response_model=Page[ClientDto])
async def get_clients(params: pageable_params, db: db_dependency):
    return await service.get_clients(params, db)


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


@app.post(f"{base_url}task-page", dependencies=[Depends(get_current_user)])
async def get_tasks(params: pageable_params, request: TasksDtoRequest, db: db_dependency):
    return await service.get_tasks(params, request, db)


@app.get(f"{base_url}child-tasks", dependencies=[Depends(get_current_user)], response_model=Page[TaskDto])
async def get_child_tasks(params: pageable_params, task_id, db: db_dependency):
    return await service.get_child_tasks(params, task_id, db)


@app.put(f"{base_url}task", dependencies=[Depends(get_current_user)], response_model=TaskDto)
async def update_task(task_id, form: TaskUpdateForm, db: db_dependency):
    return await service.update_task(task_id, form, db)


@app.get(f"{base_url}task-clients", dependencies=[Depends(get_current_user)])
async def get_task_clients(params: pageable_params, task_id, db: db_dependency):
    return await service.get_task_clients(params, task_id, db)


@app.get(f"{base_url}client-tasks", dependencies=[Depends(get_current_user)], response_model=Page[ClientTaskDto])
async def get_client_tasks(params: pageable_params, client_id, db: db_dependency):
    return await service.get_client_tasks(params, client_id, db)


add_pagination(app)


@app.exception_handler(TelegramClientException)
async def telegram_client_exception_handler(request: Request, ex: TelegramClientException):
    return JSONResponse(
        status_code=400,
        content=ex.get_error_message()
    )
