import os, tempfile
_test_dir = tempfile.TemporaryDirectory()
os.environ.update(BOT_TOKEN="123456:TEST", SUPER_ADMIN_ID="12345",
                  DATABASE_URL="sqlite+aiosqlite:///" + _test_dir.name + "/smoke.db")
import asyncio
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from sqlalchemy import select
from telegram import Update
from telegram.ext import Application
from src.bot import AccountingBot
from src.handlers import basic, billing
from src.models import init_db, close_db, AsyncSessionLocal, Transaction
async def test():
    app=Application.builder().token("123456:TEST").build()
    runner=AccountingBot()
    runner.setup_handlers(app)
    update=Update.de_json({"update_id":1,"message":{"message_id":1,"date":1,"chat":{"id":-987654321,"type":"supergroup","title":"test"},"from":{"id":12345,"is_bot":False,"first_name":"Test"},"text":"+0"}}, None)
    chosen=next(h for h in app.handlers[0] if h.check_update(update))
    assert chosen.callback is billing.show_bills
    await runner.post_init(app)
    assert app.bot_data["schedule_service"] is runner.schedule_service
    user=NS(id=12345,username="test",first_name="Test")
    msg=NS(text="开始",message_id=1,reply_to_message=None,reply_text=AsyncMock())
    u=NS(message=msg,effective_chat=NS(id=-987654321,title="test",type="supergroup"),effective_user=user)
    await basic.start_billing(u,NS())
    msg.text="+100u";msg.message_id=2
    await billing.handle_deposit(u,NS())
    msg.text="下发20u";msg.message_id=3
    await billing.handle_withdraw(u,NS())
    await billing.show_bills(u,NS())
    async with AsyncSessionLocal() as db:
        rows=(await db.execute(select(Transaction))).scalars().all()
        assert len(rows)==2, len(rows)
        assert rows[0].transaction_type=="deposit" and rows[0].amount==100
        assert rows[1].transaction_type=="withdraw" and rows[1].amount==20
    assert msg.reply_text.await_count==4
    await runner.post_shutdown(app)
    print("PASS: startup, scheduler, +0 route, start, deposit, withdraw, bill, DB persistence, shutdown")
asyncio.run(test())
