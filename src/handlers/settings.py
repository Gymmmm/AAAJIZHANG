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


async def set_exchange_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置汇率"""
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

        # 解析设置命令
        rate_info = CommandParser.parse_rate_setting(text)

        if not rate_info or rate_info['type'] != 'exchange_rate':
            return

        # 如果指定了用户名，设置个人汇率
        if rate_info['username']:
            # TODO: 需要通过用户名查找用户ID，这里简化处理
            await update.message.reply_text("❌ 请使用回复消息的方式设置个人汇率")
            return
        # 如果是回复消息，设置个人汇率
        elif update.message.reply_to_message and update.message.reply_to_message.from_user:
            target_user = update.message.reply_to_message.from_user

            # 查找或创建用户配置
            query = select(UserConfig).where(
                and_(
                    UserConfig.group_id == chat_id,
                    UserConfig.user_id == target_user.id
                )
            )
            result = await db.execute(query)
            user_config = result.scalar_one_or_none()

            if not user_config:
                user_config = UserConfig(
                    group_id=chat_id,
                    user_id=target_user.id,
                    username=target_user.username,
                    first_name=target_user.first_name
                )
                db.add(user_config)

            user_config.exchange_rate = rate_info['value']
            await db.commit()

            user_display = target_user.first_name or target_user.username
            await update.message.reply_text(f"✅ 已设置 {user_display} 的汇率为 {rate_info['value']}")
        else:
            # 设置群组默认汇率
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.exchange_rate = rate_info['value']
                await db.commit()
                await update.message.reply_text(f"✅ 已设置群组汇率为 {rate_info['value']}")
            else:
                await update.message.reply_text("❌ 未找到群组配置")


async def set_fee_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置费率"""
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

        # 解析设置命令
        rate_info = CommandParser.parse_rate_setting(text)

        if not rate_info or rate_info['type'] != 'fee_rate':
            return

        # 如果是回复消息，设置个人费率
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            target_user = update.message.reply_to_message.from_user

            # 查找或创建用户配置
            query = select(UserConfig).where(
                and_(
                    UserConfig.group_id == chat_id,
                    UserConfig.user_id == target_user.id
                )
            )
            result = await db.execute(query)
            user_config = result.scalar_one_or_none()

            if not user_config:
                user_config = UserConfig(
                    group_id=chat_id,
                    user_id=target_user.id,
                    username=target_user.username,
                    first_name=target_user.first_name
                )
                db.add(user_config)

            user_config.fee_rate = rate_info['value']
            await db.commit()

            user_display = target_user.first_name or target_user.username
            await update.message.reply_text(f"✅ 已设置 {user_display} 的费率为 {rate_info['value']}%")
        else:
            # 设置群组默认费率
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.fee_rate = rate_info['value']
                await db.commit()
                await update.message.reply_text(f"✅ 已设置群组费率为 {rate_info['value']}%")
            else:
                await update.message.reply_text("❌ 未找到群组配置")


async def show_user_configs(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查看费汇配置"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        # 获取所有用户配置
        query = select(UserConfig).where(UserConfig.group_id == chat_id)
        result = await db.execute(query)
        configs = result.scalars().all()

        # 格式化消息
        message = Formatter.format_user_configs(configs)

        await update.message.reply_text(message)


async def delete_user_config(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除用户配置"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 如果是回复消息
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            target_user = update.message.reply_to_message.from_user

            # 查找用户配置
            query = select(UserConfig).where(
                and_(
                    UserConfig.group_id == chat_id,
                    UserConfig.user_id == target_user.id
                )
            )
            result = await db.execute(query)
            user_config = result.scalar_one_or_none()

            if user_config:
                await db.delete(user_config)
                await db.commit()

                user_display = target_user.first_name or target_user.username
                await update.message.reply_text(f"✅ 已删除 {user_display} 的费汇配置")
            else:
                await update.message.reply_text("❌ 未找到该用户的配置")
        else:
            await update.message.reply_text("❌ 请回复用户消息来删除配置")


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

        if not count_info:
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
            await update.message.reply_text(f"✅ 已设置显示币种为 {currency}")
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
        time_str = CommandParser.parse_day_cut_time(text)

        if not time_str:
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
            await update.message.reply_text(f"📫 下发地址:\n\n{group.withdraw_address}")
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
