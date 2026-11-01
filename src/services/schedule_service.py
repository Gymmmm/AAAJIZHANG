"""Per-chat closing schedule using the same period rules as manual save."""
import json
import logging
from decimal import Decimal
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from config import config
from ..models import Group, get_db
from .billing_service import BillingService
from ..utils.formatter import Formatter

class ScheduleService:
    def __init__(self, bot):
        self.bot=bot
        self.scheduler=AsyncIOScheduler(timezone=config.TIMEZONE)

    async def start(self):
        self.scheduler.start()
        async for db in get_db():
            await self.load_day_cut_tasks(db)

    async def stop(self):
        if self.scheduler.running:
            self.scheduler.shutdown()

    async def load_day_cut_tasks(self, db):
        groups=(await db.execute(select(Group).where(Group.day_cut_time.is_not(None)))).scalars().all()
        for group in groups:
            await self.add_day_cut_task(group)

    async def add_day_cut_task(self, group):
        await self.remove_day_cut_task(group.group_id)
        if group.day_cut_time:
            self.scheduler.add_job(self.execute_day_cut,
                trigger=CronTrigger(hour=group.day_cut_time.hour, minute=group.day_cut_time.minute,
                                    timezone=config.TIMEZONE), args=[group.group_id],
                id=f'day_cut_{group.group_id}', replace_existing=True, coalesce=True, misfire_grace_time=3600)

    async def remove_day_cut_task(self, group_id):
        if self.scheduler.get_job(f'day_cut_{group_id}'):
            self.scheduler.remove_job(f'day_cut_{group_id}')

    async def execute_day_cut(self, group_id):
        try:
            async for db in get_db():
                group=(await db.execute(select(Group).where(Group.group_id==group_id))).scalar_one_or_none()
                if not group or not group.is_active:
                    return
                period=await BillingService.close_period(db,group_id,scheduled=True)
                if period:
                    summary={k:Decimal(v) if isinstance(v,str) else v for k,v in json.loads(period.summary).items()}
                    await self.bot.send_message(chat_id=group_id,text=Formatter.format_summary(summary,
                        f'日切账期 #{period.id} 已保存')+'\n历史账单保留，本期重新计账。')
        except Exception:
            logging.exception('Yam scheduled close failed for chat %s',group_id)

    async def manual_day_cut(self,group_id):
        async for db in get_db():
            await BillingService.close_period(db,group_id)
