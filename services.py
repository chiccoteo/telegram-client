import asyncio
import datetime
import random
from asyncio import CancelledError
from datetime import timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi_pagination.ext.sqlalchemy import paginate as s_paginate
from fastapi_pagination import paginate
from fastapi_pagination.utils import disable_installed_extensions_check
from pyrogram.enums import ChatMemberStatus
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, BadRequest, UserAlreadyParticipant, \
    PhoneNumberInvalid, RPCError, UserNotParticipant, UsernameInvalid, MessageIdInvalid, PhoneCodeExpired

from pyrogram import Client
from pyrogram.raw import functions
from sqlalchemy import func, false, true
from sqlalchemy.sql import text

import utils as utils
from database import SessionLocal
from enums import GrantType, TaskType, TaskStatus
from models import MyClient, Task, ClientTask, User
from exceptions import *
from dtos import *
from consts import api_id, api_hash, schedule_interval_time, comment_messages

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
        my_client = db.query(MyClient).filter(MyClient.phone_number == form.phone_number).filter(
            MyClient.deleted == false()).first()
        if my_client and my_client.signed:
            raise ClientAlreadyRegisteredException("Client already registered")
        elif my_client:
            raise CodeIsSentException("Confirmation code was sent")
        else:
            try:
                client = Client(name=form.phone_number, api_id=api_id, api_hash=api_hash,
                                phone_number=form.phone_number, workdir="app/db")
                await client.connect()
                sent_code = await client.send_code(client.phone_number)
                deleted_client = db.query(MyClient).filter(MyClient.phone_number == form.phone_number).filter(
                    MyClient.deleted == true()).first()
                if deleted_client:
                    deleted_client.deleted = False
                    deleted_client.sent_code_hash = sent_code.phone_code_hash
                    db.add(deleted_client)
                    db.commit()
                    db.refresh(deleted_client)
                else:
                    new_my_client = MyClient(phone_number=form.phone_number, sent_code_hash=sent_code.phone_code_hash)
                    db.add(new_my_client)
                    db.commit()
                    db.refresh(new_my_client)

                clients[client.phone_number] = client
                return form.phone_number
            except PhoneNumberInvalid as ex:
                raise PhoneNumberInvalidException(ex.MESSAGE)

    @staticmethod
    async def confirm_code(form: ConfirmationCodeForm, db):
        my_client = db.query(MyClient).filter(MyClient.phone_number == form.phone_number).filter(
            MyClient.deleted == false()).first()
        if not my_client:
            raise ClientNotFoundException("Phone number not found")
        client = clients.get(form.phone_number)
        try:
            signed_user = await client.sign_in(phone_number=form.phone_number,
                                               phone_code_hash=my_client.sent_code_hash,
                                               phone_code=form.sent_code)
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

    @staticmethod
    async def check_two_step_password(form: CheckTwoStepPasswordForm, db):
        my_client = db.query(MyClient).filter(MyClient.phone_number == form.phone_number).filter(
            MyClient.deleted == false()).first()
        if not my_client:
            raise ClientNotFoundException("Phone number not found")
        client = clients.get(form.phone_number)
        try:
            signing_user = await client.check_password(form.two_step_password)
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

    @staticmethod
    async def get_client(phone_number: str, db):
        my_client = db.query(MyClient).filter(MyClient.phone_number == phone_number).filter(
            MyClient.deleted == false()).first()
        if not my_client:
            raise ClientNotFoundException("Client not found")
        return my_client

    @staticmethod
    async def create_task(form: TaskForm, db):
        if form.count is None:
            task = Task(chat_id=form.chat_id, task_type=form.task_type, status=TaskStatus.CREATED.value)
        else:
            if form.count > db.query(func.count(MyClient.id)).scalar():
                raise TaskCountTooManyException("Task count is too many")
            task = Task(chat_id=form.chat_id, count=form.count, task_type=form.task_type,
                        status=TaskStatus.PENDING.value)
        if form.task_type == TaskType.TERMLY_READ_MESSAGES.value:
            task.term_days = form.term_days
        elif form.task_type == TaskType.JOIN_CHAT.value:
            task.interval = form.interval
        elif form.task_type == TaskType.READ_MESSAGE.value:
            task.message_id = form.message_id
            task.interval = form.interval
        elif form.task_type == TaskType.REACT_MESSAGE.value:
            task.message_id = form.message_id
            task.reaction = form.reaction
            task.interval = form.interval
        elif form.task_type == TaskType.EXPORT_CHAT_MEMBERS.value:
            task.exported_chat_id = form.exported_chat_id
            task.interval = form.interval
        elif form.task_type == TaskType.COMMENT_MESSAGE.value:
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
        task_types = [e for e in TaskType]
        return task_types

    @staticmethod
    async def get_task_statuses():
        task_statuses = [e for e in TaskStatus]
        return task_statuses

    @staticmethod
    async def get_task_by_id(task_id, db):
        task = db.query(Task).filter(Task.id == task_id).filter(Task.deleted == false()).first()
        if not task:
            raise TaskNotFoundException("Task not found")
        query = """
        select t.id,
       chat_id,
       message_id,
       reaction,
       exported_chat_id,
       task_type,
       status,
       count,
       interval,
       term_days,
       parent_task_id,
       count(ct.id)  as done_count,
       count(ct1.id) as failed_count
from task t
         left join public.client_task ct on t.id = ct.task_id and ct.success = TRUE
         left join public.client_task ct1 on t.id = ct1.task_id and ct1.success = FALSE
where t.id = :task_id
group by t.id"""
        result = db.execute(text(query), {"task_id": task_id}).fetchone()
        return result

    @staticmethod
    async def get_tasks(request, db):
        def task_types(x): return request.task_type if len(x) != 0 else [e for e in TaskType]

        def task_statuses(x): return request.task_status if len(x) != 0 else [e for e in TaskStatus]

        def start_date(x): return request.start_date if x is not None else datetime.now() - timedelta(days=1)

        def end_date(x): return request.end_date if x is not None else datetime.now()

        query_str = """
        select t.id,
       chat_id,
       message_id,
       reaction,
       exported_chat_id,
       task_type,
       status,
       count,
       interval,
       term_days,
       parent_task_id,
       count(ct.id)  as done_count,
       count(ct1.id) as failed_count
from task t
         left join public.client_task ct on t.id = ct.task_id and ct.success = TRUE
         left join public.client_task ct1 on t.id = ct1.task_id and ct1.success = FALSE
where t.task_type = ANY(:types)
  and t.status = ANY(:statuses)
  and t.created_at between :start_date and :end_date
group by t.id, t.created_at
order by t.created_at"""
        results = db.execute(text(query_str),
                             {"types": task_types(request.task_type), "statuses": task_statuses(request.task_status),
                              "start_date": start_date(request.start_date),
                              "end_date": end_date(request.end_date)}).fetchall()
        return paginate(results)

    @staticmethod
    async def update_task(task_id, form, db):
        task = db.query(Task).filter(Task.id == task_id).filter(Task.deleted == false()).first()
        if not task:
            raise TaskNotFoundException("Task not found")
        if form.count is not None:
            task.count = form.count
            if task.status == TaskStatus.CREATED:
                task.status = TaskStatus.PENDING
        if task.status == TaskStatus.PENDING and form.status == TaskStatus.PAUSING:
            task.status = form.status
        if task.status == TaskStatus.PAUSING and form.status == TaskStatus.PENDING:
            task.status = form.status
        db.add(task)
        db.commit()
        db.refresh(task)
        return task

    @staticmethod
    async def get_task_clients(params, task_id, db):
        return s_paginate(db.query(ClientTask).filter(ClientTask.task_id == task_id).order_by(ClientTask.date),
                          params)

    @staticmethod
    async def get_client_tasks(params, client_id, db):
        return s_paginate(db.query(ClientTask).filter(ClientTask.client_id == client_id).order_by(ClientTask.date),
                          params)


async def join_monsters(monster, task, db):
    async with monster:
        try:
            await monster.join_chat(task.chat_id)
            return True
        except UserAlreadyParticipant:
            return False
        except UsernameInvalid:
            return set_task_invalid(task, db)
        except RPCError:
            return False


async def read_chat_message(monster, task, db):
    async with monster:
        try:
            await monster.invoke(
                functions.messages.GetMessagesViews(peer=await monster.resolve_peer(task.chat_id),
                                                    id=[extract_message_id(task.message_id)],
                                                    increment=True)
            )
            return True
        except UsernameInvalid | MessageIdInvalid:
            return set_task_invalid(task, db)
        except RPCError:
            return False


async def react_chat_message(monster, task, db):
    async with monster:
        try:
            await monster.send_reaction(task.chat_id, extract_message_id(task.message_id), task.reaction)
            return True
        except UsernameInvalid | MessageIdInvalid:
            return set_task_invalid(task, db)
        except RPCError:
            return False


async def export_chat_members(monster, task, db):
    async with monster:
        try:
            await monster.join_chat(task.chat_id)
            await monster.join_chat(task.exported_chat_id)
        except UsernameInvalid:
            return set_task_invalid(task, db)
        try:
            async for member in monster.get_chat_members(chat_id=task.chat_id):
                if member.status == ChatMemberStatus.MEMBER:
                    try:
                        await monster.get_chat_member(task.exported_chat_id, member.user.id)
                    except UserNotParticipant:
                        try:
                            await monster.add_chat_members(task.exported_chat_id, member.user.id)
                            await asyncio.sleep(task.interval)
                        except RPCError:
                            return False
        except RPCError:
            return False


async def comment_message(monster: Client, task, db):
    async with monster:
        try:
            message = await monster.get_discussion_message(task.chat_id, extract_message_id(task.message_id))
            await message.reply(random.choice(comment_messages))
            return True
        except UsernameInvalid | MessageIdInvalid:
            return set_task_invalid(task, db)
        except RPCError:
            return False


def set_task_pending(db):
    query = """
    update task
set status='PENDING'
where status in ('COMPLETED', 'ILLEGAL')"""
    db.execute(text(query))
    db.commit()


def extract_message_id(link: str):
    splits: [] = link.split("/")
    return int(splits[-1])


def set_task_invalid(task, db):
    task.status = TaskStatus.INVALID
    db.add(task)
    db.commit()
    return False


latest_perform_tasks = dict()


async def perform_tasks(latest_perform, db):
    monsters_count = db.query(func.count(MyClient.id)).scalar()
    monsters = get_all_clients(db)
    try:
        grouped_task_map = dict.fromkeys([e for e in TaskType], 0)
        grouped_tasks_query = """
            with ordered_tasks as
                 (select *
                  from task
                  order by created_at)

        select task_type, min(created_at) as created_at, json_agg(ordered_tasks) as tasks
        from ordered_tasks
        where status = 'PENDING'
        group by task_type
        order by created_at"""
        grouped_tasks = list()
        while True:
            grouped_tasks.extend(db.execute(text(grouped_tasks_query)).fetchall())

            # fixed delay
            if len(grouped_tasks) == 0:
                # print(f"schedule go to sleeping: {datetime.datetime.now()}")
                await asyncio.sleep(schedule_interval_time)
                # print(f"next schedule: {datetime.datetime.now()}")
                continue

            while len(grouped_tasks) != 0:
                for index in range(len(grouped_tasks)):
                    grouped_task = grouped_tasks[index]
                    if len(grouped_task.tasks) == 0:
                        grouped_tasks.pop(index)
                        continue
                    task = Task(grouped_task.tasks[grouped_task_map[grouped_task.task_type]])

                    # done task
                    done_count = db.query(func.count(ClientTask.id)).filter(ClientTask.task_id == task.id).filter(
                        ClientTask.success).scalar()
                    used_count = db.query(func.count(ClientTask.id)).filter(ClientTask.task_id == task.id).scalar()
                    if done_count >= task.count or used_count == monsters_count:
                        if done_count >= task.count:
                            task.status = TaskStatus.COMPLETED
                        elif used_count == monsters_count and done_count == 0:
                            task.status = TaskStatus.ILLEGAL
                        else:
                            task.status = TaskStatus.NOT_COMPLETED
                        db.query(Task).filter(Task.id == task.id).update({'status': task.status})
                        db.commit()

                        grouped_task.tasks.pop(0)
                        if len(grouped_task.tasks) == 0:
                            grouped_tasks.pop()

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

                    # last grouped_task sleeping interval
                    if len(grouped_tasks) == 1:
                        query_str = """
                        select extract(epoch from (current_timestamp at time zone 'Asia/Tashkent' - max(ct.date)))
from client_task ct
where ct.task_id in (select id from task t where t.task_type = :type)"""
                        seconds = db.execute(text(query_str), {"type": task.task_type}).scalar()
                        if seconds < 3:
                            await asyncio.sleep(3 - float(seconds))

                    # perform task by empty monster
                    if task.count > done_count:
                        monster = monsters[index_monster]
                        result = False
                        match task.task_type:
                            case "JOIN_CHAT":
                                result = await join_monsters(monster, task, db)
                            case "READ_MESSAGE":
                                result = await read_chat_message(monster, task, db)
                            case "REACT_MESSAGE":
                                result = await react_chat_message(monster, task, db)
                            case "EXPORT_CHAT_MEMBERS":
                                result = await export_chat_members(monster, task, db)
                            case "COMMENT_MESSAGE":
                                result = await comment_message(monster, task, db)
                        if task.status != TaskStatus.INVALID:
                            user = db.query(MyClient).filter(MyClient.phone_number == monster.name).first()
                            client_task = ClientTask(user.id, task.id, result, datetime.now())
                            db.add(client_task)
                            db.commit()
                            db.refresh(client_task)
                            latest_perform[task.id] = datetime.now()

                    if len(grouped_task.tasks) == grouped_task_map[grouped_task.task_type] + 1:
                        grouped_task_map[grouped_task.task_type] = 0
                    else:
                        grouped_task_map[grouped_task.task_type] += 1

            grouped_task_map.update(dict.fromkeys([e for e in TaskType], 0))

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
