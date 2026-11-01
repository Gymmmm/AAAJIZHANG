"""
参数设置处理器
"""
from datetime import time as dt_time
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select, and_

from ..models import Group, UserConfig, get_db
from ..utils.parser import CommandParser
from ..utils.formatter import Formatter
from .operator import is_operator


async def _set_rate(update, context):
    from ..services.identity import resolve_user
    from ..models import LedgerAudit
    async for db in get_db():
        gid, uid = update.effective_chat.id, update.effective_user.id
        if not await is_operator(uid, gid, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        try:
            info = CommandParser.parse_rate_setting(update.message.text)
            if not info:
                await update.message.reply_text("格式：设置汇率7.3 或 设置费率3%。")
                return
            reply = update.message.reply_to_message
            name = info['username']
            target = None
            if name not in (None, '他', '她'):
                target = await resolve_user(db, gid, name)
            elif reply and reply.from_user and not reply.from_user.is_bot:
                target = reply.from_user
            elif name:
                raise ValueError('请回复成员消息设置个人配置。')
            if target:
                row = (await db.execute(select(UserConfig).where(UserConfig.group_id == gid,
                    UserConfig.user_id == target.id))).scalar_one_or_none()
                if not row:
                    row = UserConfig(group_id=gid, user_id=target.id, username=target.username, first_name=target.first_name)
                    db.add(row)
                label = target.first_name or target.username or str(target.id)
            else:
                row = (await db.execute(select(Group).where(Group.group_id == gid))).scalar_one_or_none()
                if not row:
                    raise ValueError('请先发送「开始」。')
                label = '本群'
            old = getattr(row, info['type'])
            setattr(row, info['type'], float(info['value']))
            db.add(LedgerAudit(group_id=gid, actor_id=uid, action='set_' + info['type'],
                               detail=f'{label}: {old} -> {info["value"]}'))
            await db.commit()
            unit = '%' if info['type'] == 'fee_rate' else ' CNY / USDT'
            await update.message.reply_text(f'✅ {label} {"费率" if info["type"] == "fee_rate" else "汇率"}：{info["value"]}{unit}')
        except ValueError as error:
            await update.message.reply_text(str(error))

async def set_exchange_rate(update, context):
    await _set_rate(update, context)

async def set_fee_rate(update, context):
    await _set_rate(update, context)

async def show_user_configs(update, context):
    async for db in get_db():
        if not await is_operator(update.effective_user.id, update.effective_chat.id, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        configs = (await db.execute(select(UserConfig).where(UserConfig.group_id == update.effective_chat.id))).scalars().all()
        await update.message.reply_text(Formatter.format_user_configs(configs))

async def delete_user_config(update, context):
    from ..services.identity import resolve_user
    async for db in get_db():
        gid = update.effective_chat.id
        if not await is_operator(update.effective_user.id, gid, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        try:
            name = update.message.text.removeprefix('删除').removesuffix('配置').strip()
            reply = update.message.reply_to_message
            if name not in ('他','他的','她','她的',''):
                target = await resolve_user(db, gid, name)
            elif reply and reply.from_user and not reply.from_user.is_bot:
                target = reply.from_user
            else:
                raise ValueError('请回复该成员的消息，再发送「删除配置」。')
            row = (await db.execute(select(UserConfig).where(UserConfig.group_id == gid, UserConfig.user_id == target.id))).scalar_one_or_none()
            if row:
                await db.delete(row)
                await db.commit()
            await update.message.reply_text('✅ 已清除该成员的个人费汇配置，后续使用群默认配置。')
        except ValueError as error:
            await update.message.reply_text(str(error))


async def set_display_count(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置显示条数"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析命令
        count_info = CommandParser.parse_display_count(text)

        if not count_info or not 1 <= count_info['count'] <= 50:
            await update.message.reply_text('显示条数须在 1 到 50 之间。')
            return

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            if count_info['type'] == 'deposit':
                group.deposit_display_count = count_info['count']
                await db.commit()
                await update.message.reply_text(f"✅ 已设置入款显示条数为 {count_info['count']}")
            elif count_info['type'] == 'withdraw':
                group.withdraw_display_count = count_info['count']
                await db.commit()
                await update.message.reply_text(f"✅ 已设置下发显示条数为 {count_info['count']}")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def set_classic_display_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置经典显示模式1/2/3
    显示模式1：最近3笔（默认）
    显示模式2：最近1笔
    显示模式3：仅汇总
    """
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    async for db in get_db():
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            await update.message.reply_text("❌ 未找到群组配置")
            return

        if text == "显示模式1":
            group.deposit_display_count = 3
            group.withdraw_display_count = 3
            await db.commit()
            await update.message.reply_text("✅ 已设置显示模式1（最近 3 笔入款/下发）")
        elif text == "显示模式2":
            group.deposit_display_count = 1
            group.withdraw_display_count = 1
            await db.commit()
            await update.message.reply_text("✅ 已设置显示模式2（最近 1 笔入款/下发）")
        elif text == "显示模式3":
            group.deposit_display_count = 0
            group.withdraw_display_count = 0
            await db.commit()
            await update.message.reply_text("✅ 已设置显示模式3（仅显示汇总）")
        else:
            await update.message.reply_text("格式：显示模式1 / 显示模式2 / 显示模式3")


async def set_currency_display(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置币种显示"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析命令
        currency = CommandParser.parse_currency_display(text)

        if not currency:
            return

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.currency_display = currency
            await db.commit()
            await update.message.reply_text(f"✅ 已设置显示币种标签为 {currency}；不会改变原始入账币种或金额。")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def toggle_pin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换置顶功能"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            if text in ["记账置顶", "开启置顶"]:
                group.pin_enabled = True
                await db.commit()
                await update.message.reply_text("✅ 已开启记账置顶")
            elif text in ["置顶关闭", "关闭置顶"]:
                group.pin_enabled = False
                await db.commit()
                await update.message.reply_text("✅ 已关闭记账置顶")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def toggle_currency_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换币种模式"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            if text == "双币模式":
                group.currency_mode = "dual"
                await db.commit()
                await update.message.reply_text("✅ 已切换为双币模式")
            elif text == "单币模式":
                group.currency_mode = "single"
                await db.commit()
                await update.message.reply_text("✅ 已切换为单币模式")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def toggle_display_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """切换显示模式"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            if text == "纯净模式":
                group.display_mode = "pure"
                await db.commit()
                await update.message.reply_text("✅ 已切换为纯净模式")
            elif text == "显示回复人":
                group.display_mode = "reply"
                await db.commit()
                await update.message.reply_text("✅ 已切换为显示回复人模式")
            elif text == "显示入账人":
                group.display_mode = "operator"
                await db.commit()
                await update.message.reply_text("✅ 已切换为显示操作人模式")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def set_day_cut_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置日切时间"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析时间
        if text == '关闭日切':
            group = (await db.execute(select(Group).where(Group.group_id == chat_id))).scalar_one_or_none()
            if group:
                group.day_cut_time = None
                await db.commit()
                service = context.application.bot_data.get('schedule_service')
                if service:
                    await service.remove_day_cut_task(chat_id)
                await update.message.reply_text('✅ 已关闭自动日切，账期可手动保存。')
            return
        time_str = CommandParser.parse_day_cut_time(text)

        if not time_str:
            await update.message.reply_text('格式：设置日切时间06:00，或 关闭日切。')
            return

        try:
            hour, minute = map(int, time_str.split(':'))
            day_cut_time = dt_time(hour=hour, minute=minute)

            # 更新群组配置
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.day_cut_time = day_cut_time
                await db.commit()

                # 更新定时任务
                from ..services.schedule_service import ScheduleService
                if context.application.bot_data.get("schedule_service"):
                    await context.application.bot_data["schedule_service"].add_day_cut_task(group)

                await update.message.reply_text(f"✅ 已设置日切时间为 {time_str}")
            else:
                await update.message.reply_text("❌ 未找到群组配置")
        except Exception as e:
            await update.message.reply_text(f"❌ 时间格式错误: {str(e)}")


async def set_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置下发地址"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 提取地址
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("❌ 请提供下发地址")
            return

        address = parts[1].strip()

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.withdraw_address = address
            await db.commit()
            await update.message.reply_text(f"✅ 已设置下发地址\n\n{address}")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def show_withdraw_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示下发地址"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group and group.withdraw_address:
            await update.message.reply_text(f"📮 下发地址:\n\n{group.withdraw_address}")
        else:
            await update.message.reply_text("❌ 未设置下发地址")


async def show_group_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示群组配置"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            message = Formatter.format_group_config(group)
            await update.message.reply_text(message)
        else:
            await update.message.reply_text("❌ 未找到群组配置")
