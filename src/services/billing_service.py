"""
账单服务
"""
from datetime import datetime, timedelta
import json
from decimal import Decimal
from sqlalchemy.exc import IntegrityError
from ..models import LedgerReceipt, LedgerAudit, LedgerPeriod
from config import config
import pytz
from typing import List, Optional, Dict, Any
from sqlalchemy import select, and_, or_, desc
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Transaction, DailySummary, Group, UserConfig
from ..utils.calculator import Calculator


class BillingService:
    """账单服务类"""

    @staticmethod
    async def create_transaction(
        db: AsyncSession,
        group_id: int,
        user_id: int,
        username: Optional[str],
        first_name: Optional[str],
        operator_id: int,
        operator_username: Optional[str],
        operator_first_name: Optional[str],
        transaction_type: str,
        amount: float,
        currency: str = "USDT",
        exchange_rate: Optional[float] = None,
        fee_rate: Optional[float] = None,
        note: str = "",
        message_id: Optional[int] = None,
        reply_to_message_id: Optional[int] = None,
        is_correction: bool = False
    ) -> Transaction:
        """
        创建交易记录
        """
        receipt = None
        if message_id is not None:
            # Reserve the Telegram message within the same transaction as the ledger write.
            old = (await db.execute(select(Transaction.id).where(
                Transaction.group_id == group_id, Transaction.message_id == message_id))).first()
            if old:
                return None
            receipt = LedgerReceipt(group_id=group_id, message_id=message_id)
            db.add(receipt)
            try:
                await db.flush()
            except IntegrityError:
                await db.rollback()
                return None
        # 计算金额
        calc_result = Calculator.calculate_transaction(
            amount=amount,
            currency=currency,
            exchange_rate=exchange_rate,
            fee_rate=fee_rate
        )

        # 创建交易记录
        transaction = Transaction(
            group_id=group_id,
            user_id=user_id,
            username=username,
            first_name=first_name,
            operator_id=operator_id,
            operator_username=operator_username,
            operator_first_name=operator_first_name,
            transaction_type=transaction_type,
            amount=amount,
            currency=currency,
            exchange_rate=exchange_rate,
            fee_rate=fee_rate,
            cny_amount=calc_result['cny_amount'],
            fee_amount=calc_result['fee_amount'],
            final_amount=calc_result['final_amount'],
            note=note,
            message_id=message_id,
            reply_to_message_id=reply_to_message_id,
            is_correction=is_correction,
            transaction_date=datetime.utcnow()
        )

        db.add(transaction)
        await db.flush()
        if receipt:
            receipt.transaction_id = transaction.id
            receipt.exact_values = json.dumps({
                'amount': str(amount), 'exchange_rate': str(exchange_rate) if exchange_rate is not None else None,
                'fee_rate': str(fee_rate) if fee_rate is not None else None,
                **{key: str(calc_result[key]) for key in ('cny_amount', 'fee_amount', 'final_amount')}
            })
        db.add(LedgerAudit(group_id=group_id, transaction_id=transaction.id,
                           actor_id=operator_id, action='correction' if is_correction else 'create'))
        await db.commit()
        await db.refresh(transaction)

        return transaction

    @staticmethod
    async def get_transactions(
        db: AsyncSession,
        group_id: int,
        transaction_type: Optional[str] = None,
        user_id: Optional[int] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: Optional[int] = None,
        include_deleted: bool = False,
        current_period: bool = False
    ) -> List[Transaction]:
        """
        查询交易记录
        """
        query = select(Transaction).where(Transaction.group_id == group_id)

        if current_period:
            group = (await db.execute(select(Group).where(Group.group_id == group_id))).scalar_one_or_none()
            if group:
                query = query.where(Transaction.transaction_date >= BillingService.period_start(group))
        if not include_deleted:
            query = query.where(Transaction.is_deleted == False)

        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)

        if user_id:
            query = query.where(Transaction.user_id == user_id)

        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)

        if end_date:
            query = query.where(Transaction.transaction_date < end_date)

        query = query.order_by(desc(Transaction.transaction_date))

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        rows = list(result.scalars().all())
        if rows:
            receipts = (await db.execute(select(LedgerReceipt).where(
                LedgerReceipt.transaction_id.in_([row.id for row in rows])))).scalars().all()
            exact = {r.transaction_id: json.loads(r.exact_values) for r in receipts}
            audits = (await db.execute(select(LedgerAudit).where(
                LedgerAudit.transaction_id.in_([row.id for row in rows])).order_by(LedgerAudit.id))).scalars().all()
            for row in rows:
                row.audit_history = '; '.join(f'{a.action} / {a.actor_id} / {a.created_at.isoformat()}'
                                              for a in audits if a.transaction_id == row.id)
                # Set committed values: querying must never rewrite old monetary data.
                from sqlalchemy.orm.attributes import set_committed_value
                for key, value in exact.get(row.id, {}).items():
                    set_committed_value(row, key, Decimal(value) if value is not None else None)
        return rows

    @staticmethod
    async def get_latest_transaction(
        db: AsyncSession,
        group_id: int,
        transaction_type: str
    ) -> Optional[Transaction]:
        """
        获取最新的一条交易记录
        """
        query = select(Transaction).where(
            and_(
                Transaction.group_id == group_id,
                Transaction.transaction_type == transaction_type,
                Transaction.is_deleted == False
            )
        ).order_by(desc(Transaction.transaction_date)).limit(1)

        result = await db.execute(query)
        return result.scalar_one_or_none()

    @staticmethod
    async def delete_transaction(
        db: AsyncSession,
        transaction_id: int
    ) -> bool:
        """
        删除（标记）交易记录
        """
        query = select(Transaction).where(Transaction.id == transaction_id)
        result = await db.execute(query)
        transaction = result.scalar_one_or_none()

        if transaction:
            transaction.is_deleted = True
            await db.commit()
            return True

        return False

    @staticmethod
    async def delete_all_transactions(
        db: AsyncSession,
        group_id: int
    ) -> int:
        """
        删除（标记）群组所有交易记录
        """
        query = select(Transaction).where(
            and_(
                Transaction.group_id == group_id,
                Transaction.is_deleted == False
            )
        )
        result = await db.execute(query)
        transactions = result.scalars().all()

        count = 0
        for transaction in transactions:
            transaction.is_deleted = True
            count += 1

        await db.commit()
        return count

    @staticmethod
    async def get_user_transactions(
        db: AsyncSession,
        group_id: int,
        user_id: int,
        limit: Optional[int] = None
    ) -> List[Transaction]:
        """
        获取指定用户的交易记录
        """
        return await BillingService.get_transactions(
            db=db,
            group_id=group_id,
            user_id=user_id,
            limit=limit
        )

    @staticmethod
    async def search_user_by_name(
        db: AsyncSession,
        group_id: int,
        name_query: str
    ) -> List[int]:
        """
        根据名字模糊查询用户ID
        """
        query = select(Transaction.user_id).where(
            and_(
                Transaction.group_id == group_id,
                or_(
                    Transaction.username.ilike(f"%{name_query}%"),
                    Transaction.first_name.ilike(f"%{name_query}%")
                )
            )
        ).distinct()

        result = await db.execute(query)
        return result.scalars().all()

    @staticmethod
    async def calculate_summary(
        db: AsyncSession,
        group_id: int,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None
    ) -> Dict[str, Any]:
        """
        计算账单汇总
        """
        transactions = await BillingService.get_transactions(
            db=db,
            group_id=group_id,
            start_date=start_date,
            end_date=end_date
        )

        return Calculator.calculate_summary(transactions)

    @staticmethod
    async def create_daily_summary(
        db: AsyncSession,
        group_id: int,
        summary_date: datetime
    ) -> DailySummary:
        """
        创建每日汇总
        """
        # 计算当日汇总
        start_date = summary_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date + timedelta(days=1)

        summary_data = await BillingService.calculate_summary(
            db=db,
            group_id=group_id,
            start_date=start_date,
            end_date=end_date
        )

        # 创建或更新汇总记录
        query = select(DailySummary).where(
            and_(
                DailySummary.group_id == group_id,
                DailySummary.summary_date == summary_date.date()
            )
        )
        result = await db.execute(query)
        daily_summary = result.scalar_one_or_none()

        if not daily_summary:
            daily_summary = DailySummary(
                group_id=group_id,
                summary_date=summary_date.date()
            )
            db.add(daily_summary)

        # 更新汇总数据
        daily_summary.total_deposit_count = summary_data['deposit_count']
        daily_summary.total_deposit_amount = summary_data['deposit_amount']
        daily_summary.total_deposit_cny = summary_data['deposit_cny']
        daily_summary.total_withdraw_count = summary_data['withdraw_count']
        daily_summary.total_withdraw_amount = summary_data['withdraw_amount']
        daily_summary.total_withdraw_cny = summary_data['withdraw_cny']
        daily_summary.total_storage_amount = summary_data['storage_amount']
        daily_summary.total_fee_amount = summary_data['total_fee']
        daily_summary.net_amount = summary_data['net_amount']

        await db.commit()
        await db.refresh(daily_summary)

        return daily_summary

    @staticmethod
    def period_start(group, now=None):
        now = now or datetime.utcnow()
        start = group.last_day_cut or datetime(1970, 1, 1)
        if group.day_cut_time:
            tz = pytz.timezone(config.TIMEZONE)
            local = pytz.utc.localize(now).astimezone(tz)
            cut = tz.localize(datetime.combine(local.date(), group.day_cut_time))
            if cut > local:
                cut -= timedelta(days=1)
            start = max(start, cut.astimezone(pytz.utc).replace(tzinfo=None))
        return start

    @staticmethod
    async def bind_reply(db, transaction, reply_message_id):
        row = (await db.execute(select(LedgerReceipt).where(
            LedgerReceipt.transaction_id == transaction.id))).scalar_one_or_none()
        if row:
            row.reply_message_id = reply_message_id
            await db.commit()

    @staticmethod
    async def set_void(db, group_id, message_id, actor_id, restore=False, kind=None):
        query = select(Transaction).where(Transaction.group_id == group_id)
        if message_id is not None:
            receipt = (await db.execute(select(LedgerReceipt).where(
                LedgerReceipt.group_id == group_id,
                (LedgerReceipt.message_id == message_id) | (LedgerReceipt.reply_message_id == message_id)))).scalar_one_or_none()
            query = query.where(Transaction.id == receipt.transaction_id) if receipt else query.where(Transaction.message_id == message_id)
        elif kind:
            query = query.where(Transaction.transaction_type == kind, Transaction.is_deleted == False)
        else:
            raise ValueError('请回复要操作的记账消息。')
        row = (await db.execute(query.order_by(Transaction.id.desc()).limit(1))).scalar_one_or_none()
        if not row:
            raise ValueError('没有找到本群对应的记账记录。')
        if row.is_deleted == (not restore):
            return row, False
        row.is_deleted = not restore
        db.add(LedgerAudit(group_id=group_id, transaction_id=row.id, actor_id=actor_id,
                           action='restore' if restore else 'void'))
        await db.commit()
        return row, True

    @staticmethod
    async def close_period(db, group_id, actor_id=0, now=None, scheduled=False):
        now = now or datetime.utcnow()
        group = (await db.execute(select(Group).where(Group.group_id == group_id))).scalar_one()
        # A scheduled close includes the period immediately BEFORE the boundary.
        end = BillingService.period_start(group, now) if scheduled else now
        start = BillingService.period_start(group, end - timedelta(microseconds=1)) if scheduled else BillingService.period_start(group, now)
        if end <= start:
            return None
        rows = await BillingService.get_transactions(db, group_id, start_date=start, end_date=end)
        summary = Calculator.calculate_summary(rows)
        period = LedgerPeriod(group_id=group_id, start_at=start, end_at=end, actor_id=actor_id,
                              summary=json.dumps(summary, default=str))
        db.add(period)
        group.last_day_cut = end
        db.add(LedgerAudit(group_id=group_id, actor_id=actor_id, action='close_period',
                           detail=f'{start.isoformat()} / {end.isoformat()}'))
        try:
            await db.commit()
        except IntegrityError:
            await db.rollback()
            return None
        return period

    @staticmethod
    async def save_bills(db, group_id):
        return await BillingService.close_period(db, group_id)
