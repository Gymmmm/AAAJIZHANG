"""
定时任务服务
"""
from datetime import datetime, time
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from telegram import Bot

from ..models import Group, get_db
from .billing_service import BillingService


class ScheduleService:
    """定时任务服务类"""

    def __init__(self, bot: Bot):
        self.bot = bot
        self.scheduler = AsyncIOScheduler()

    async def start(self):
        """启动定时任务"""
        # 启动调度器
        self.scheduler.start()

        # 加载所有群组的日切任务
        async for db in get_db():
            await self.load_day_cut_tasks(db)

    async def stop(self):
        """停止定时任务"""
        self.scheduler.shutdown()

    async def load_day_cut_tasks(self, db):
        """加载所有群组的日切任务"""
        query = select(Group).where(Group.day_cut_time.is_not(None))
        result = await db.execute(query)
        groups = result.scalars().all()

        for group in groups:
            await self.add_day_cut_task(group)

    async def add_day_cut_task(self, group: Group):
        """
        添加日切任务

        Args:
            group: 群组对象
        """
        if not group.day_cut_time:
            return

        # 创建任务ID
        job_id = f"day_cut_{group.group_id}"

        # 移除已存在的任务
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

        # 添加新任务
        trigger = CronTrigger(
            hour=group.day_cut_time.hour,
            minute=group.day_cut_time.minute,
            second=0
        )

        self.scheduler.add_job(
            self.execute_day_cut,
            trigger=trigger,
            args=[group.group_id],
            id=job_id,
            replace_existing=True
        )

    async def remove_day_cut_task(self, group_id: int):
        """
        移除日切任务

        Args:
            group_id: 群组ID
        """
        job_id = f"day_cut_{group_id}"
        if self.scheduler.get_job(job_id):
            self.scheduler.remove_job(job_id)

    async def execute_day_cut(self, group_id: int):
        """
        执行日切操作

        Args:
            group_id: 群组ID
        """
        try:
            async for db in get_db():
                # 获取群组信息
                query = select(Group).where(Group.group_id == group_id)
                result = await db.execute(query)
                group = result.scalar_one_or_none()

                if not group or not group.is_active:
                    return

                # 创建每日汇总
                today = datetime.utcnow()
                daily_summary = await BillingService.create_daily_summary(
                    db=db,
                    group_id=group_id,
                    summary_date=today
                )

                # 更新最后日切时间
                group.last_day_cut = today
                await db.commit()

                # 发送日切通知
                message = self._format_day_cut_message(daily_summary, group)
                await self.bot.send_message(
                    chat_id=group_id,
                    text=message,
                    parse_mode='HTML'
                )

        except Exception as e:
            print(f"Error executing day cut for group {group_id}: {e}")

    def _format_day_cut_message(self, daily_summary, group: Group) -> str:
        """
        格式化日切消息

        Args:
            daily_summary: 每日汇总对象
            group: 群组对象

        Returns:
            格式化的消息文本
        """
        lines = [
            "🌙 <b>日切汇总</b>",
            "=" * 30,
            "",
            f"📅 日期: {daily_summary.summary_date.strftime('%Y-%m-%d')}",
            f"🏢 群组: {group.group_name}",
            "",
            "<b>💰 入款统计</b>",
            f"  笔数: {daily_summary.total_deposit_count}",
            f"  总额: {daily_summary.total_deposit_amount:.2f} USDT",
            f"  人民币: ¥{daily_summary.total_deposit_cny:.2f}",
            "",
            "<b>💸 下发统计</b>",
            f"  笔数: {daily_summary.total_withdraw_count}",
            f"  总额: {daily_summary.total_withdraw_amount:.2f} USDT",
            f"  人民币: ¥{daily_summary.total_withdraw_cny:.2f}",
            "",
            f"<b>📦 寄存: ¥{daily_summary.total_storage_amount:.2f}</b>",
            f"<b>💵 手续费: ¥{daily_summary.total_fee_amount:.2f}</b>",
            "",
            f"<b>📈 净额: ¥{daily_summary.net_amount:.2f}</b>",
        ]

        return "\n".join(lines)

    async def manual_day_cut(self, group_id: int):
        """
        手动执行日切

        Args:
            group_id: 群组ID
        """
        await self.execute_day_cut(group_id)
