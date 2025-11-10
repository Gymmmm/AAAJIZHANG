"""
账单服务
"""
from datetime import datetime, timedelta
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
        include_deleted: bool = False
    ) -> List[Transaction]:
        """
        查询交易记录
        """
        query = select(Transaction).where(Transaction.group_id == group_id)

        if not include_deleted:
            query = query.where(Transaction.is_deleted == False)

        if transaction_type:
            query = query.where(Transaction.transaction_type == transaction_type)

        if user_id:
            query = query.where(Transaction.user_id == user_id)

        if start_date:
            query = query.where(Transaction.transaction_date >= start_date)

        if end_date:
            query = query.where(Transaction.transaction_date <= end_date)

        query = query.order_by(desc(Transaction.transaction_date))

        if limit:
            query = query.limit(limit)

        result = await db.execute(query)
        return result.scalars().all()

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
    async def save_bills(
        db: AsyncSession,
        group_id: int
    ) -> DailySummary:
        """
        保存账单（创建当日汇总并标记为已保存）
        """
        today = datetime.utcnow()
        daily_summary = await BillingService.create_daily_summary(
            db=db,
            group_id=group_id,
            summary_date=today
        )

        daily_summary.is_saved = True
        await db.commit()
        await db.refresh(daily_summary)

        return daily_summary
