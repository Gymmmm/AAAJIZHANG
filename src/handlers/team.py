"""
团队操作处理器（单群多盘口）
"""
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import Team, TeamMember, get_db
from .operator import is_operator


async def create_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建团队"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()
    if not text.startswith("创建团队"):
        return
    name = text.removeprefix("创建团队").strip()
    if not name:
        await update.message.reply_text("格式：创建团队xx")
        return
    async for db in get_db():
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        team = Team(group_id=chat_id, name=name)
        db.add(team)
        await db.commit()
        await update.message.reply_text(f"✅ 已创建团队：{name}")


async def list_teams(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """团队列表"""
    if not update.message or not update.effective_chat:
        return
    chat_id = update.effective_chat.id
    async for db in get_db():
        teams = (await db.execute(
            select(Team).where(Team.group_id == chat_id, Team.is_archived == False)
        )).scalars().all()
        if not teams:
            await update.message.reply_text("暂无团队")
            return
        lines = ["👥 团队列表："]
        for t in teams:
            lines.append(f"• {t.name}")
        await update.message.reply_text("\n".join(lines))


async def archive_team(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """归档团队"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()
    if not text.startswith("归档团队"):
        return
    name = text.removeprefix("归档团队").strip()
    if not name:
        await update.message.reply_text("格式：归档团队xx")
        return
    async for db in get_db():
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        team = (await db.execute(
            select(Team).where(Team.group_id == chat_id, Team.name == name, Team.is_archived == False)
        )).scalar_one_or_none()
        if not team:
            await update.message.reply_text("未找到该团队")
            return
        team.is_archived = True
        await db.commit()
        await update.message.reply_text(f"✅ 已归档团队：{name}")
