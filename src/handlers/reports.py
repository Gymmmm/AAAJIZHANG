import io
import os
from ..models import get_db
from ..services.billing_service import BillingService
from ..services.reports import html_text, xlsx_bytes, report_token
from .operator import is_operator

async def export_bills(update, context):
    gid = update.effective_chat.id
    async for db in get_db():
        if not await is_operator(update.effective_user.id, gid, db):
            await update.message.reply_text('❌ 只有本群管理员或操作人可以导出账单。')
            return
        rows = await BillingService.get_transactions(db, gid, include_deleted=True)
        excel = io.BytesIO(xlsx_bytes(rows)); excel.name = 'Yam_账单明细.xlsx'
        await update.message.reply_document(document=excel, caption='完整历史明细（含撤销记录），金额和实际费汇逐笔保留。')

async def web_bills(update, context):
    gid = update.effective_chat.id
    async for db in get_db():
        if not await is_operator(update.effective_user.id, gid, db):
            await update.message.reply_text('❌ 只有本群管理员或操作人可以打开完整账单。')
            return
        base = os.environ.get('YAM_REPORT_URL','').rstrip('/')
        if base:
            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
            token=report_token(gid)
            await update.message.reply_text('📋 本群完整账单\n链接一小时内有效，请仅分享给对账人员。',
                reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton('查看完整账单', url=base+'/bill/'+token)]]))
        else:
            rows = await BillingService.get_transactions(db, gid, include_deleted=True)
            page = io.BytesIO(html_text(rows).encode()); page.name='Yam_完整账单.html'
            await update.message.reply_document(document=page, caption='完整账单，可下载后打开。')
