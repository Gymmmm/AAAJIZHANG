"""
团队模型（单群多盘口）
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import String, BigInteger, Boolean, DateTime
from sqlalchemy.orm import Mapped, mapped_column

from .database import Base


class Team(Base):
    """团队模型"""
    __tablename__ = "teams"

    team_id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    group_id: Mapped[int] = mapped_column(BigInteger, index=True, comment="所属群组")
    name: Mapped[str] = mapped_column(String(100), comment="团队名称")
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, comment="是否已归档")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class TeamMember(Base):
    """团队成员"""
    __tablename__ = "team_members"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    team_id: Mapped[int] = mapped_column(BigInteger, index=True)
    user_id: Mapped[int] = mapped_column(BigInteger, index=True)
    username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
