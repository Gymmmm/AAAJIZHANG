"""
查询和辅助功能处理器
"""
from telegram import Update
from telegram.ext import ContextTypes
import httpx
import re
from datetime import datetime
from math import radians, cos, sin, asin, sqrt

from ..services.exchange_service import ExchangeService
from ..utils.parser import CommandParser
from ..utils.calculator import Calculator

# 简单省份映射（前2位）
PROVINCE_MAP = {
    '11': '北京市', '12': '天津市', '13': '河北省', '14': '山西省', '15': '内蒙古自治区',
    '21': '辽宁省', '22': '吉林省', '23': '黑龙江省',
    '31': '上海市', '32': '江苏省', '33': '浙江省', '34': '安徽省', '35': '福建省', '36': '江西省', '37': '山东省',
    '41': '河南省', '42': '湖北省', '43': '湖南省', '44': '广东省', '45': '广西壮族自治区', '46': '海南省',
    '50': '重庆市', '51': '四川省', '52': '贵州省', '53': '云南省', '54': '西藏自治区',
    '61': '陕西省', '62': '甘肃省', '63': '青海省', '64': '宁夏回族自治区', '65': '新疆维吾尔自治区',
    '71': '台湾省', '81': '香港特别行政区', '82': '澳门特别行政区'
}

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

async def query_gold_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询黄金价格"""
    if not update.message:
        return
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 使用免费公开接口
            resp = await client.get("https://xaus.com/api/v1/spot")
            if resp.status_code == 200:
                data = resp.json()
                price = data.get("spot_usd_oz") or data.get("xau", {}).get("price")
                if price:
                    await update.message.reply_text(f"🪙 黄金价格: ${float(price):.2f} / 盎司")
                    return
    except Exception:
        pass
    await update.message.reply_text("❌ 获取黄金价格失败")

async def query_id_card(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查身份证（仅校验格式 + 省份/生日/性别，无个人数据查询）"""
    if not update.message:
        return
    text = update.message.text.strip()
    match = re.match(r'^(查)?(\d{17}[\dXx])$', text)
    if not match:
        return
    id_num = match.group(2).upper()
    if len(id_num) != 18:
        await update.message.reply_text("❌ 身份证号必须为18位")
        return

    # 校验码验证
    weights = [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]
    check_codes = '10X98765432'
    total = sum(int(id_num[i]) * weights[i] for i in range(17))
    expected = check_codes[total % 11]
    if id_num[17] != expected:
        await update.message.reply_text("❌ 身份证校验码错误")
        return

    province = PROVINCE_MAP.get(id_num[:2], '未知省份')
    birthday = f"{id_num[6:10]}-{id_num[10:12]}-{id_num[12:14]}"
    sex = '男' if int(id_num[16]) % 2 == 1 else '女'

    msg = (
        f"📄 身份证解析\n"
        f"省份：{province}\n"
        f"生日：{birthday}\n"
        f"性别：{sex}\n"
        f"（仅格式校验，不查询个人信息）"
    )
    await update.message.reply_text(msg)

async def query_trc20_address(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询TRC20地址信息"""
    if not update.message:
        return
    text = update.message.text.strip()
    if not CommandParser.is_trc20_address(text):
        return
    address_info = await ExchangeService.get_tron_address_info(text)
    if address_info:
        message = await ExchangeService.format_tron_address_info(address_info)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❌ 获取地址信息失败")

async def query_trc20_transactions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询TRC20地址交易记录（查U记录）"""
    if not update.message:
        return
    text = update.message.text.strip()
    if update.message.reply_to_message:
        text = update.message.reply_to_message.text.strip()
    if not CommandParser.is_trc20_address(text):
        await update.message.reply_text("❌ 请提供有效的TRC20地址")
        return
    transactions = await ExchangeService.get_tron_transactions(text)
    if transactions:
        message = await ExchangeService.format_tron_transactions(transactions)
        await update.message.reply_text(message)
    else:
        await update.message.reply_text("❌ 获取交易记录失败")

async def query_fiat_rate(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """查询法币汇率（自定义币种）"""
    if not update.message:
        return
    text = update.message.text.strip()
    # 法币汇率CNY 或 法币汇率 USD
    match = re.match(r'^法币汇率\s*([A-Za-z]{3})$', text, re.IGNORECASE)
    if not match:
        await update.message.reply_text("格式：法币汇率CNY")
        return
    currency = match.group(1).upper()
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            # 使用免费汇率接口
            resp = await client.get(f"https://api.exchangerate-api.com/v4/latest/USDT")
            if resp.status_code == 200:
                data = resp.json()
                rate = data.get("rates", {}).get(currency)
                if rate:
                    await update.message.reply_text(f"💱 {currency} 汇率: 1 USDT = {rate:.4f} {currency}")
                    return
    except Exception:
        pass
    await update.message.reply_text(f"❌ 获取 {currency} 汇率失败")

async def query_distance(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """两地距离（回复带地址的消息）"""
    if not update.message or not update.message.reply_to_message:
        await update.message.reply_text("请回复带地址的消息后发送两地距离")
        return
    addr1 = update.message.reply_to_message.text.strip()
    addr2 = update.message.text.replace("两地距离", "").strip()
    if not addr2:
        await update.message.reply_text("请在命令后填写目标地址")
        return
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            # 简单地理编码（使用 Nominatim）
            async def geocode(addr):
                r = await client.get(
                    "https://nominatim.openstreetmap.org/search",
                    params={"q": addr, "format": "json", "limit": 1},
                    headers={"User-Agent": "AAAJIZHANG-Bot"}
                )
                if r.status_code == 200 and r.json():
                    d = r.json()[0]
                    return float(d["lat"]), float(d["lon"])
                return None, None
            lat1, lon1 = await geocode(addr1)
            lat2, lon2 = await geocode(addr2)
            if lat1 and lat2:
                # Haversine
                lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])
                dlon = lon2 - lon1
                dlat = lat2 - lat1
                a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                c = 2 * asin(sqrt(a))
                km = 6371 * c
                await update.message.reply_text(f"📍 距离约 {km:.1f} 公里")
                return
    except Exception:
        pass
    await update.message.reply_text("❌ 无法解析地址或计算距离")

async def broadcast_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """群发广播（基础版：向当前群发送广播内容）"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    from sqlalchemy import select
    from ..models import Group, get_db
    from .operator import is_operator
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text
    async for db in get_db():
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        content = text.removeprefix("群发广播").strip()
        if not content:
            await update.message.reply_text("格式：群发广播 内容")
            return
        try:
            await context.bot.send_message(chat_id, f"📢 广播：{content}")
            await update.message.reply_text("✅ 广播已发送")
        except Exception as e:
            await update.message.reply_text(f"❌ 发送失败: {e}")

async def calculate_expression(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """计算功能"""
    if not update.message:
        return
    text = update.message.text.strip()
    if text.startswith("计算"):
        expression = text[2:].strip()
    else:
        return
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
        member_count = await context.bot.get_chat_member_count(update.effective_chat.id)
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
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            await update.message.reply_text("❌ 请提供分组标签")
            return
        tag = parts[1].strip()
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()
        if group:
            group.group_tag = tag
            await db.commit()
            await update.message.reply_text(f"✅ 已设置分组为: {tag}")
        else:
            await update.message.reply_text("❌ 未找到群组配置")

async def set_business_mode(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """设置代收/代付模式"""
    if not update.message or not update.effective_chat or not update.effective_user:
        return
    from sqlalchemy import select
    from ..models import Group, get_db
    from .operator import is_operator
    chat_id = update.effective_chat.id
    user = update.effective_user
    text = update.message.text.strip()
    async for db in get_db():
        if not await is_operator(user.id, chat_id, db):
            await update.message.reply_text("❌ 您没有操作权限")
            return
        group = (await db.execute(select(Group).where(Group.group_id == chat_id))).scalar_one_or_none()
        if not group:
            await update.message.reply_text("❌ 未找到群组配置")
            return
        if text == "设置代收":
            group.group_tag = "代收"
            await db.commit()
            await update.message.reply_text("✅ 已设置为代收模式")
        elif text == "设置代付":
            group.group_tag = "代付"
            await db.commit()
            await update.message.reply_text("✅ 已设置为代付模式")

async def stop_trading(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """拉停警示"""
    if not update.message:
        return
    await update.message.reply_text("⛔️ 拉停！请暂停业务，等待进一步通知。")
