"""Run with PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'."""
import os
import tempfile
_tmp = tempfile.TemporaryDirectory()
os.environ.update(BOT_TOKEN='123456:TEST', SUPER_ADMIN_ID='1', TIMEZONE='Asia/Phnom_Penh',
                  DATABASE_URL='sqlite+aiosqlite:///'+_tmp.name+'/ledger.db')
import asyncio
import io
import json
import unittest
import zipfile
from datetime import datetime, time
from decimal import Decimal
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock
from xml.etree import ElementTree as ET
from sqlalchemy import select
from telegram import Update
from telegram.ext import Application
from fastapi.testclient import TestClient
from src.models import Base, engine, AsyncSessionLocal, init_db, Group, Transaction, LedgerReceipt, LedgerAudit, KnownMember, UserConfig
from src.handlers import basic, billing, settings, operator
from src.services.billing_service import BillingService as Ledger
from src.services.identity import remember_user, resolve_user
from src.services.reports import html_text, xlsx_bytes, report_token, read_report_token
from src.services.schedule_service import ScheduleService
from src.utils.parser import CommandParser as Parser
from src.utils.calculator import Calculator
from src.bot import AccountingBot
from src.web.ledger_reports import app as report_app

def update(text, mid=1, uid=1, gid=-10, reply=None):
    user=NS(id=uid,username=f'user{uid}',first_name=f'用户{uid}',full_name=f'用户{uid}',is_bot=False)
    msg=NS(text=text,message_id=mid,reply_to_message=reply,entities=[],from_user=user,
           reply_text=AsyncMock(return_value=NS(message_id=mid+10000,pin=AsyncMock())),reply_document=AsyncMock())
    return NS(message=msg,effective_message=msg,effective_user=user,effective_chat=NS(id=gid,title='测试群',type='supergroup'))

def context():
    return NS(bot=NS(get_chat_member=AsyncMock(return_value=NS(status='member'))),application=NS(bot_data={}))

class LedgerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        operator.permission_bot=None
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
        await init_db()
        async with AsyncSessionLocal() as db:
            db.add(Group(group_id=-10,group_name='测试群',exchange_rate=7.3,fee_rate=3))
            await db.commit()

    async def rows(self,deleted=False):
        async with AsyncSessionLocal() as db:
            return await Ledger.get_transactions(db,-10,include_deleted=deleted)

    async def test_fee_percent_and_exact_rounding(self):
        for text in ['设置费率3','设置费率3%']:
            self.assertEqual(Parser.parse_rate_setting(text)['value'],Decimal(3))
        info=Parser.parse_deposit('+100u/7.3*0.12')
        self.assertEqual(info['fee_rate'],Decimal('0.12'))
        calc=Calculator.calculate_transaction(Decimal('1.005'),'CNY',fee_rate=0)
        self.assertEqual(calc['final_amount'],Decimal('1.01'))
        with self.assertRaises(ValueError): Parser.parse_deposit('+1.001')
        with self.assertRaises(ValueError): Parser.parse_deposit('+1u/0')
        with self.assertRaises(ValueError): Parser.parse_deposit('+1*101')
        self.assertIsNone(Parser.parse_deposit('+1u/7.3junk'))

    async def test_create_correction_summary_and_precision(self):
        await billing.handle_deposit(update('+100u',1),context())
        await billing.handle_withdraw(update('下发20u',2),context())
        await billing.handle_correction(update('-73',3),context())
        await billing.handle_correction(update('下发-7.3',4),context())
        rows=await self.rows()
        self.assertEqual(len(rows),4)
        self.assertTrue(rows[0].is_correction)
        self.assertEqual(Calculator.calculate_summary(rows)['net_amount'],Decimal('502.75'))
        await billing.handle_deposit(update('+0.123456u*0',5),context())
        r=(await self.rows())[0]
        self.assertEqual(r.amount,Decimal('0.123456'))
        self.assertEqual(r.fee_rate,Decimal(0))

    async def test_duplicate_and_after_void(self):
        u=update('+100',1)
        await billing.handle_deposit(u,context())
        await billing.handle_deposit(u,context())
        self.assertEqual(len(await self.rows()),1)
        await billing.revoke_record(update('撤销',2,reply=NS(message_id=1)),context())
        await billing.handle_deposit(u,context())
        self.assertEqual(len(await self.rows(deleted=True)),1)
        self.assertEqual(await self.rows(),[])

    async def test_receipt_void_restore_and_audit(self):
        await billing.handle_deposit(update('+100',1),context())
        await billing.revoke_record(update('撤销',2,reply=NS(message_id=10001)),context())
        self.assertEqual(await self.rows(),[])
        await billing.revoke_record(update('撤销恢复',3,reply=NS(message_id=1)),context())
        self.assertEqual(len(await self.rows()),1)
        async with AsyncSessionLocal() as db:
            actions=(await db.execute(select(LedgerAudit.action).order_by(LedgerAudit.id))).scalars().all()
            self.assertEqual(actions,['create','void','restore'])

    async def test_cross_chat_and_unauthorized(self):
        await billing.handle_deposit(update('+100',1),context())
        await billing.revoke_record(update('撤销',2,uid=2,reply=NS(message_id=1)),context())
        self.assertEqual(len(await self.rows()),1)
        await billing.revoke_record(update('撤销',2,gid=-20,reply=NS(message_id=1)),context())
        self.assertEqual(len(await self.rows()),1)
        await billing.handle_deposit(update('+100',3,uid=2),context())
        self.assertEqual(len(await self.rows()),1)

    async def test_identity_ambiguous_and_named_personal_zero(self):
        async with AsyncSessionLocal() as db:
            await remember_user(db,-10,update('',uid=2).effective_user)
            await db.commit()
        await settings.set_fee_rate(update('设置用户2费率0',1),context())
        await billing.handle_deposit(update('用户2+100',2),context())
        row=(await self.rows())[0]
        self.assertEqual(row.user_id,2)
        self.assertEqual(row.fee_rate,Decimal(0))
        await billing.handle_deposit(update('未知人+100',3),context())
        self.assertEqual(len(await self.rows()),1)
        async with AsyncSessionLocal() as db:
            db.add(KnownMember(group_id=-10,user_id=3,username='another',first_name='用户2'))
            await db.commit()
            with self.assertRaises(ValueError): await resolve_user(db,-10,'用户2')

    async def test_operator_batch_and_owner_only_global(self):
        async with AsyncSessionLocal() as db:
            for uid in [2,3]: await remember_user(db,-10,update('',uid=uid).effective_user)
            await db.commit()
        await operator.add_operator(update('添加操作人 @user2 @user3'),context())
        async with AsyncSessionLocal() as db:
            self.assertTrue(await operator.is_operator(2,-10,db))
        await operator.remove_operator(update('删除操作人 @user2'),context())
        async with AsyncSessionLocal() as db:
            self.assertFalse(await operator.is_operator(2,-10,db))
        await operator.add_global_operator(update('添加全局操作人 @user3'),context())
        await operator.remove_global_operator(update('删除全局操作人 @user3',uid=2),context())
        async with AsyncSessionLocal() as db:
            self.assertTrue(await operator.is_operator(3,-20,db))
        await operator.remove_global_operator(update('删除全局操作人 @user3'),context())
        async with AsyncSessionLocal() as db:
            self.assertFalse(await operator.is_operator(3,-20,db))

    async def test_manual_period_archive_preserves_history(self):
        await billing.handle_deposit(update('+100',1),context())
        await billing.save_bills(update('保存账单',2),context())
        async with AsyncSessionLocal() as db:
            self.assertEqual(await Ledger.get_transactions(db,-10,current_period=True),[])
            self.assertEqual(len(await Ledger.get_transactions(db,-10)),1)
        await billing.handle_deposit(update('+50',3),context())
        async with AsyncSessionLocal() as db:
            self.assertEqual(len(await Ledger.get_transactions(db,-10,current_period=True)),1)

    async def test_scheduled_boundary_and_timezone(self):
        group=Group(group_id=-10,group_name='测试',day_cut_time=time(6),last_day_cut=None)
        self.assertEqual(Ledger.period_start(group,datetime(2026,11,1,22,59)),datetime(2026,10,31,23))
        self.assertEqual(Ledger.period_start(group,datetime(2026,11,1,23)),datetime(2026,11,1,23))
        service=ScheduleService(NS())
        await service.add_day_cut_task(group)
        self.assertIn('Asia/Phnom_Penh',str(service.scheduler.get_job('day_cut_-10').trigger.timezone))
        async with AsyncSessionLocal() as db:
            g=(await db.execute(select(Group))).scalar_one();g.day_cut_time=time(6)
            await db.commit()
            a=await Ledger.close_period(db,-10,scheduled=True,now=datetime(2026,11,1,23))
            b=await Ledger.close_period(db,-10,scheduled=True,now=datetime(2026,11,1,23))
            self.assertIsNotNone(a);self.assertIsNone(b)

    async def test_concurrent_duplicate(self):
        async def create():
            async with AsyncSessionLocal() as db:
                return await Ledger.create_transaction(db,-10,1,'u','u',1,'u','u','deposit',Decimal('1'),message_id=99)
        results=await asyncio.gather(create(),create())
        self.assertEqual(sum(x is not None for x in results),1)
        self.assertEqual(len(await self.rows()),1)

    async def test_reports_no_formulas_and_auth_scope(self):
        await billing.handle_deposit(update('+100 =HYPERLINK("https://x") <script>bad</script>',1),context())
        rows=await self.rows()
        with zipfile.ZipFile(io.BytesIO(xlsx_bytes(rows))) as archive:
            xml=archive.read('xl/worksheets/sheet1.xml')
            ET.fromstring(xml)
            self.assertNotIn(b'<f>',xml)
        page=html_text(rows)
        self.assertNotIn('<script>',page)
        token=report_token(-10,now=100)
        self.assertEqual(read_report_token(token,now=101),-10)
        with self.assertRaises(ValueError): read_report_token(token+'bad',now=101)
        with self.assertRaises(ValueError): read_report_token(token,now=3701)
        with TestClient(report_app) as client:
            self.assertEqual(client.get('/bill/bad').status_code,403)
            self.assertEqual(client.get('/bill/'+report_token(-10)).status_code,200)
            self.assertEqual(client.get('/bill/'+report_token(-20)).status_code,200)
            self.assertNotIn('HYPERLINK',client.get('/bill/'+report_token(-20)).text)

    async def test_routing_and_setting_validation(self):
        a=Application.builder().token('123456:TEST').build()
        AccountingBot().setup_handlers(a)
        for text,callback in [('+0',billing.show_bills),('-100',billing.handle_correction),('下发-100u',billing.handle_correction),
                             ('撤销',billing.revoke_record),('设置费率0%',settings.set_fee_rate)]:
            u=Update.de_json({'update_id':1,'message':{'message_id':1,'date':1,'chat':{'id':-10,'type':'supergroup'},
                'from':{'id':1,'is_bot':False,'first_name':'test'},'text':text}},None)
            chosen=next(h for h in a.handlers[0] if h.check_update(u))
            self.assertIs(chosen.callback,callback)
        await settings.set_exchange_rate(update('设置汇率0'),context())
        async with AsyncSessionLocal() as db:
            g=(await db.execute(select(Group))).scalar_one();self.assertEqual(g.exchange_rate,7.3)

if __name__=='__main__': unittest.main()
