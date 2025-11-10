"""
SaaS多租户相关数据模型
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, BigInteger, Boolean, Float, Integer, Text, DateTime, Enum as SQLEnum
from sqlalchemy.orm import Mapped, mapped_column
import enum

from .database import Base


class UserRole(str, enum.Enum):
    """用户角色"""
    SUPER_ADMIN = "super_admin"  # 超级管理员
    ADMIN = "admin"  # 管理员
    TENANT = "tenant"  # 租户


class OrderStatus(str, enum.Enum):
    """订单状态"""
    PENDING = "pending"  # 待支付
    PAID = "paid"  # 已支付
    EXPIRED = "expired"  # 已过期
    CANCELLED = "cancelled"  # 已取消


class BotStatus(str, enum.Enum):
    """机器人状态"""
    CREATING = "creating"  # 创建中
    RUNNING = "running"  # 运行中
    STOPPED = "stopped"  # 已停止
    ERROR = "error"  # 错误


class User(Base):
    """用户模型"""
    __tablename__ = "users"

    # 基本信息
    username: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="用户名")
    password_hash: Mapped[str] = mapped_column(String(255), comment="密码哈希")
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True, comment="邮箱")

    # Telegram信息
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True, unique=True, comment="Telegram用户ID")
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Telegram用户名")
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="Telegram名字")

    # 角色和状态
    role: Mapped[str] = mapped_column(String(20), default=UserRole.TENANT, comment="用户角色")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, comment="是否激活")

    # 订阅信息
    subscription_expires: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="订阅到期时间")
    max_bots: Mapped[int] = mapped_column(Integer, default=1, comment="最大机器人数量")


class Order(Base):
    """订单模型"""
    __tablename__ = "orders"

    # 订单信息
    order_no: Mapped[str] = mapped_column(String(50), unique=True, index=True, comment="订单号")
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户ID")

    # 商品信息
    product_name: Mapped[str] = mapped_column(String(100), comment="商品名称")
    product_type: Mapped[str] = mapped_column(String(50), comment="商品类型: monthly, yearly, lifetime")
    price: Mapped[float] = mapped_column(Float, comment="价格（USDT）")

    # 支付信息
    payment_address: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="支付地址")
    payment_amount: Mapped[Optional[float]] = mapped_column(Float, nullable=True, comment="实际支付金额")
    payment_tx: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="交易哈希")
    payment_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="支付时间")

    # 订单状态
    status: Mapped[str] = mapped_column(String(20), default=OrderStatus.PENDING, comment="订单状态")
    expires_at: Mapped[datetime] = mapped_column(DateTime, comment="订单过期时间")

    # 备注
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="备注")


class BotInstance(Base):
    """机器人实例模型"""
    __tablename__ = "bot_instances"

    # 所属用户
    user_id: Mapped[int] = mapped_column(Integer, index=True, comment="用户ID")

    # 机器人信息
    bot_token: Mapped[str] = mapped_column(String(255), unique=True, comment="机器人Token")
    bot_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="机器人用户名")
    bot_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="机器人名称")

    # 运行状态
    status: Mapped[str] = mapped_column(String(20), default=BotStatus.CREATING, comment="运行状态")
    process_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, comment="进程ID")

    # 配置信息
    config: Mapped[Optional[str]] = mapped_column(Text, nullable=True, comment="配置信息(JSON)")

    # 统计信息
    total_groups: Mapped[int] = mapped_column(Integer, default=0, comment="总群组数")
    total_transactions: Mapped[int] = mapped_column(Integer, default=0, comment="总交易数")

    # 时间信息
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="启动时间")
    stopped_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="停止时间")
    last_active: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="最后活跃时间")


class PaymentCallback(Base):
    """支付回调记录"""
    __tablename__ = "payment_callbacks"

    # 回调信息
    trade_id: Mapped[str] = mapped_column(String(100), index=True, comment="交易ID")
    order_id: Mapped[str] = mapped_column(String(100), index=True, comment="订单ID")
    amount: Mapped[float] = mapped_column(Float, comment="金额")
    actual_amount: Mapped[float] = mapped_column(Float, comment="实际金额")
    token: Mapped[str] = mapped_column(String(50), comment="币种")

    # 区块链信息
    block_transaction_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="区块链交易ID")
    status: Mapped[int] = mapped_column(Integer, comment="状态: 1已支付, 2已过期")

    # 完整回调数据
    callback_data: Mapped[str] = mapped_column(Text, comment="完整回调数据(JSON)")

    # 处理状态
    processed: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已处理")
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, comment="处理时间")


class SystemConfig(Base):
    """系统配置"""
    __tablename__ = "system_configs"

    key: Mapped[str] = mapped_column(String(100), unique=True, index=True, comment="配置键")
    value: Mapped[str] = mapped_column(Text, comment="配置值")
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, comment="描述")
    is_public: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否公开")
