import asyncio

from pyrogram import Client, raw
from pyrogram.enums import ChatMembersFilter, ChatMemberStatus
from pyrogram.errors import MessageIdInvalid, UsernameInvalid, RPCError, UserAlreadyParticipant
from pyrogram.raw import functions
from sqlalchemy import text, func

from app.api.consts import api_id, api_hash
from app.api.models import Task, User
from app.db.database import SessionLocal


def test():
    db = SessionLocal()
    d = db.execute(text("""select count(id), sum(count)
from task
where parent_task_id = :task_id"""), {"task_id": 1}).fetchone()
    print(d)


async def a():
    c = Client("998910031711", api_id, api_hash, workdir="app/db")
    async with c:
        members = []
        async for member in c.get_chat_members(chat_id="OptimusInvest_Academy", filter=ChatMembersFilter.RECENT):
            if member.status == ChatMemberStatus.MEMBER and not member.user.is_deleted:
                members.append(member)
                if len(members) == 5:
                    break
        print(members)


if __name__ == '__main__':
    test()
