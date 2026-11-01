"""Additive ledger metadata: message deduplication, audit trail and closed periods."""
from datetime import datetime
from typing import Optional
from sqlalchemy import BigInteger, String, Text, DateTime, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .database import Base

class LedgerReceipt(Base):
    __tablename__ = 'ledger_receipts'
    __table_args__ = (UniqueConstraint('group_id', 'message_id'),)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    message_id: Mapped[int] = mapped_column(BigInteger)
    transaction_id: Mapped[Optional[int]] = mapped_column(nullable=True, index=True)
    reply_message_id: Mapped[Optional[int]] = mapped_column(BigInteger, nullable=True)
    exact_values: Mapped[str] = mapped_column(Text, default='{}')

class LedgerAudit(Base):
    __tablename__ = 'ledger_audit'
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    transaction_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    action: Mapped[str] = mapped_column(String(40))
    detail: Mapped[str] = mapped_column(Text, default='')

class KnownMember(Base):
    __tablename__ = 'known_members'
    __table_args__ = (UniqueConstraint('group_id', 'user_id'),)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[str] = mapped_column(String(255))

class LedgerPeriod(Base):
    __tablename__ = 'ledger_periods'
    __table_args__ = (UniqueConstraint('group_id', 'end_at'),)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime)
    end_at: Mapped[datetime] = mapped_column(DateTime)
    actor_id: Mapped[int] = mapped_column(BigInteger)
    summary: Mapped[str] = mapped_column(Text)
