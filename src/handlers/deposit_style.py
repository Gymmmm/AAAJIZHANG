"""Per-bot, per-group deposit display settings using existing configuration storage."""
import json
from types import SimpleNamespace
from datetime import datetime
from sqlalchemy import select
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, ForceReply
from telegram.ext import ApplicationHandlerStop
from ..models import SystemConfig, Group, get_db
from .operator import is_operator
from ..utils.deposit_style import STYLES, render_deposit, validate_template

async def load_style(db, bot_id, group_id):
    row = (await db.execute(select(SystemConfig).where(
        SystemConfig.key == f'deposit_style:{bot_id}:{group_id}'))).scalar_one_or_none()
    if row:
        try:
            data = json.loads(row.value)
            if isinstance(data, dict):
                return data
        except (ValueError, TypeError):
            pass
    return None

async def save_style(db, bot_id, group_id, value):
    key = f'deposit_style:{bot_id}:{group_id}'
    row = (await db.execute(select(SystemConfig).where(SystemConfig.key == key))).scalar_one_or_none()
    if row is None:
        row = SystemConfig(key=key, value='{}', is_public=False)
        db.add(row)
    row.value = json.dumps(value, ensure_ascii=False)
    await db.commit()

async def allowed(update, context, db):
    gid = update.effective_chat.id
    group = (await db.execute(select(Group).where(Group.group_id == gid))).scalar_one_or_none()
    return group is not None and await is_operator(update.effective_user.id, gid, db)

def panel(style):
    name = '⚙️ 自定义版' if style and style.get('name') == 'custom' else STYLES.get((style or {}).get('name'), ('原有样式', ''))[0]
    lines = ['📊 入款账单样式配置', '┆', f'└ 当前样式：{name}', '', '选择新的样式：']
    sample = SimpleNamespace(transaction_date=datetime(2026,10,31,7,23), amount=1000,
        exchange_rate=7.2, fee_rate=2, final_amount=980, currency='CNY',
        first_name='张三', username=None, user_id=1, operator_first_name='李四', operator_username=None, operator_id=2)
    for key, (label, _) in STYLES.items():
        lines.extend(['', label + '：', render_deposit(sample, {'name': key})])
    lines.extend(['', '⚙️ 自定义版：点击下方按钮输入自定义模板', '可用变量：{time} {money} {username} {signname} {rate_calc} {usum}',
        'username：入账人；signname：操作人；usum：扣费后U金额。', '仅更改展示，不修改账目、汇率或费率。'])
    buttons = [[InlineKeyboardButton(label, callback_data='depstyle:' + key)] for key, (label, _) in STYLES.items()]
    buttons.append([InlineKeyboardButton('⚙️ 自定义版', callback_data='depstyle:custom')])
    return '\n'.join(lines), InlineKeyboardMarkup(buttons)

async def show_style(update, context):
    async for db in get_db():
        if not await allowed(update, context, db):
            await update.effective_message.reply_text('❌ 请先开启记账，并使用操作人账号配置。')
            return
        body, keyboard = panel(await load_style(db, context.bot.id, update.effective_chat.id))
        await update.effective_message.reply_text(body, reply_markup=keyboard)

async def choose_style(update, context):
    query = update.callback_query
    async for db in get_db():
        if not await allowed(update, context, db):
            await query.answer('您没有操作权限', show_alert=True)
            return
        key = query.data.removeprefix('depstyle:')
        if key not in STYLES and key != 'custom':
            await query.answer('无效样式', show_alert=True)
            return
        await query.answer()
        if key == 'custom':
            prompt = await query.message.reply_text('请回复本条消息输入模板（最多300字），发送「取消」放弃。\n示例：{time} {money} | {usum}U {username}\n变量：{time} {money} {username} {signname} {rate_calc} {usum}', reply_markup=ForceReply(selective=True))
            context.user_data['deposit_template_prompt'] = (update.effective_chat.id, prompt.message_id)
            return
        await save_style(db, context.bot.id, update.effective_chat.id, {'name': key})
        context.user_data.pop('deposit_template_prompt', None)
        body, keyboard = panel({'name': key})
        await query.message.reply_text('✅ 已应用到本群入款账单。\n\n' + body, reply_markup=keyboard)

async def receive_template(update, context):
    msg = update.effective_message
    pending = context.user_data.get('deposit_template_prompt')
    if not msg or not msg.reply_to_message or pending != (update.effective_chat.id, msg.reply_to_message.message_id):
        return
    if msg.text.strip() == '取消':
        context.user_data.pop('deposit_template_prompt', None)
        await msg.reply_text('已取消，原样式保持不变。')
        raise ApplicationHandlerStop
    async for db in get_db():
        if not await allowed(update, context, db):
            await msg.reply_text('❌ 您没有操作权限')
            raise ApplicationHandlerStop
        try:
            template = validate_template(msg.text)
        except ValueError as error:
            await msg.reply_text(str(error) + '\n请继续回复原提示消息重试，或发送「取消」。')
            raise ApplicationHandlerStop
        await save_style(db, context.bot.id, update.effective_chat.id, {'name':'custom', 'template':template})
        context.user_data.pop('deposit_template_prompt', None)
        await msg.reply_text('✅ 自定义模板已应用到本群入款账单。')
    raise ApplicationHandlerStop
