import asyncio
import random
from asyncio import CancelledError
from datetime import timedelta
import math

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi_pagination.ext.sqlalchemy import paginate as s_paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from pyrogram.enums import ChatMemberStatus, ChatMembersFilter
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, BadRequest, UserAlreadyParticipant, \
    PhoneNumberInvalid, RPCError, UsernameInvalid, PhoneCodeExpired, UserBannedInChannel

from pyrogram import Client
from pyrogram.raw import functions
from sqlalchemy import func, false, true
from sqlalchemy.sql import text

import app.api.utils as utils
from app.api.database import SessionLocal
from .enums import GrantType, TaskType, TaskStatus
from .models import MyClient, Task, ClientTask, User
from .exceptions import *
from .dtos import *
from .consts import api_id, api_hash, schedule_interval_time, comment_messages

disable_installed_extensions_check()

clients = dict()


class TgService:

    def __init__(self):
        super()

    @staticmethod
    async def authenticate(form, db):
        if form.grant_type is None:
            raise GeneralApiException("Unsupported grant type")
        match form.grant_type:
            case GrantType.PASSWORD.value:
                if form.username is None:
                    raise GeneralApiException("Username must not empty")
                if form.password is None:
                    raise GeneralApiException("Password must not empty")
                user = db.query(User).filter(User.username == form.username).first()
                if not utils.verify_password(form.password, user.password):
                    raise PasswordIncorrectException("Password incorrect")
                return utils.generate_token(user)
            case GrantType.REFRESH_TOKEN.value:
                if form.refresh_token is None:
                    raise GeneralApiException("Refresh token must not empty")
                token_details = utils.validate_token_and_get_token_details(form.refresh_token)
                if token_details.token_type != GrantType.REFRESH_TOKEN.value:
                    raise RefreshTokenInvalidException("Refresh token invalid")
                user = db.query(User).filter(User.username == token_details.username).first()
                return utils.generate_token(user)

    @staticmethod
    async def register_client(form, db):
        phone_number = correct_phone_number_format(form.phone_number)
        my_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
            MyClient.deleted == false()).first()
        if my_client and my_client.signed:
            raise ClientAlreadyRegisteredException("Client already registered")
        elif my_client:
            raise CodeIsSentException("Confirmation code already has been sent")
        else:
            try:
                deleted_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
                    MyClient.deleted == true()).first()
                if deleted_client:
                    client = clients.get(phone_number)
                else:
                    client = Client(name=phone_number, api_id=api_id, api_hash=api_hash,
                                    phone_number=phone_number, workdir="app/db")
                    await client.connect()
                sent_code = await client.send_code(client.phone_number)
                if deleted_client:
                    deleted_client.deleted = False
                    deleted_client.sent_code_hash = sent_code.phone_code_hash
                    db.add(deleted_client)
                    db.commit()
                    db.refresh(deleted_client)
                else:
                    new_my_client = MyClient(phone_number=phone_number, sent_code_hash=sent_code.phone_code_hash)
                    db.add(new_my_client)
                    db.commit()
                    db.refresh(new_my_client)

                clients[client.phone_number] = client
                return phone_number
            except PhoneNumberInvalid as ex:
                raise PhoneNumberInvalidException(ex.MESSAGE)

    @staticmethod
    async def confirm_code(form: ConfirmationCodeForm, db):
        phone_number = correct_phone_number_format(form.phone_number)
        my_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
            MyClient.deleted == false()).first()
        if my_client and my_client.signed:
            raise ClientAlreadyRegisteredException("Client already registered")
        elif my_client:
            client = clients.get(phone_number)
            try:
                signed_user = await client.sign_in(phone_number=phone_number,
                                                   phone_code_hash=my_client.sent_code_hash,
                                                   phone_code=form.sent_code)
                await client.disconnect()
                my_client.signed = True
                my_client.username = signed_user.username
                my_client.chat_id = signed_user.id
                db.add(my_client)
                db.commit()
                db.refresh(my_client)

                set_task_pending(db)

                clients.pop(client.phone_number)
                return my_client
            except PhoneCodeExpired:
                my_client.deleted = True
                db.add(my_client)
                db.commit()
                db.refresh(my_client)
                raise PhoneCodeExpiredException("Confirmation code expired")
            except SessionPasswordNeeded:
                raise TwoStepPasswordNeededException("Two step password needed")
            except PhoneCodeInvalid:
                raise PhoneCodeInvalidException("Confirmation code is invalid")
        else:
            raise ClientNotFoundException("Phone number not found")

    @staticmethod
    async def check_two_step_password(form: CheckTwoStepPasswordForm, db):
        phone_number = correct_phone_number_format(form.phone_number)
        my_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
            MyClient.deleted == false()).first()
        if my_client and my_client.signed:
            raise ClientAlreadyRegisteredException("Client already registered")
        elif my_client:
            client = clients.get(phone_number)
            try:
                signing_user = await client.check_password(form.two_step_password)
                await client.disconnect()
                my_client.signed = True
                my_client.username = signing_user.username
                my_client.chat_id = signing_user.id
                db.add(my_client)
                db.commit()
                db.refresh(my_client)

                set_task_pending(db)

                clients.pop(client.phone_number)
                return my_client
            except BadRequest:
                raise TwoStepPasswordInvalidException("Two step password is invalid")
        else:
            raise ClientNotFoundException("Phone number not found")

    @staticmethod
    async def get_client(phone_number: str, db):
        my_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
            MyClient.signed == true()).filter(
            MyClient.deleted == false()).first()
        if not my_client:
            raise ClientNotFoundException("Client not found")
        return my_client

    @staticmethod
    async def get_clients(params, db):
        return s_paginate(db.query(MyClient).filter(
            MyClient.deleted == false()).filter(
            MyClient.signed == true()).order_by(
            MyClient.created_at), params)

    @staticmethod
    async def create_task(form: TaskForm, db):
        if form.count == 0:
            task = Task(chat_id=form.chat_id, task_type=TaskType[form.task_type].value, status=TaskStatus.CREATED)
        else:
            if form.task_type != TaskType.EXPORT_CHAT_MEMBERS.name and form.count > db.query(
                    func.count(MyClient.id)).scalar():
                raise TaskCountTooManyException("Task count is too many")
            task = Task(chat_id=form.chat_id, count=form.count, task_type=TaskType[form.task_type].value,
                        status=TaskStatus.PENDING)
        if form.task_type == TaskType.TERMLY_READ_MESSAGES.name:
            task.term_days = form.term_days
        elif form.task_type == TaskType.JOIN_CHAT.name:
            task.interval = form.interval
        elif form.task_type == TaskType.READ_MESSAGE.name:
            task.message_id = form.message_id
            task.interval = form.interval
        elif form.task_type == TaskType.REACT_MESSAGE.name:
            task.message_id = form.message_id
            task.reaction = form.reaction
            task.interval = form.interval
        elif form.task_type == TaskType.EXPORT_CHAT_MEMBERS.name:
            task.exported_chat_id = form.exported_chat_id
            task.interval = form.interval
        elif form.task_type == TaskType.COMMENT_MESSAGE.name:
            task.message_id = form.message_id
            task.interval = form.interval
        else:
            raise GeneralApiException("Task type invalid")
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    async def get_task_types():
        task_types = [{"label": TaskType(e).value, "value": TaskType(e).name} for e in TaskType]
        return task_types

    @staticmethod
    async def get_task_statuses():
        task_statuses = [{"label": TaskType(e).value, "value": TaskType(e).name} for e in TaskStatus]
        return task_statuses

    @staticmethod
    async def get_task_by_id(task_id, db):
        task = db.query(Task).filter(Task.id == task_id).filter(Task.deleted == false()).first()
        if not task:
            raise TaskNotFoundException("Task not found")
        if task.task_type == TaskType.EXPORT_CHAT_MEMBERS:
            query = """
            select id,
       chat_id,
       exported_chat_id,
       task_type,
       status,
       count,
       (select sum(count) from task where parent_task_id = :task_id) as done_count
from task
where id = :task_id"""
        elif task.task_type == TaskType.TERMLY_READ_MESSAGES:
            query = """
            select id,
       chat_id,
       task_type,
       status,
       count,
       term_days,
       (select current_timestamp at time zone 'Asia/Tashkent'::DATE - created_at::DATE) as done_count
from task
where id = :task_id"""
        else:
            query = """
        select t.id,
       chat_id,
       message_id,
       reaction,
       task_type,
       status,
       count,
       t.interval,
       count(ct.id)  as done_count,
       count(ct1.id) as failed_count
from task t
         left join public.client_task ct on t.id = ct.task_id and ct.success = TRUE
         left join public.client_task ct1 on t.id = ct1.task_id and ct1.success = FALSE
where t.id = :task_id
group by t.id"""
        task = db.execute(text(query), {"task_id": task_id}).fetchone()
        return task

    @staticmethod
    async def get_tasks(params, request, db):
        def task_types(x):
            return request.task_type if len(x) != 0 else [TaskType(e).value for e in TaskType]

        def task_statuses(x):
            return request.task_status if len(x) != 0 else [TaskStatus(e).value for e in TaskStatus]

        count_tasks_query = """
        select count(id)
from task
where task_type = ANY (:types)
  and status = ANY (:statuses)
  and (:start_date is null or :end_date is null or created_at between :start_date and :end_date)
  and parent_task_id is NULL"""
        total_tasks_count = db.execute(text(count_tasks_query), {"types": task_types(request.task_type),
                                                                 "statuses": task_statuses(request.task_status),
                                                                 "start_date": request.start_date,
                                                                 "end_date": request.end_date}).scalar()
        tasks = []
        if total_tasks_count != 0:
            query_str = """
            select t.id,
       chat_id,
       task_type,
       status,
       count,
       t.interval
from task t
where t.task_type = ANY (:types)
  and t.status = ANY (:statuses)
  and (:start_date is null or :end_date is null or t.created_at between :start_date and :end_date)
  and t.parent_task_id is NULL
group by t.id, t.created_at
order by t.created_at desc
limit :page offset :page_size"""
            task_rows = db.execute(text(query_str),
                                   {"types": task_types(request.task_type),
                                    "statuses": task_statuses(request.task_status),
                                    "start_date": request.start_date, "end_date": request.end_date,
                                    "page": params.size, "page_size": (params.page - 1) * params.size}).fetchall()

            for task in task_rows:
                tasks.append(TaskDto(id=task.id, chat_id=task.chat_id, task_type=task.task_type, status=task.status,
                                     count=task.count, interval=task.interval))
        return BasePageResponse(items=tasks, total=total_tasks_count, page=params.page,
                                size=params.size, pages=math.ceil(total_tasks_count / params.size))

    @staticmethod
    async def get_child_tasks(params, task_id, db):
        count_query = """
        select count(id)
from task
where parent_task_id = :task_id"""
        query = """
        select id,
       chat_id,
       message_id,
       task_type,
       status,
       count,
       t.interval,
       parent_task_id
from task t
where parent_task_id = :task_id
order by created_at desc
limit :page offset :page_size"""
        total = db.execute(text(count_query), {"task_id": task_id}).scalar()
        child_task_rows = db.execute(text(query), {"task_id": task_id, "page": params.size,
                                                   "page_size": (params.page - 1) * params.size}).fetchall()
        tasks = []
        for task in child_task_rows:
            tasks.append(TaskDto(id=task.id, chat_id=task.chat_id, message_id=task.message_id, task_type=task.task_type,
                                 status=task.status, count=task.count, interval=task.interval,
                                 parent_task_id=task.parent_task_id))
        return BasePageResponse(items=tasks, total=total, page=params.page,
                                size=params.size, pages=math.ceil(total / params.size))

    @staticmethod
    async def update_task(task_id, form, db):
        task = db.query(Task).filter(Task.id == task_id).filter(Task.deleted == false()).first()
        if not task:
            raise TaskNotFoundException("Task not found")
        if task.status == TaskStatus.CREATED or task.status == TaskStatus.PENDING:
            if form.count is not None:
                task.count = form.count
                task.status = TaskStatus.PENDING
            if form.interval is not None:
                task.interval = form.interval
        if task.status == TaskStatus.PENDING and form.status == TaskStatus.PAUSING:
            task.status = TaskStatus.PAUSING
        if task.status == TaskStatus.PAUSING and form.status == TaskStatus.PENDING:
            task.status = TaskStatus.PENDING
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    async def get_task_clients(params, task_id, db):
        task = db.query(Task).filter(Task.id == task_id).filter(Task.deleted == false()).first()
        if not task:
            raise TaskNotFoundException("Task not found")
        if task.task_type == TaskType.EXPORT_CHAT_MEMBERS:
            count_query = """
            select count(ct.id)
from client_task ct
         join client c on c.id = ct.client_id
         join task t on t.id = ct.task_id and t.parent_task_id = :task_id"""
            query = """
        select ct.id,
       c.phone_number as client_phone_number,
       c.chat_id      as client_chat_id,
       task_id,
       t.count,
       success,
       reason,
       ct.interval,
       task_data,
       date
from client_task ct
         join client c on c.id = ct.client_id
         join task t on t.id = ct.task_id and t.parent_task_id = :task_id
order by date"""
        else:
            count_query = """
            select count(ct.id)
from client_task ct
         join client c on c.id = ct.client_id
where ct.task_id = :task_id"""
            query = """
        select ct.id,
       c.phone_number as client_phone_number,
       c.chat_id      as client_chat_id,
       task_id,
       success,
       reason,
       interval,
       task_data,
       date
from client_task ct
         join client c on c.id = ct.client_id
where ct.task_id = :task_id
order by date"""

        total = db.execute(text(count_query), {"task_id": task_id}).scalar()
        client_task_rows = db.execute(text(query), {"task_id": task_id}).fetchall()
        client_tasks = []
        for client_task in client_task_rows:
            if client_task.task_data is not None:
                task_data = client_task.task_data.split(",")
            else:
                task_data = []
            client_tasks.append(ClientTaskDto(id=client_task.id, client_phone_number=client_task.client_phone_number,
                                              client_chat_id=client_task.client_chat_id, task_id=client_task.task_id,
                                              count=client_task.count, success=client_task.success,
                                              reason=client_task.reason,
                                              inetrval=client_task.interval, task_data=task_data,
                                              date=client_task.date))
        return BasePageResponse(total=total, items=client_tasks, page=params.page,
                                size=params.size, pages=math.ceil(total / params.size))

    @staticmethod
    async def get_client_tasks(params, client_id, db):
        client = db.query(MyClient).filter(MyClient.id == client_id).filter(MyClient.deleted == false()).first()
        if not client:
            raise ClientNotFoundException("Client not found")
        count_query = """
        select count(ct.id)
from client_task ct
         join client c on c.id = ct.client_id
where client_id = :client_id"""
        query = """
        select ct.id,
       c.phone_number as client_phone_number,
       c.chat_id      as client_chat_id,
       task_id,
       success,
       reason,
       ct.interval,
       task_data,
       date
from client_task ct
         join client c on c.id = ct.client_id
where client_id = :client_id
order by date"""

        total = db.execute(text(count_query), {"client_id": client_id}).scalar()
        client_task_rows = db.execute(text(query), {"client_id": client_id}).fetchall()
        client_tasks = []
        for client_task in client_task_rows:
            if client_task.task_data is not None:
                task_data = client_task.task_data.split(",")
            else:
                task_data = []
            task = db.query(Task).filter(Task.id == client_task.task_id).filter(Task.deleted == false()).first()
            if task.task_type == TaskType.EXPORT_CHAT_MEMBERS:
                count = task.count
            else:
                count = 1
            client_tasks.append(ClientTaskDto(id=client_task.id, client_phone_number=client_task.client_phone_number,
                                              client_chat_id=client_task.client_chat_id, task_id=client_task.task_id,
                                              count=count, success=client_task.success, reason=client_task.reason,
                                              inetrval=client_task.interval, task_data=task_data,
                                              date=client_task.date))
        return BasePageResponse(total=total, items=client_tasks, page=params.page,
                                size=params.size, pages=math.ceil(total / params.size))


async def join_monsters(monster, task, db):
    async with monster:
        try:
            await monster.join_chat(task.chat_id)
            return ClientTaskDetails()
        except UserAlreadyParticipant as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except UsernameInvalid as ex:
            set_task_invalid(task, db)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except RPCError as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)


async def read_chat_message(monster, task, db):
    async with monster:
        try:
            await monster.invoke(
                functions.messages.GetMessagesViews(peer=await monster.resolve_peer(task.chat_id),
                                                    id=[extract_message_id(task.message_id)],
                                                    increment=True)
            )
            return ClientTaskDetails()
        except BadRequest as ex:
            set_task_invalid(task, db)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except RPCError as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)


async def react_chat_message(monster, task, db):
    async with monster:
        try:
            await monster.send_reaction(task.chat_id, extract_message_id(task.message_id), task.reaction)
            return ClientTaskDetails()
        except BadRequest as ex:
            set_task_invalid(task, db)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except RPCError as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)


async def export_chat_members(monster: Client, task, db, latest_perform):
    query_str = """
    select count(id), sum(count)
    from task
    where parent_task_id = :task_id"""
    count_child_tasks = db.execute(text(query_str), {"task_id": task.id}).fetchone()
    async with monster:
        try:
            await monster.join_chat(task.chat_id)
            await monster.join_chat(task.exported_chat_id)
            members = []
            until = count_child_tasks.count * 10
            count_members_to_be_exported = 10

            if count_child_tasks.sum is None:
                total_count = 0
            else:
                total_count = count_child_tasks.sum
            if task.count - total_count < 10:
                count_members_to_be_exported = task.count - count_child_tasks.sum

            async for member in monster.get_chat_members(chat_id=task.chat_id, filter=ChatMembersFilter.RECENT):
                if member.status == ChatMemberStatus.MEMBER and not member.user.is_deleted:
                    if until == 0:
                        members.append(member.user.id)
                        if len(members) == count_members_to_be_exported:
                            break
                    else:
                        until -= 1

            previous_members_count = await monster.get_chat_members_count(task.exported_chat_id)
            await monster.add_chat_members(task.exported_chat_id, members)
            next_members_count = await monster.get_chat_members_count(task.exported_chat_id)

            new_members = []
            async for member in monster.get_chat_members(chat_id=task.exported_chat_id,
                                                         filter=ChatMembersFilter.RECENT):
                if member.status == ChatMemberStatus.MEMBER and not member.user.is_deleted:
                    new_members.append(str(member.user.id))
                    if len(members) == next_members_count - previous_members_count:
                        break

            child_task = Task(chat_id=task.chat_id, count=next_members_count - previous_members_count,
                              task_type=task.task_type, status=TaskStatus.COMPLETED,
                              exported_chat_id=task.exported_chat_id,
                              parent_task_id=task.id, interval=task.interval)
            db.add(child_task)
            db.commit()
            db.refresh(child_task)

            user = db.query(MyClient).filter(MyClient.phone_number == monster.name).first()
            client_task = ClientTask(client_id=user.id, task_id=child_task.id, success=True, date=datetime.now(),
                                     interval=task.interval, task_data=','.join(new_members))
            db.add(client_task)
            db.commit()
            db.refresh(client_task)

            latest_perform[task.id] = datetime.now()
        except UsernameInvalid as ex:
            set_task_invalid(task, db)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except UserBannedInChannel as ex:
            user.banned = True
            db.add(user)
            db.commit()
            db.refresh(user)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except RPCError as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)


async def comment_message(monster: Client, task, db):
    async with monster:
        try:
            message = await monster.get_discussion_message(task.chat_id, extract_message_id(task.message_id))
            commented_message = random.choice(comment_messages)
            await message.reply(commented_message)
            return ClientTaskDetails(task_data=[commented_message])
        except UserBannedInChannel as ex:
            user = db.query(MyClient).filter(MyClient.phone_number == monster.name).first()
            user.banned = True
            db.add(user)
            db.commit()
            db.refresh(user)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except BadRequest as ex:
            set_task_invalid(task, db)
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)
        except RPCError as ex:
            return ClientTaskDetails(success=False, reason=ex.MESSAGE)


def set_task_pending(db):
    query = """
    update task
set status = :pending
where status = ANY (:statuses)"""
    db.execute(text(query), {"pending": TaskStatus.PENDING, "statuses": [TaskStatus.NOT_COMPLETED, TaskStatus.ILLEGAL]})
    db.commit()


def extract_message_id(link: str):
    splits: [] = link.split("/")
    return int(splits[-1])


def correct_phone_number_format(phone_number):
    if phone_number[0] != "+":
        return f"+{phone_number}"
    else:
        return phone_number


def set_task_invalid(task, db):
    task.status = TaskStatus.INVALID
    db.add(task)
    db.commit()
    db.refresh(task)


latest_perform_tasks = dict()


async def perform_tasks(latest_perform, db):
    try:
        grouped_task_map = dict.fromkeys([TaskType(e).value for e in TaskType], 0)
        grouped_tasks_query = """
            with ordered_tasks as
                 (select *
                  from task
                  where task_type != :termly
                  order by created_at)

        select task_type, min(created_at) as created_at, json_agg(ordered_tasks) as tasks
        from ordered_tasks
        where status = :pending
        group by task_type
        order by created_at"""
        grouped_tasks = list()
        while True:
            grouped_tasks.extend(db.execute(text(grouped_tasks_query), {"termly": TaskType.TERMLY_READ_MESSAGES,
                                                                        "pending": TaskStatus.PENDING}).fetchall())

            # fixed delay
            if len(grouped_tasks) == 0:
                # print(f"schedule go to sleeping: {datetime.now()}")
                await asyncio.sleep(schedule_interval_time)
                # print(f"next schedule: {datetime.now()}")
                continue

            monsters = get_all_clients(db)
            monsters_count = len(monsters)

            while len(grouped_tasks) != 0:
                for index in range(len(grouped_tasks)):
                    grouped_task = grouped_tasks[index]
                    if len(grouped_task.tasks) == 0:
                        grouped_tasks.pop(index)
                        continue
                    task = Task(grouped_task.tasks[grouped_task_map[grouped_task.task_type]])

                    # done task
                    if task.task_type == TaskType.EXPORT_CHAT_MEMBERS.name:
                        done_count = db.query(func.sum(Task.count)).filter(Task.parent_task_id == task.id).scalar()
                        if done_count is None:
                            done_count = 0
                    else:
                        done_count = db.query(func.count(ClientTask.id)).filter(ClientTask.task_id == task.id).filter(
                            ClientTask.success).scalar()
                    used_count = db.query(func.count(ClientTask.id)).filter(ClientTask.task_id == task.id).scalar()
                    if done_count >= task.count or used_count == monsters_count:
                        if done_count >= task.count:
                            task.status = TaskStatus.COMPLETED.name
                        elif used_count == monsters_count and done_count == 0:
                            task.status = TaskStatus.ILLEGAL.name
                        else:
                            task.status = TaskStatus.NOT_COMPLETED.name
                        db.query(Task).filter(Task.id == task.id).update({'status': task.status})
                        db.commit()

                        grouped_task.tasks.pop(grouped_task_map[grouped_task.task_type])

                        try:
                            latest_perform.pop(task.id)
                        except KeyError:
                            pass
                        continue

                    # check task interval
                    if latest_perform.get(task.id) is not None:
                        if int((datetime.now() - latest_perform.get(task.id)).total_seconds()) < task.interval:
                            continue

                    index_monster = 0

                    exported_task_monster_phone_number = None
                    if task.task_type == TaskType.EXPORT_CHAT_MEMBERS.name:
                        query_current_task_monster = """
                        select distinct (phone_number)
from client c
         join client_task ct on c.id = ct.client_id
         join task t on t.id = ct.task_id and t.parent_task_id = :task_id
where banned = false"""
                        exported_task_monster_phone_number = db.execute(text(query_current_task_monster),
                                                                        {"task_id": task.id}).scalar()

                    if exported_task_monster_phone_number is not None:
                        monster = Client(str(exported_task_monster_phone_number), api_id, api_hash, workdir="app/db")
                    else:
                        # finding empty monster
                        while index_monster < len(monsters):
                            monster = monsters[index_monster]
                            user = db.query(MyClient).filter(MyClient.phone_number == monster.name).first()
                            client_task = db.query(ClientTask).filter(
                                ClientTask.task_id == task.id).filter(ClientTask.client_id == user.id).first()

                            if client_task:
                                index_monster += 1
                                continue
                            else:
                                is_monster_empty = """
                                    select *
                from task t
                where t.task_type =:task_type
                  and t.id in (select task_id
                               from client_task ct
                               where ct.client_id =:monster_id
                                 and ct.date + INTERVAL '3 seconds' > current_timestamp at time zone 'Asia/Tashkent')"""
                                empty_monsters = db.execute(text(is_monster_empty),
                                                            {"monster_id": user.id, "task_type": task.task_type})
                                client_tasks = empty_monsters.fetchall()

                                if client_tasks:
                                    index_monster += 1
                                    continue
                                else:
                                    break

                        if index_monster >= len(monsters):
                            continue
                        monster = monsters[index_monster]

                    # last grouped_task sleeping interval
                    if len(grouped_tasks) == 1:
                        query_str = f"""
                        select extract(epoch from (:now - max(ct.date)))
from client_task ct
where ct.task_id in (select id from task t where t.task_type = :type)"""
                        seconds = db.execute(text(query_str), {"now": datetime.now(), "type": task.task_type}).scalar()
                        if seconds is not None and seconds < 3:
                            print(f"Before sleeping: {datetime.now()}")
                            await asyncio.sleep(3 - float(seconds))
                            print(f"After sleeping: {datetime.now()}")

                    # perform task by empty monster
                    if task.count > done_count:
                        print(f"Begin: {datetime.now()}")
                        client_task_details = None
                        match task.task_type:
                            case "JOIN_CHAT":
                                client_task_details = await join_monsters(monster, task, db)
                            case "READ_MESSAGE":
                                client_task_details = await read_chat_message(monster, task, db)
                            case "REACT_MESSAGE":
                                client_task_details = await react_chat_message(monster, task, db)
                            case "EXPORT_CHAT_MEMBERS":
                                client_task_details = await export_chat_members(monster, task, db, latest_perform)
                            case "COMMENT_MESSAGE":
                                client_task_details = await comment_message(monster, task, db)
                        if task.task_type != TaskType.EXPORT_CHAT_MEMBERS or (
                                task.task_type == TaskType.EXPORT_CHAT_MEMBERS and task.status == TaskStatus.INVALID):
                            user = db.query(MyClient).filter(MyClient.phone_number == monster.name).first()
                            client_task = ClientTask(client_id=user.id, task_id=task.id,
                                                     success=client_task_details.success,
                                                     reason=client_task_details.reason, interval=task.interval,
                                                     task_data=client_task_details.task_data,
                                                     date=datetime.now())
                            db.add(client_task)
                            db.commit()
                            db.refresh(client_task)
                            if task.status == TaskStatus.INVALID:
                                grouped_task.tasks.pop(grouped_task_map[grouped_task.task_type])
                            else:
                                latest_perform[task.id] = datetime.now()
                        print(f"End: {datetime.now()}")

                    if len(grouped_task.tasks) == grouped_task_map[grouped_task.task_type] + 1:
                        grouped_task_map[grouped_task.task_type] = 0
                    else:
                        grouped_task_map[grouped_task.task_type] += 1

            grouped_task_map.update(dict.fromkeys([TaskType(e).value for e in TaskType], 0))

    except CancelledError:
        print("Tasks were cancelled")


def get_all_clients(db):
    my_clients = []
    telegram_users = db.query(MyClient).filter(MyClient.signed).all()
    for telegram_user in telegram_users:
        session = Client(telegram_user.phone_number, api_id, api_hash, workdir="app/db")
        my_clients.append(session)
    return my_clients


def context_refresh_event():
    db = SessionLocal()
    initialize_admin(db)
    scheduler = AsyncIOScheduler()
    scheduler.add_job(perform_tasks, "date", run_date=datetime.now() + timedelta(seconds=1),
                      args=[latest_perform_tasks, db])
    scheduler.start()


def initialize_admin(db):
    exists_user = db.query(db.query(User).filter(User.username == 'admin').exists()).scalar()
    if not exists_user:
        admin = User("admin", utils.hash_password("123"), "Admin")
        db.add(admin)
        db.commit()
