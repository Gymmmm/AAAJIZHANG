"""
查询和辅助功能处理器
"""
from telegram import Update
from telegram.ext import ContextTypes

from ..services.exchange_service import ExchangeService
from ..utils.parser import CommandParser
from ..utils.calculator import Calculator


async def query_huobi_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询火币U价"""
    if not update.message:
        return

    price = await ExchangeService.get_huobi_usdt_price()

    if price:
        await update.message.reply_text(f"🔥 火币 USDT 价格: ¥{price:.4f}")
    else:
        await update.message.reply_text("❌ 获取火币价格失败")


async def query_okex_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询欧易U价"""
    if not update.message:
        return

    price = await ExchangeService.get_okex_usdt_price()

    if price:
        await update.message.reply_text(f"💰 欧易 USDT 价格: ¥{price:.4f}")
    else:
        await update.message.reply_text("❌ 获取欧易价格失败")


async def query_trc20_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询TRC20地址信息"""
    if not update.message:
        return

    text = update.message.text.strip()

    # 检查是否为TRC20地址
    if not CommandParser.is_trc20_address(text):
        return

    # 获取地址信息
    address_info = await ExchangeService.get_tron_address_info(text)

    if address_info:
        message = await ExchangeService.format_tron_address_info(address_info)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❌ 获取地址信息失败")


async def query_trc20_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询TRC20地址交易记录"""
    if not update.message:
        return

    text = update.message.text.strip()

    # 从回复消息中获取地址
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text.strip()

    # 检查是否为TRC20地址
    if not CommandParser.is_trc20_address(text):
        await update.message.reply_text("❌ 请提供有效的TRC20地址")
        return

    # 获取交易记录
    transactions = await ExchangeService.get_tron_transactions(text)

    if transactions:
        message = await ExchangeService.format_tron_transactions(transactions)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❌ 获取交易记录失败")


async def calculate_expression(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """计算功能"""
    if not update.message:
        return

    text = update.message.text.strip()

    # 提取表达式（去掉"计算"等前缀）
    if text.startswith("计算"):
        expression = text[2:].strip()
    else:
        return

    # 计算结果
    result = Calculator.evaluate_expression(expression)

    if result is not None:
        await update.message.reply_text(f"💡 计算结果: {expression} = {result}")
    else:
        await update.message.reply_text("❌ 表达式格式错误")


async def mention_all(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """通知所有人（@all）"""
    if not update.message or not update.effective_chat:
        return

    try:
        # 获取群组成员数量
        chat = await context.bot.get_chat(update.effective_chat.id)
        member_count = await context.bot.get_chat_member_count(update.effective_chat.id)

        # 发送通知消息
        message = f"📢 群组通知\n\n全体成员请注意！（{member_count} 人）"

        await update.message.reply_text(message)

    except Exception as e:
        await update.message.reply_text(f"❌ 操作失败: {str(e)}")


async def set_group_tag(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置分组标签"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return

    from sqlalchemy import select
    from ..models import Group, get_db
    from .operator import is_operator

    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text

    async for db in get_db():
        # 检查操作权限
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return

        # 提取标签
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("❌ 请提供分组标签")
            return

        tag = parts[1].strip()

        # 更新群组配置
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.group_tag = tag
            await db.commit()
            await update.message.reply_text(f"✅ 已设置分组为: {tag}")
        else:
            await update.message.reply_text("❌ 未找到群组配置")
