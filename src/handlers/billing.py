"""Ledger handlers. Original messages and bot receipts address the same entry."""
import json
from decimal import Decimal
from telegram import Update
from telegram.ext import ContextTypes
from sqlalchemy import select
from ..models import Group, UserConfig, get_db, LedgerAudit
from ..services.billing_service import BillingService
from ..services.identity import resolve_user
from ..utils.parser import CommandParser
from ..utils.formatter import Formatter
from ..utils.calculator import Calculator
from .operator import is_operator

async def target_user(update, db, name=None):
    if name:
        return await resolve_user(db, update.effective_chat.id, name)
    reply = update.message.reply_to_message
    if reply and reply.from_user and not reply.from_user.is_bot:
        return reply.from_user
    return update.effective_user

async def _record(update, context, kind, correction=False):
    if not update.message or not update.effective_user:
        return
    msg, user, gid = update.message, update.effective_user, update.effective_chat.id
    try:
        info = (CommandParser.parse_correction(msg.text) if correction else
                CommandParser.parse_storage(msg.text) if kind == 'storage' else
                CommandParser.parse_withdraw(msg.text) if kind == 'withdraw' else
                CommandParser.parse_deposit(msg.text))
        if not info:
            await msg.reply_text('格式不正确。入款：+1000；下发：下发1000；USDT 金额加 u；单笔费率用 *3%（3%）。')
            return
        async for db in get_db():
            group = (await db.execute(select(Group).where(Group.group_id == gid))).scalar_one_or_none()
            if not group or not group.is_active:
                await msg.reply_text('记账尚未开启，请管理员发送「开始」。')
                return
            if not await is_operator(user.id, gid, db):
                await msg.reply_text('❌ 您没有操作权限')
                return
            target = await target_user(update, db, info.get('username'))
            personal = (await db.execute(select(UserConfig).where(UserConfig.group_id == gid,
                UserConfig.user_id == target.id))).scalar_one_or_none()
            def effective(key):
                value = info.get(key)
                if value is None and personal:
                    value = getattr(personal, key)
                return value if value is not None else getattr(group, key)
            amount = info['amount']
            currency = info.get('currency', 'CNY')
            if kind == 'storage':
                amount *= 1 if info['operation'] == '+' else -1
            rate = effective('exchange_rate')
            fee = effective('fee_rate') if kind != 'storage' else Decimal(0)
            trans = await BillingService.create_transaction(db=db, group_id=gid,
                user_id=target.id, username=target.username, first_name=target.first_name,
                operator_id=user.id, operator_username=user.username, operator_first_name=user.first_name,
                transaction_type=kind, amount=amount, currency=currency,
                exchange_rate=rate, fee_rate=fee, note=info['note'], message_id=msg.message_id,
                reply_to_message_id=msg.reply_to_message.message_id if msg.reply_to_message else None,
                is_correction=correction)
            if trans is None:
                await msg.reply_text('这条消息已经记账，不会重复入账。')
                return
            label = {'deposit':'入款','withdraw':'下发','storage':'寄存'}[kind]
            sent = await msg.reply_text(f'✅ {label}{"修正" if correction else "成功"} · #{trans.id}\n\n' +
                Formatter.format_transaction(trans, group.display_mode, group.currency_mode) +
                '\n\n回复本条或原消息发送「撤销」；恢复请发送「撤销恢复」。')
            await BillingService.bind_reply(db, trans, sent.message_id)
            if group.pin_enabled:
                try:
                    await sent.pin(disable_notification=True)
                except Exception:
                    await msg.reply_text('记账已保存；置顶失败，请检查机器人置顶权限。')
    except ValueError as error:
        await msg.reply_text(str(error))

async def handle_deposit(update, context):
    await _record(update, context, 'deposit')

async def handle_withdraw(update, context):
    await _record(update, context, 'withdraw')

async def handle_storage(update, context):
    await _record(update, context, 'storage')

async def handle_correction(update, context):
    await _record(update, context, 'withdraw' if update.message.text.startswith('下发-') else 'deposit', True)

async def _show(update, context, history=False, personal=False):
    gid = update.effective_chat.id
    async for db in get_db():
        group = (await db.execute(select(Group).where(Group.group_id == gid))).scalar_one_or_none()
        if not group:
            await update.message.reply_text('请管理员先发送「开始」。')
            return
        # Querying another person's account requires ledger operator privileges.
        name = update.message.text.removeprefix('查账单').strip() if update.message.text.startswith('查账单') else None
        target = await target_user(update, db, name) if personal else None
        if target and target.id != update.effective_user.id and not await is_operator(update.effective_user.id, gid, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        rows = await BillingService.get_transactions(db, gid, user_id=target.id if target else None,
                                                     current_period=not history)
        if history:
            shown = rows[:50]
        else:
            shown = []
            for kind, limit in [('deposit', group.deposit_display_count), ('withdraw', group.withdraw_display_count), ('storage', 5)]:
                shown.extend([r for r in rows if r.transaction_type == kind][:limit])
            shown.sort(key=lambda r:r.id, reverse=True)
        summary = Formatter.format_summary(Calculator.calculate_summary(rows),
                                          '历史账单' if history else '本期账单')
        body = summary + '\n\n' + Formatter.format_transaction_list(shown, '明细')
        if len(shown) < len(rows):
            body += '\n\n更多明细请发送「导出账单」或「网页账单」。'
        await reply_chunks(update.message, body)

async def reply_chunks(message, body):
    # Keep each Telegram message below its text limit.
    while body:
        end = min(3800, len(body))
        if len(body) > end:
            split = body.rfind('\n', 0, end)
            if split > 0:
                end = split
        await message.reply_text(body[:end])
        body = body[end:].lstrip('\n')

async def show_bills(update, context):
    await _show(update, context)

async def show_all_bills(update, context):
    await _show(update, context, history=True)

async def show_summary(update, context):
    await _show(update, context)

async def show_my_bills(update, context):
    try:
        await _show(update, context, personal=True)
    except ValueError as error:
        await update.message.reply_text(str(error))

async def _void(update, context, kind=None):
    async for db in get_db():
        gid, uid = update.effective_chat.id, update.effective_user.id
        if not await is_operator(uid, gid, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        reply = update.message.reply_to_message
        if kind is None and not reply:
            await update.message.reply_text('请回复要操作的原始记账消息或机器人回执，再发送「撤销」或「撤销恢复」。')
            return
        try:
            row, changed = await BillingService.set_void(db, gid, reply.message_id if reply else None,
                uid, restore=update.message.text in ('撤销恢复','恢复'), kind=kind)
            await update.message.reply_text(f'✅ 记录 #{row.id} ' + ('已恢复' if not row.is_deleted else '已撤销') +
                                            ('，历史痕迹保留。' if changed else '，无需重复操作。'))
        except ValueError as error:
            await update.message.reply_text(str(error))

async def revoke_deposit(update, context):
    await _void(update, context, 'deposit')

async def revoke_withdraw(update, context):
    await _void(update, context, 'withdraw')

async def revoke_record(update, context):
    await _void(update, context)

async def delete_bills(update, context):
    """Logical deletion preserves evidence. Group and member permissions are still checked."""
    async for db in get_db():
        gid, uid = update.effective_chat.id, update.effective_user.id
        if not await is_operator(uid, gid, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        all_history = update.message.text in ('删除全部账单','清除全部账单')
        rows = await BillingService.get_transactions(db, gid, current_period=not all_history)
        for row in rows:
            row.is_deleted = True
            db.add(LedgerAudit(group_id=gid, actor_id=uid, transaction_id=row.id, action='void_all' if all_history else 'void_period'))
        await db.commit()
        await update.message.reply_text(f'✅ 已作废 {len(rows)} 笔{"历史" if all_history else "本期"}记录，原始记录及操作痕迹保留。')

async def save_bills(update, context):
    async for db in get_db():
        gid, uid = update.effective_chat.id, update.effective_user.id
        if not await is_operator(uid, gid, db):
            await update.message.reply_text('❌ 您没有操作权限')
            return
        period = await BillingService.close_period(db, gid, uid)
        if not period:
            await update.message.reply_text('该账期已经保存。')
            return
        summary = {k:Decimal(v) if k.endswith(('amount','cny','fee')) else v for k,v in json.loads(period.summary).items()}
        await update.message.reply_text(Formatter.format_summary(summary, f'账期 #{period.id} 已保存') +
                                       '\n\n本期重新计账；历史记录可查，可导出。')
