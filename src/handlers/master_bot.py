"""
父机器人（主Bot）处理器 - 用于用户购买和管理
"""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import select
from datetime import datetime, timedelta
import secrets

from ..models import User, Order, BotInstance, OrderStatus, get_db
from ..web.auth import generate_username, generate_random_password, get_password_hash
from ..services.payment_service import PaymentService
from ..services.bot_manager import bot_manager

# 对话状态
WAITING_BOT_TOKEN = 1


async def start_master(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """主Bot开始命令"""
    if not update.message or not update.effective_user:
        return

    user = update.effective_user

    # 欢迎消息
    welcome_text = f"""
🤖 <b>欢迎使用飞机记账机器人 SaaS 平台</b>

您好 {user.first_name}！

本平台提供专业的Telegram记账机器人服务：
✅ 完整的记账功能
✅ 多群组管理
✅ 自定义汇率和费率
✅ 网页后台管理
✅ 实时账单统计

<b>价格方案：</b>
📦 月付：10 USDT/月
📦 年付：100 USDT/年（节省20 USDT）
📦 永久：300 USDT（一次付费，永久使用）

请选择您需要的操作：
"""

    keyboard = [
        [InlineKeyboardButton("💳 购买服务", callback_data="buy_service")],
        [InlineKeyboardButton("🤖 创建机器人", callback_data="create_bot")],
        [InlineKeyboardButton("📊 我的机器人", callback_data="my_bots")],
        [InlineKeyboardButton("👤 个人中心", callback_data="user_center")],
        [InlineKeyboardButton("❓ 帮助", callback_data="help")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text(
        welcome_text,
        parse_mode='HTML',
        reply_markup=reply_markup
    )


async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """按钮回调处理"""
    query = update.callback_query
    await query.answer()

    if not update.effective_user:
        return

    telegram_user = update.effective_user
    callback_data = query.data

    async for db in get_db():
        # 查找或创建用户
        query_user = select(User).where(User.telegram_id == telegram_user.id)
        result = await db.execute(query_user)
        user = result.scalar_one_or_none()

        if not user:
            # 自动创建用户
            username = generate_username(telegram_user.id)
            password = generate_random_password()

            user = User(
                username=username,
                password_hash=get_password_hash(password),
                telegram_id=telegram_user.id,
                telegram_username=telegram_user.username,
                telegram_first_name=telegram_user.first_name,
                role="tenant"
            )
            db.add(user)
            await db.commit()
            await db.refresh(user)

            # 发送登录凭据
            credentials_text = f"""
✅ <b>账户创建成功！</b>

您的登录凭据：
👤 用户名: <code>{username}</code>
🔑 密码: <code>{password}</code>

🌐 管理后台: http://your-domain.com/dashboard
（请保存好您的登录信息）
"""
            await query.message.reply_text(credentials_text, parse_mode='HTML')

        # 处理不同的回调
        if callback_data == "buy_service":
            await show_pricing_plans(query, user, db)
        elif callback_data == "create_bot":
            await start_create_bot(query, user, db, context)
        elif callback_data == "my_bots":
            await show_my_bots(query, user, db)
        elif callback_data == "user_center":
            await show_user_center(query, user, db)
        elif callback_data == "help":
            await show_help(query)
        elif callback_data.startswith("buy_"):
            await handle_buy_plan(query, user, db, callback_data)


async def show_pricing_plans(query, user: User, db):
    """显示价格方案"""
    text = """
💰 <b>选择您的订阅方案</b>

所有方案包含完整功能：
✅ 无限群组
✅ 无限交易记录
✅ 网页后台管理
✅ 实时账单统计
✅ 定时日切
✅ 多种显示模式

请选择：
"""

    keyboard = [
        [InlineKeyboardButton("📅 月付 - 10 USDT/月", callback_data="buy_monthly")],
        [InlineKeyboardButton("📆 年付 - 100 USDT/年", callback_data="buy_yearly")],
        [InlineKeyboardButton("♾️ 永久 - 300 USDT", callback_data="buy_lifetime")],
        [InlineKeyboardButton("« 返回", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)


async def handle_buy_plan(query, user: User, db, callback_data: str):
    """处理购买方案"""
    plan_map = {
        "buy_monthly": ("月付", 10, "monthly", 30),
        "buy_yearly": ("年付", 100, "yearly", 365),
        "buy_lifetime": ("永久", 300, "lifetime", 36500),
    }

    if callback_data not in plan_map:
        return

    plan_name, price, plan_type, days = plan_map[callback_data]

    # 创建订单
    order_no = f"ORD{int(datetime.now().timestamp())}{secrets.token_hex(4)}"
    order = Order(
        order_no=order_no,
        user_id=user.id,
        product_name=f"记账机器人服务 - {plan_name}",
        product_type=plan_type,
        price=price,
        status=OrderStatus.PENDING,
        expires_at=datetime.utcnow() + timedelta(hours=24)  # 24小时内有效
    )
    db.add(order)
    await db.commit()
    await db.refresh(order)

    # 创建支付订单
    try:
        notify_url = "http://your-domain.com/api/payment/callback"
        payment_result = await PaymentService.create_payment_order(
            db=db,
            order=order,
            notify_url=notify_url
        )

        if payment_result.get("code") == 200:
            payment_url = payment_result["data"].get("payment_url")
            payment_address = payment_result["data"].get("payment_address")

            text = f"""
📋 <b>订单创建成功</b>

订单号: <code>{order_no}</code>
商品: {plan_name}
金额: {price} USDT

💳 <b>支付方式：</b>
请向以下地址转账 {price} USDT (TRC20)

地址: <code>{payment_address}</code>

⚠️ <b>注意事项：</b>
1. 请使用TRC20网络转账
2. 转账金额必须完全匹配
3. 订单24小时内有效
4. 支付后自动激活服务

<a href="{payment_url}">点击此处支付</a>
"""
        else:
            text = f"❌ 创建支付订单失败: {payment_result.get('msg', '未知错误')}"

    except Exception as e:
        text = f"❌ 创建支付订单失败: {str(e)}"

    keyboard = [[InlineKeyboardButton("« 返回", callback_data="buy_service")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)


async def start_create_bot(query, user: User, db, context: ContextTypes.DEFAULT_TYPE):
    """开始创建机器人"""
    # 检查订阅状态
    if not user.subscription_expires or user.subscription_expires < datetime.utcnow():
        text = "❌ 您的订阅已过期，请先购买服务。"
        keyboard = [[InlineKeyboardButton("💳 购买服务", callback_data="buy_service")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    # 检查机器人数量限制
    query_bots = select(BotInstance).where(BotInstance.user_id == user.id)
    result = await db.execute(query_bots)
    user_bots = result.scalars().all()

    if len(user_bots) >= user.max_bots:
        text = f"❌ 您已达到机器人数量上限（{user.max_bots}个）"
        keyboard = [[InlineKeyboardButton("« 返回", callback_data="back_to_main")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(text, reply_markup=reply_markup)
        return

    # 请求Bot Token
    text = """
🤖 <b>创建新的记账机器人</b>

请按照以下步骤操作：

1️⃣ 在Telegram中找到 @BotFather
2️⃣ 发送 /newbot 创建新机器人
3️⃣ 按照提示设置机器人名称
4️⃣ 复制BotFather给你的Token
5️⃣ 将Token发送给我

<b>Token格式示例：</b>
<code>1234567890:ABCdefGHIjklMNOpqrsTUVwxyz</code>

请发送您的Bot Token：
"""

    await query.edit_message_text(text, parse_mode='HTML')
    return WAITING_BOT_TOKEN


async def receive_bot_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """接收Bot Token"""
    if not update.message or not update.effective_user:
        return ConversationHandler.END

    bot_token = update.message.text.strip()
    telegram_user = update.effective_user

    async for db in get_db():
        # 查找用户
        query_user = select(User).where(User.telegram_id == telegram_user.id)
        result = await db.execute(query_user)
        user = result.scalar_one_or_none()

        if not user:
            await update.message.reply_text("❌ 用户不存在")
            return ConversationHandler.END

        # 验证Token格式
        if not bot_token or ':' not in bot_token:
            await update.message.reply_text("❌ Token格式不正确，请重新发送")
            return WAITING_BOT_TOKEN

        try:
            # 创建机器人实例
            await update.message.reply_text("⏳ 正在创建机器人实例，请稍候...")

            bot_instance = await bot_manager.create_instance(
                db=db,
                user_id=user.id,
                bot_token=bot_token
            )

            # 启动机器人
            success = await bot_manager.start_instance(db, bot_instance.id)

            if success:
                text = f"""
✅ <b>机器人创建成功！</b>

🤖 机器人: @{bot_instance.bot_username}
📛 名称: {bot_instance.bot_name}
🆔 实例ID: {bot_instance.id}

您现在可以：
1. 将机器人添加到群组
2. 发送 /start 开始使用
3. 访问网页后台管理

🌐 管理后台: http://your-domain.com/dashboard
"""
            else:
                text = "❌ 机器人启动失败，请稍后重试"

        except Exception as e:
            text = f"❌ 创建失败: {str(e)}"

        await update.message.reply_text(text, parse_mode='HTML')
        return ConversationHandler.END


async def show_my_bots(query, user: User, db):
    """显示我的机器人"""
    # 获取用户的机器人实例
    user_bots = await bot_manager.get_user_instances(db, user.id)

    if not user_bots:
        text = "您还没有创建任何机器人\n\n请先购买服务并创建机器人。"
        keyboard = [
            [InlineKeyboardButton("🤖 创建机器人", callback_data="create_bot")],
            [InlineKeyboardButton("« 返回", callback_data="back_to_main")],
        ]
    else:
        text = f"<b>我的机器人列表</b>\n\n共 {len(user_bots)} 个机器人:\n\n"

        keyboard = []
        for bot in user_bots:
            status_emoji = {
                "running": "🟢",
                "stopped": "🔴",
                "creating": "🟡",
                "error": "⚠️"
            }.get(bot.status, "⚪")

            text += f"{status_emoji} @{bot.bot_username} ({bot.status})\n"
            keyboard.append([
                InlineKeyboardButton(
                    f"管理 @{bot.bot_username}",
                    callback_data=f"manage_bot_{bot.id}"
                )
            ])

        keyboard.append([InlineKeyboardButton("« 返回", callback_data="back_to_main")])

    reply_markup = InlineKeyboardMarkup(keyboard)
    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)


async def show_user_center(query, user: User, db):
    """显示个人中心"""
    subscription_status = "✅ 有效" if user.subscription_expires and user.subscription_expires > datetime.utcnow() else "❌ 已过期"
    expires_date = user.subscription_expires.strftime("%Y-%m-%d") if user.subscription_expires else "未订阅"

    text = f"""
👤 <b>个人中心</b>

用户名: <code>{user.username}</code>
Telegram: @{user.telegram_username or 'N/A'}

📊 <b>订阅信息</b>
状态: {subscription_status}
到期时间: {expires_date}
机器人额度: {user.max_bots}

🌐 <b>管理后台</b>
访问: http://your-domain.com/dashboard
用户名: <code>{user.username}</code>
（如忘记密码，请联系管理员）
"""

    keyboard = [
        [InlineKeyboardButton("💳 续费", callback_data="buy_service")],
        [InlineKeyboardButton("« 返回", callback_data="back_to_main")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)


async def show_help(query):
    """显示帮助"""
    text = """
❓ <b>帮助信息</b>

<b>1. 如何开始？</b>
• 购买服务订阅
• 创建机器人实例
• 将机器人添加到群组
• 开始记账

<b>2. 如何创建机器人？</b>
• 找到 @BotFather
• 发送 /newbot
• 按提示创建
• 将Token发送给我

<b>3. 如何使用记账功能？</b>
• 详见机器人的 /help 命令
• 或访问网页后台查看文档

<b>4. 遇到问题？</b>
• 检查订阅是否有效
• 确认机器人状态正常
• 联系客服: @your_support

<b>5. 网页后台</b>
• 地址: http://your-domain.com
• 使用您的用户名和密码登录
"""

    keyboard = [[InlineKeyboardButton("« 返回", callback_data="back_to_main")]]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await query.edit_message_text(text, parse_mode='HTML', reply_markup=reply_markup)
