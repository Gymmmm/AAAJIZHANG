"""
交易记录数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, BigInteger, Float, Integer, Text, Boolean
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Transaction(Base):
    """交易记录模型"""
    __tablename__ = "transactions"

    # 基本信息
    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="群组ID")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="用户ID")
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户名")
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="名字")

    # 操作人信息
    operator_id: Mapped[int] = mapped_column(BigInteger, comment="操作人ID")
    operator_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="操作人用户名")
    operator_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="操作人名字")

    # 交易信息
    transaction_type: Mapped[str] = mapped_column(String(20), index=True, comment="交易类型: deposit(入款), withdraw(下发), storage(寄存)")
    amount: Mapped[float] = mapped_column(Float, comment="金额")
    currency: Mapped[str] = mapped_column(String(10), default="USDT", comment="币种")

    # 汇率和费率
    exchange_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="汇率")
    fee_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="费率(%)")

    # 计算结果
    cny_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="人民币金额")
    fee_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="手续费金额")
    final_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="最终金额")

    # 备注和消息
    note: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="备注")
    message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="消息ID")
    reply_to_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, comment="回复的消息ID")

    # 状态
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已删除")
    is_correction: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否为修正记录")

    # 日期
    transaction_date: Mapped[datetime] = mapped_column(index=True, comment="交易日期")
    day_cut_date: Mapped[Optional[datetime]] = mapped_column(nullable=True, comment="所属日切日期")


class DailySummary(Base):
    """每日汇总模型"""
    __tablename__ = "daily_summaries"

    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="群组ID")
    summary_date: Mapped[datetime] = mapped_column(index=True, comment="汇总日期")

    # 入款统计
    total_deposit_count: Mapped[int] = mapped_column(Integer, default=0, comment="入款笔数")
    total_deposit_amount: Mapped[float] = mapped_column(Float, default=0, comment="入款总额")
    total_deposit_cny: Mapped[float] = mapped_column(Float, default=0, comment="入款人民币总额")

    # 下发统计
    total_withdraw_count: Mapped[int] = mapped_column(Integer, default=0, comment="下发笔数")
    total_withdraw_amount: Mapped[float] = mapped_column(Float, default=0, comment="下发总额")
    total_withdraw_cny: Mapped[float] = mapped_column(Float, default=0, comment="下发人民币总额")

    # 寄存统计
    total_storage_amount: Mapped[float] = mapped_column(Float, default=0, comment="寄存总额")

    # 手续费统计
    total_fee_amount: Mapped[float] = mapped_column(Float, default=0, comment="手续费总额")

    # 净额
    net_amount: Mapped[float] = mapped_column(Float, default=0, comment="净额（入款-下发）")

    # 是否已保存
    is_saved: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已保存")
