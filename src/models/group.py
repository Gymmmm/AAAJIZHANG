"""
群组相关数据模型
"""
from datetime import datetime, time
from typing import Optional
from sqlalchemy import String, BigInteger, Boolean, Float, Integer, Time, JSON, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Group(Base):
    """群组模型"""
    __tablename__ = "groups"

    # 基本信息
    group_id: Mapped[int] = mapped_column(BigInteger, unique=True, index=True, comment="Telegram群组ID")
    group_name: Mapped[str] = mapped_column(String(255), comment="群组名称")
    group_type: Mapped[str] = mapped_column(String(50), default="group", comment="群组类型: group, supergroup, channel")

    # 状态配置
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="记账是否开启")
    is_muted: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否禁言模式（下课）")

    # 显示配置
    display_mode: Mapped[str] = mapped_column(String(20), default="pure", comment="显示模式: pure(纯净), reply(显示回复人), operator(显示操作人)")
    currency_mode: Mapped[str] = mapped_column(String(20), default="single", comment="币种模式: single(单币), dual(双币)")
    currency_display: Mapped[str] = mapped_column(String(10), default="USDT", comment="显示的币种")
    pin_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否启用置顶")
    deposit_display_count: Mapped[int] = mapped_column(Integer, default=5, comment="入款显示条数")
    withdraw_display_count: Mapped[int] = mapped_column(Integer, default=5, comment="下发显示条数")
    category_enabled: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否启用账单分类")

    # 参数配置
    exchange_rate: Mapped[float] = mapped_column(Float, default=7.3, comment="默认汇率")
    fee_rate: Mapped[float] = mapped_column(Float, default=3, comment="默认费率(%)")
    real_time_rate: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否使用实时汇率")

    # 日切配置
    day_cut_time: Mapped[Optional[time]] = mapped_column(Time, nullable=True, comment="日切时间")
    last_day_cut: Mapped[Optional[datetime]] = mapped_column(nullable=True, comment="上次日切时间")

    # 操作人配置
    all_members_operator: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否全员可操作")

    # 其他配置
    group_tag: Mapped[Optional[str]] = mapped_column(String(50), nullable=True, comment="分组标签")
    withdraw_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="下发地址")

    # 广告配置
    top_ad: Mapped[Optional[str]] = mapped_column(String(500), nullable=True, comment="顶部广告")

    # 试用与权限控制
    trial_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="免费试用到期时间")
    access_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="付费权限到期时间")
    is_whitelisted: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否白名单（永久可用）")


class GroupOperator(Base):
    """群组操作人模型"""
    __tablename__ = "group_operators"

    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="群组ID")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="用户ID")
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户名")
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="名字")
    is_global: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否全局操作人")


class UserConfig(Base):
    """用户个人配置模型（群组内）"""
    __tablename__ = "user_configs"

    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="群组ID")
    user_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="用户ID")
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="用户名")
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="名字")

    # 个人费率配置
    exchange_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="个人汇率")
    fee_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="个人费率(%)")
