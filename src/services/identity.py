"""Resolve only Telegram identities actually observed in this chat."""
from types import SimpleNamespace
from sqlalchemy import select, func
from sqlalchemy.exc import IntegrityError
from ..models import KnownMember, AsyncSessionLocal

async def remember_user(db, group_id, user):
    if not user or user.is_bot:
        return
    row = (await db.execute(select(KnownMember).where(
        KnownMember.group_id == group_id, KnownMember.user_id == user.id))).scalar_one_or_none()
    if not row:
        row = KnownMember(group_id=group_id, user_id=user.id, first_name=user.full_name)
        db.add(row)
    row.username = user.username
    row.first_name = user.full_name
    await db.flush()

async def remember_update(update, context):
    if not update.effective_chat or not update.effective_user:
        return
    async with AsyncSessionLocal() as db:
        try:
            await remember_user(db, update.effective_chat.id, update.effective_user)
            reply = update.effective_message.reply_to_message if update.effective_message else None
            if reply:
                await remember_user(db, update.effective_chat.id, reply.from_user)
            await db.commit()
        except IntegrityError:
            await db.rollback()

async def resolve_user(db, group_id, name):
    name = name.strip()
    q = select(KnownMember).where(KnownMember.group_id == group_id)
    if name.startswith('@'):
        q = q.where(func.lower(KnownMember.username) == name[1:].lower())
    else:
        q = q.where((KnownMember.first_name == name) | (func.lower(KnownMember.username) == name.lower()))
    rows = (await db.execute(q)).scalars().all()
    if len(rows) != 1:
        raise ValueError('没有找到唯一对应的成员，请回复该成员的消息操作。')
    row = rows[0]
    return SimpleNamespace(id=row.user_id, username=row.username, first_name=row.first_name,
                           full_name=row.first_name)
