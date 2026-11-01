"""
基础功能处理器
"""
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import Group, get_db
from .operator import require_manager


async def start_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始记账"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
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
            from config import config
            group.exchange_rate = config.DEFAULT_EXCHANGE_RATE
            group.fee_rate = config.DEFAULT_FEE_RATE
            db.add(group)
        else:
            group.is_active = True

        await db.commit()

        await update.message.reply_text("✅ 记账功能已开启")


async def stop_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止记账"""
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
            group.is_active = False
            await db.commit()
            await update.message.reply_text("⛔ 记账功能已停止")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def mute_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """下课（禁言模式）- 需要机器人为管理员"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 设置禁言
        from telegram import ChatPermissions
        permissions = ChatPermissions(can_send_messages=False)
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

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 解除禁言
        from telegram import ChatPermissions
        permissions = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True,
            can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True)
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
📚 <b>Yam 记账说明</b>

<b>开始与权限</b>
开始 / 停止：管理员开启或暂停本群记账
添加操作人 / 删除操作人：回复成员消息，或 @本群已发言的成员
显示操作人 / 设置全员 / 取消全员
全局操作人由机器人所有者统一管理

<b>记一笔账</b>
+1000：入款 1000 CNY
+100u：入款 100 USDT
下发1000 / 下发100u：下发人民币 / USDT
P+100 / P-100：增加 / 减少寄存（CNY）
+100u/7.3*3%：本笔汇率 7.3，费率 3%
*0.12 表示 0.12%，不是 12%；回执会明确显示
-100 / 下发-100u：入款 / 下发修正，另存一笔负数记录
张三+100 / 张三下发100：指定本群已见成员
也可回复该成员消息记账；重名时必须回复消息

<b>查看与纠错</b>
显示账单 / +0：本期账单
全部账单：历史账单
/我 / /my：个人本期账单
回复成员消息发送「账单」，或 查账单张三
回复原始记账消息或回执：撤销 / 撤销恢复
撤销入款 / 撤销下发：撤销最近一笔对应记录

<b>费汇与显示</b>
设置汇率7.3 / 设置费率3 / 设置费率3%
设置张三费率0：个人零费率覆盖群费率
回复成员发送「设置汇率7.6」可配置个人汇率
费汇配置 / 删除张三配置
设置入款条数5 / 设置下发条数5（1—50）
纯净模式 / 显示回复人 / 显示入账人
单币模式 / 双币模式 / 记账置顶 / 置顶关闭

<b>结账与导出</b>
保存账单：结束本期，重新计账，历史保留
设置日切时间06:00 / 设置日切6 / 关闭日切
日切与账单时间使用金边时间（UTC+7）
删除账单：作废本期；删除全部账单：作废全部历史
导出账单：Excel 完整明细，包含撤销状态
网页账单：本群完整账单，一小时有效链接

上课 / 下课：管理员控制群发言，需要机器人有相应权限
"""

    await update.message.reply_text(help_text, parse_mode='HTML')
