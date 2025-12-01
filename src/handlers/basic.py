"""
基础功能处理器
"""
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import Group, get_db


async def start_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始记账"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"

    async for db in get_db():
        # 查找或创建群组
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            # 创建新群组
            group = Group(
                group_id=chat_id,
                group_name=chat_title,
                group_type=update.effective_chat.type,
                is_active=True
            )
            db.add(group)
        else:
            group.is_active = True

        await db.commit()

        await update.message.reply_text("✅ 记账功能已开启")


async def stop_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止记账"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.is_active = False
            await db.commit()
            await update.message.reply_text("⛔ 记账功能已停止")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def mute_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """下课（禁言模式）- 需要机器人为管理员"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 设置禁言
        permissions = await update.effective_chat.get_permissions()
        permissions.can_send_messages = False
        await context.bot.set_chat_permissions(chat_id, permissions)

        async for db in get_db():
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.is_muted = True
                await db.commit()

        await update.message.reply_text("🔇 群组已进入禁言模式（下课）")

    except Exception as e:
        await update.message.reply_text(f"❌ 操作失败: {str(e)}")


async def unmute_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """上课（解除禁言）- 需要机器人为管理员"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 解除禁言
        permissions = await update.effective_chat.get_permissions()
        permissions.can_send_messages = True
        await context.bot.set_chat_permissions(chat_id, permissions)

        async for db in get_db():
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.is_muted = False
                await db.commit()

        await update.message.reply_text("🔊 群组已解除禁言（上课）")

    except Exception as e:
        await update.message.reply_text(f"❌ 操作失败: {str(e)}")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示帮助信息"""
    if not update.message:
        return

    help_text = """
📚 <b>飞机最强记账机器人操作说明</b>

<b>1️⃣ 基础功能</b>
• 开始 - 开始记账
• 停止 - 停止记账
• 上课 - 打开发言（需管理员权限）
• 下课 - 停止发言（需管理员权限）

<b>2️⃣ 账单操作</b>
• +1000 - 记账入款
• +1000u - USDT入款
• +1000/7.3 - 指定汇率
• +1000*3% - 指定费率
• 张三+1000 - 指定用户入款
• 下发1000 - 记账下发
• P+1000 - 账单寄存
• -1000 - 入款修正

<b>3️⃣ 查询功能</b>
• 显示账单 或 +0 - 显示当前账单
• 全部账单 - 查看所有账单
• 账单汇总 - 查看汇总统计
• /我 - 查看我的账单

<b>4️⃣ 配置功能</b>
• 设置汇率7.3
• 设置费率3
• 设置张三汇率7.3
• 显示操作人
• 添加操作人 @用户

发送 /commands 查看完整命令列表
"""

    await update.message.reply_text(help_text, parse_mode='HTML')
