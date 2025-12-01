"""
账单记录和操作处理器
"""
from telegram import Update
from telegram.ext import ContextTypes, MessageHandler, filters
from sqlalchemy import select, and_

from ..models import Group, UserConfig, Transaction, get_db
from ..services.billing_service import BillingService
from ..utils.parser import CommandParser
from ..utils.formatter import Formatter
from .operator import is_operator


async def handle_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理入款操作"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查记账是否开启
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group or not group.is_active:
            return

        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析入款命令
        deposit_info = CommandParser.parse_deposit(text)

        if not deposit_info:
            return

        # 确定入款用户
        target_user_id = user.id
        target_username = user.username
        target_first_name = user.first_name

        # 如果指定了用户名或是回复消息
        if deposit_info['username']:
            # TODO: 根据用户名查找用户ID
            pass
        elif update.message.reply_to_message and update.message.reply_to_message.from_user:
            replied_user = update.message.reply_to_message.from_user
            target_user_id = replied_user.id
            target_username = replied_user.username
            target_first_name = replied_user.first_name

        # 获取用户个人配置
        query = select(UserConfig).where(
            and_(
                UserConfig.group_id == chat_id,
                UserConfig.user_id == target_user_id
            )
        )
        result = await db.execute(query)
        user_config = result.scalar_one_or_none()

        # 确定汇率和费率
        exchange_rate = deposit_info['exchange_rate'] or \
                       (user_config.exchange_rate if user_config else None) or \
                       group.exchange_rate

        fee_rate = deposit_info['fee_rate'] or \
                  (user_config.fee_rate if user_config else None) or \
                  group.fee_rate

        # 创建交易记录
        transaction = await BillingService.create_transaction(
            db=db,
            group_id=chat_id,
            user_id=target_user_id,
            username=target_username,
            first_name=target_first_name,
            operator_id=user.id,
            operator_username=user.username,
            operator_first_name=user.first_name,
            transaction_type='deposit',
            amount=deposit_info['amount'],
            currency=deposit_info['currency'],
            exchange_rate=exchange_rate if deposit_info['currency'] == 'USDT' else None,
            fee_rate=fee_rate,
            note=deposit_info['note'],
            message_id=update.message.message_id,
            reply_to_message_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None
        )

        # 格式化回复消息
        reply_message = Formatter.format_transaction(
            transaction,
            display_mode=group.display_mode,
            currency_mode=group.currency_mode
        )

        # 发送确认消息
        sent_message = await update.message.reply_text(f"✅ 入款成功\n\n{reply_message}")

        # 如果开启置顶，置顶消息
        if group.pin_enabled:
            try:
                await sent_message.pin(disable_notification=True)
            except Exception:
                pass


async def handle_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理下发操作"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查记账是否开启
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group or not group.is_active:
            return

        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析下发命令
        withdraw_info = CommandParser.parse_withdraw(text)

        if not withdraw_info:
            return

        # 确定下发用户
        target_user_id = user.id
        target_username = user.username
        target_first_name = user.first_name

        # 如果是回复消息
        if update.message.reply_to_message and update.message.reply_to_message.from_user:
            replied_user = update.message.reply_to_message.from_user
            target_user_id = replied_user.id
            target_username = replied_user.username
            target_first_name = replied_user.first_name

        # 获取用户个人配置
        query = select(UserConfig).where(
            and_(
                UserConfig.group_id == chat_id,
                UserConfig.user_id == target_user_id
            )
        )
        result = await db.execute(query)
        user_config = result.scalar_one_or_none()

        # 确定汇率和费率
        exchange_rate = withdraw_info['exchange_rate'] or \
                       (user_config.exchange_rate if user_config else None) or \
                       group.exchange_rate

        fee_rate = withdraw_info['fee_rate'] or \
                  (user_config.fee_rate if user_config else None) or \
                  group.fee_rate

        # 创建交易记录
        transaction = await BillingService.create_transaction(
            db=db,
            group_id=chat_id,
            user_id=target_user_id,
            username=target_username,
            first_name=target_first_name,
            operator_id=user.id,
            operator_username=user.username,
            operator_first_name=user.first_name,
            transaction_type='withdraw',
            amount=withdraw_info['amount'],
            currency=withdraw_info['currency'],
            exchange_rate=exchange_rate if withdraw_info['currency'] == 'USDT' else None,
            fee_rate=fee_rate,
            note=withdraw_info['note'],
            message_id=update.message.message_id,
            reply_to_message_id=update.message.reply_to_message.message_id if update.message.reply_to_message else None
        )

        # 格式化回复消息
        reply_message = Formatter.format_transaction(
            transaction,
            display_mode=group.display_mode,
            currency_mode=group.currency_mode
        )

        # 发送确认消息
        sent_message = await update.message.reply_text(f"✅ 下发成功\n\n{reply_message}")

        # 如果开启置顶，置顶消息
        if group.pin_enabled:
            try:
                await sent_message.pin(disable_notification=True)
            except Exception:
                pass


async def handle_storage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理寄存操作"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查记账是否开启
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group or not group.is_active:
            return

        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 解析寄存命令
        storage_info = CommandParser.parse_storage(text)

        if not storage_info:
            return

        # 确定金额（加或减）
        amount = storage_info['amount'] if storage_info['operation'] == '+' else -storage_info['amount']

        # 创建交易记录
        transaction = await BillingService.create_transaction(
            db=db,
            group_id=chat_id,
            user_id=user.id,
            username=user.username,
            first_name=user.first_name,
            operator_id=user.id,
            operator_username=user.username,
            operator_first_name=user.first_name,
            transaction_type='storage',
            amount=amount,
            currency='CNY',
            note=storage_info['note'],
            message_id=update.message.message_id
        )

        operation_text = "增加" if storage_info['operation'] == '+' else "减少"
        await update.message.reply_text(f"✅ 寄存{operation_text}成功: ¥{abs(amount):.2f}")


async def show_bills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示账单"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        # 获取群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            await update.message.reply_text("❌ 未找到群组配置")
            return

        # 获取入款记录
        deposits = await BillingService.get_transactions(
            db=db,
            group_id=chat_id,
            transaction_type='deposit',
            limit=group.deposit_display_count
        )

        # 获取下发记录
        withdraws = await BillingService.get_transactions(
            db=db,
            group_id=chat_id,
            transaction_type='withdraw',
            limit=group.withdraw_display_count
        )

        # 格式化消息
        message_parts = []

        if deposits:
            deposit_msg = Formatter.format_transaction_list(
                deposits,
                title=f"最近{len(deposits)}条入款",
                display_mode=group.display_mode,
                currency_mode=group.currency_mode
            )
            message_parts.append(deposit_msg)

        if withdraws:
            withdraw_msg = Formatter.format_transaction_list(
                withdraws,
                title=f"最近{len(withdraws)}条下发",
                display_mode=group.display_mode,
                currency_mode=group.currency_mode
            )
            message_parts.append(withdraw_msg)

        if not message_parts:
            message_parts.append("📋 暂无账单记录")

        await update.message.reply_text("\n\n".join(message_parts))


async def show_all_bills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示全部账单"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        # 获取群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            await update.message.reply_text("❌ 未找到群组配置")
            return

        # 获取所有交易记录
        transactions = await BillingService.get_transactions(
            db=db,
            group_id=chat_id,
            limit=50  # 限制50条
        )

        # 格式化消息
        message = Formatter.format_transaction_list(
            transactions,
            title="全部账单（最近50条）",
            display_mode=group.display_mode,
            currency_mode=group.currency_mode
        )

        await update.message.reply_text(message)


async def show_summary(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示账单汇总"""
    if not update.message or not update.effective_chat:
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        # 计算汇总
        summary = await BillingService.calculate_summary(
            db=db,
            group_id=chat_id
        )

        # 格式化消息
        message = Formatter.format_summary(summary)

        await update.message.reply_text(message)


async def show_my_bills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示我的账单"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id

    async for db in get_db():
        # 获取群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            await update.message.reply_text("❌ 未找到群组配置")
            return

        # 获取用户交易记录
        transactions = await BillingService.get_user_transactions(
            db=db,
            group_id=chat_id,
            user_id=user_id,
            limit=20
        )

        # 格式化消息
        message = Formatter.format_transaction_list(
            transactions,
            title="我的账单",
            display_mode=group.display_mode,
            currency_mode=group.currency_mode
        )

        await update.message.reply_text(message)


async def revoke_deposit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """撤销最后一条入款"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 获取最后一条入款记录
        transaction = await BillingService.get_latest_transaction(
            db=db,
            group_id=chat_id,
            transaction_type='deposit'
        )

        if not transaction:
            await update.message.reply_text("❌ 没有可撤销的入款记录")
            return

        # 标记为已删除
        await BillingService.delete_transaction(db, transaction.id)

        await update.message.reply_text(f"✅ 已撤销入款: ¥{transaction.amount:.2f}")


async def revoke_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """撤销最后一条下发"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 获取最后一条下发记录
        transaction = await BillingService.get_latest_transaction(
            db=db,
            group_id=chat_id,
            transaction_type='withdraw'
        )

        if not transaction:
            await update.message.reply_text("❌ 没有可撤销的下发记录")
            return

        # 标记为已删除
        await BillingService.delete_transaction(db, transaction.id)

        await update.message.reply_text(f"✅ 已撤销下发: ¥{transaction.amount:.2f}")


async def delete_bills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """删除账单"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 删除所有账单
        count = await BillingService.delete_all_transactions(db, chat_id)

        await update.message.reply_text(f"✅ 已删除 {count} 条账单记录")


async def save_bills(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """保存账单"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    chat_id = update.effective_chat.id
    user = update.effective_user

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 保存账单
        daily_summary = await BillingService.save_bills(db, chat_id)

        # 格式化汇总消息
        summary_dict = {
            'deposit_count': daily_summary.total_deposit_count,
            'deposit_amount': daily_summary.total_deposit_amount,
            'deposit_cny': daily_summary.total_deposit_cny,
            'withdraw_count': daily_summary.total_withdraw_count,
            'withdraw_amount': daily_summary.total_withdraw_amount,
            'withdraw_cny': daily_summary.total_withdraw_cny,
            'storage_amount': daily_summary.total_storage_amount,
            'total_fee': daily_summary.total_fee_amount,
            'net_amount': daily_summary.net_amount
        }

        message = Formatter.format_summary(summary_dict, title="账单已保存")

        await update.message.reply_text(message)
