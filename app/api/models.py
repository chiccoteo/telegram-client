from sqlalchemy import Column, Integer, Boolean, String, ForeignKey, TIMESTAMP, text, BigInteger, Text

from app.api.database import Base


class BaseModel:
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    created_at = Column(TIMESTAMP, server_default=text("now()"))
    deleted = Column(Boolean, server_default='False')


class User(Base, BaseModel):
    __tablename__ = "users"

    username = Column(String(length=16), unique=True, nullable=False)
    password = Column(String, nullable=False)
    first_name = Column(String(length=16))
    last_name = Column(String(length=16))

    def __init__(self, username, password, first_name):
        self.username = username
        self.password = password
        self.first_name = first_name


class MyClient(Base, BaseModel):
    __tablename__ = "client"

    username = Column(String(length=32), unique=True)
    phone_number = Column(String(length=13), unique=True, nullable=False)
    chat_id = Column(String(length=32), unique=True)
    banned = Column(Boolean, server_default='False')
    signed = Column(Boolean, server_default='False')
    sent_code_hash = Column(String(length=32))

    def __init__(self, phone_number, sent_code_hash):
        self.phone_number = phone_number
        self.sent_code_hash = sent_code_hash


class Task(Base, BaseModel):
    __tablename__ = "task"

    chat_id = Column(String(length=32), nullable=False)
    message_id = Column(String(length=64))
    reaction = Column(String(length=32))
    exported_chat_id = Column(String(length=32))
    task_type = Column(String, nullable=False)
    status = Column(String, nullable=False)
    count = Column(Integer, nullable=False)
    interval = Column(Integer)
    term_days = Column(Integer)
    parent_task_id = Column(BigInteger, ForeignKey("task.id"))

    def __init__(self, task_dict=None, chat_id=None, task_type=None, count=None, status=None, message_id=None,
                 reaction=None, exported_chat_id=None, interval=None, parent_task_id=None, term_days=None):
        self.chat_id = chat_id
        self.message_id = message_id
        self.reaction = reaction
        self.exported_chat_id = exported_chat_id
        self.interval = interval
        self.parent_task_id = parent_task_id
        self.task_type = task_type
        self.status = status
        self.count = count
        self.term_days = term_days

        if task_dict is not None:
            for key, value in task_dict.items():
                setattr(self, key, value)


class ClientTask(Base, BaseModel):
    __tablename__ = "client_task"

    client_id = Column(BigInteger, ForeignKey("client.id"), nullable=False)
    task_id = Column(BigInteger, ForeignKey("task.id"), nullable=False)
    success = Column(Boolean, nullable=False)
    reason = Column(String)
    interval = Column(Integer)
    task_data = Column(Text)
    date = Column(TIMESTAMP, nullable=False)

    def __init__(self, client_id, task_id, success, interval, date, reason=None, task_data=None):
        self.client_id = client_id
        self.task_id = task_id
        self.success = success
        self.reason = reason
        self.interval = interval
        self.task_data = task_data
        self.date = date
