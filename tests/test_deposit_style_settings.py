"""Exercise the handler with real SQLite storage and mocked Telegram messages."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch
from sqlalchemy import Column, Integer, String, Boolean
from sqlalchemy.orm import declarative_base
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from telegram.ext import ApplicationHandlerStop

ROOT = Path(__file__).resolve().parents[1]
N = types.SimpleNamespace
Base = declarative_base()

class Config(Base):
    __tablename__ = 'system_configs'
    key = Column(String, primary_key=True)
    value = Column(String)
    is_public = Column(Boolean)

class Group(Base):
    __tablename__ = 'groups'
    group_id = Column(Integer, primary_key=True)

def load_handler():
    modules = {}
    for name in ['_handler_test', '_handler_test.handlers', '_handler_test.utils']:
        modules[name] = types.ModuleType(name)
        modules[name].__path__ = []
    models = types.ModuleType('_handler_test.models')
    models.SystemConfig, models.Group, models.get_db = Config, Group, None
    modules[models.__name__] = models
    operator = types.ModuleType('_handler_test.handlers.operator')
    operator.is_operator = AsyncMock(return_value=True)
    modules[operator.__name__] = operator
    config = types.ModuleType('config')
    config.config = N(TIMEZONE='Asia/Shanghai')
    modules['config'] = config
    with patch.dict(sys.modules, modules):
        for name, path in [('utils.deposit_style','src/utils/deposit_style.py'),('handlers.deposit_style','src/handlers/deposit_style.py')]:
            spec = importlib.util.spec_from_file_location('_handler_test.'+name, ROOT/path)
            mod = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = mod
            spec.loader.exec_module(mod)
    return mod

handler = load_handler()

class SettingsTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.engine = create_async_engine('sqlite+aiosqlite:///:memory:')
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        self.sessions = async_sessionmaker(self.engine, expire_on_commit=False)
        async def get_db():
            async with self.sessions() as db:
                yield db
        self.db_patch = patch.object(handler, 'get_db', get_db)
        self.db_patch.start()
        self.permission = patch.object(handler, 'is_operator', AsyncMock(return_value=True))
        self.permission.start()
        async with self.sessions() as db:
            db.add(Group(group_id=-1))
            await db.commit()
        self.msg = N(reply_text=AsyncMock(), text='', reply_to_message=None)
        self.update = N(effective_chat=N(id=-1), effective_user=N(id=5), effective_message=self.msg)
        self.context = N(bot=N(id=10), user_data={})

    async def asyncTearDown(self):
        self.permission.stop()
        self.db_patch.stop()
        await self.engine.dispose()

    async def test_persistence_and_bot_group_isolation(self):
        async with self.sessions() as db:
            await handler.save_style(db,10,-1,{'name':'dual'})
        async with self.sessions() as db:
            self.assertEqual(await handler.load_style(db,10,-1),{'name':'dual'})
            self.assertIsNone(await handler.load_style(db,11,-1))
            self.assertIsNone(await handler.load_style(db,10,-2))

    async def test_panel_and_preset(self):
        await handler.show_style(self.update,self.context)
        keyboard = self.msg.reply_text.call_args.kwargs['reply_markup']
        self.assertEqual(len(keyboard.inline_keyboard),6)
        query = N(data='depstyle:usdt', answer=AsyncMock(),message=self.msg)
        self.update.callback_query=query
        await handler.choose_style(self.update,self.context)
        async with self.sessions() as db:
            self.assertEqual(await handler.load_style(db,10,-1),{'name':'usdt'})

    async def test_permission_rechecked_on_click(self):
        handler.is_operator.return_value=False
        query=N(data='depstyle:usdt',answer=AsyncMock(),message=self.msg)
        self.update.callback_query=query
        await handler.choose_style(self.update,self.context)
        self.assertTrue(query.answer.call_args.kwargs['show_alert'])
        async with self.sessions() as db:
            self.assertIsNone(await handler.load_style(db,10,-1))

    async def test_custom_prompt_and_input(self):
        self.msg.reply_text.return_value=N(message_id=99)
        self.update.callback_query=N(data='depstyle:custom',answer=AsyncMock(),message=self.msg)
        await handler.choose_style(self.update,self.context)
        self.msg.text='{time} {usum}U'
        self.msg.reply_to_message=N(message_id=99)
        with self.assertRaises(ApplicationHandlerStop):
            await handler.receive_template(self.update,self.context)
        async with self.sessions() as db:
            self.assertEqual(await handler.load_style(db,10,-1),{'name':'custom','template':self.msg.text})
        self.assertNotIn('deposit_template_prompt',self.context.user_data)

    async def test_invalid_input_cancel_and_unrelated_reply(self):
        self.context.user_data['deposit_template_prompt']=(-1,99)
        self.msg.reply_to_message=N(message_id=98)
        self.msg.text='+1000'
        await handler.receive_template(self.update,self.context)
        self.msg.reply_text.assert_not_awaited()
        self.msg.reply_to_message.message_id=99
        self.msg.text='{money.__class__}'
        with self.assertRaises(ApplicationHandlerStop):
            await handler.receive_template(self.update,self.context)
        self.assertIn('deposit_template_prompt',self.context.user_data)
        self.msg.text='取消'
        with self.assertRaises(ApplicationHandlerStop):
            await handler.receive_template(self.update,self.context)
        self.assertNotIn('deposit_template_prompt',self.context.user_data)
        async with self.sessions() as db:
            self.assertIsNone(await handler.load_style(db,10,-1))
