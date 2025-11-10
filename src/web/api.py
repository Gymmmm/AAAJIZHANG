"""
FastAPI Web应用 - API路由
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime, timedelta

from ..models import (
    User, Order, BotInstance, Transaction, DailySummary, Group,
    OrderStatus, BotStatus, get_db
)
from .auth import (
    get_current_user, get_current_admin, get_current_super_admin,
    create_access_token, verify_password, get_password_hash
)
from ..services.payment_service import PaymentService
from ..services.bot_manager import bot_manager

router = APIRouter()


# ==================== 数据模型 ====================

class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    telegram_username: Optional[str]
    subscription_expires: Optional[datetime]
    max_bots: int


class ChangePasswordRequest(BaseModel):
    old_password: str
    new_password: str


class BotInstanceResponse(BaseModel):
    id: int
    bot_username: Optional[str]
    bot_name: Optional[str]
    status: str
    total_groups: int
    total_transactions: int
    started_at: Optional[datetime]


# ==================== 认证相关 ====================

@router.post("/auth/login", response_model=TokenResponse)
async def login(
    request: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    """用户登录"""
    query = select(User).where(User.username == request.username)
    result = await db.execute(query)
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(status_code=401, detail="用户名或密码错误")

    if not user.is_active:
        raise HTTPException(status_code=400, detail="账户已被禁用")

    access_token = create_access_token(data={"sub": user.username})
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/auth/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """获取当前用户信息"""
    return current_user


@router.post("/auth/change-password")
async def change_password(
    request: ChangePasswordRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """修改密码"""
    if not verify_password(request.old_password, current_user.password_hash):
        raise HTTPException(status_code=400, detail="原密码错误")

    current_user.password_hash = get_password_hash(request.new_password)
    await db.commit()

    return {"message": "密码修改成功"}


# ==================== 机器人管理 ====================

@router.get("/bots", response_model=List[BotInstanceResponse])
async def list_bots(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取用户的机器人列表"""
    bots = await bot_manager.get_user_instances(db, current_user.id)
    return bots


@router.post("/bots/{bot_id}/start")
async def start_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """启动机器人"""
    # 验证机器人所有权
    query = select(BotInstance).where(
        BotInstance.id == bot_id,
        BotInstance.user_id == current_user.id
    )
    result = await db.execute(query)
    bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="机器人不存在")

    success = await bot_manager.start_instance(db, bot_id)
    if not success:
        raise HTTPException(status_code=500, detail="启动失败")

    return {"message": "机器人启动成功"}


@router.post("/bots/{bot_id}/stop")
async def stop_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """停止机器人"""
    query = select(BotInstance).where(
        BotInstance.id == bot_id,
        BotInstance.user_id == current_user.id
    )
    result = await db.execute(query)
    bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="机器人不存在")

    success = await bot_manager.stop_instance(db, bot_id)
    if not success:
        raise HTTPException(status_code=500, detail="停止失败")

    return {"message": "机器人停止成功"}


@router.delete("/bots/{bot_id}")
async def delete_bot(
    bot_id: int,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """删除机器人"""
    query = select(BotInstance).where(
        BotInstance.id == bot_id,
        BotInstance.user_id == current_user.id
    )
    result = await db.execute(query)
    bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="机器人不存在")

    success = await bot_manager.delete_instance(db, bot_id)
    if not success:
        raise HTTPException(status_code=500, detail="删除失败")

    return {"message": "机器人删除成功"}


# ==================== 账单查询 ====================

@router.get("/bills/{bot_id}")
async def get_bills(
    bot_id: int,
    group_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账单记录"""
    # 验证机器人所有权
    query = select(BotInstance).where(
        BotInstance.id == bot_id,
        BotInstance.user_id == current_user.id
    )
    result = await db.execute(query)
    bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="机器人不存在")

    # 查询账单
    query = select(Transaction).where(Transaction.is_deleted == False)

    if group_id:
        query = query.where(Transaction.group_id == group_id)

    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)

    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)

    query = query.order_by(Transaction.transaction_date.desc()).limit(100)

    result = await db.execute(query)
    transactions = result.scalars().all()

    return [
        {
            "id": t.id,
            "type": t.transaction_type,
            "amount": t.amount,
            "currency": t.currency,
            "cny_amount": t.cny_amount,
            "fee_amount": t.fee_amount,
            "final_amount": t.final_amount,
            "note": t.note,
            "user_id": t.user_id,
            "username": t.username,
            "first_name": t.first_name,
            "transaction_date": t.transaction_date,
        }
        for t in transactions
    ]


@router.get("/bills/{bot_id}/summary")
async def get_bills_summary(
    bot_id: int,
    group_id: Optional[int] = None,
    start_date: Optional[datetime] = None,
    end_date: Optional[datetime] = None,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """获取账单汇总"""
    # 验证机器人所有权
    query = select(BotInstance).where(
        BotInstance.id == bot_id,
        BotInstance.user_id == current_user.id
    )
    result = await db.execute(query)
    bot = result.scalar_one_or_none()

    if not bot:
        raise HTTPException(status_code=404, detail="机器人不存在")

    # 查询汇总
    query = select(Transaction).where(Transaction.is_deleted == False)

    if group_id:
        query = query.where(Transaction.group_id == group_id)

    if start_date:
        query = query.where(Transaction.transaction_date >= start_date)

    if end_date:
        query = query.where(Transaction.transaction_date <= end_date)

    result = await db.execute(query)
    transactions = result.scalars().all()

    # 计算汇总
    summary = {
        "deposit_count": 0,
        "deposit_amount": 0.0,
        "deposit_cny": 0.0,
        "withdraw_count": 0,
        "withdraw_amount": 0.0,
        "withdraw_cny": 0.0,
        "total_fee": 0.0,
        "net_amount": 0.0
    }

    for t in transactions:
        if t.transaction_type == "deposit":
            summary["deposit_count"] += 1
            summary["deposit_amount"] += t.amount
            summary["deposit_cny"] += t.cny_amount or 0
            summary["total_fee"] += t.fee_amount or 0
        elif t.transaction_type == "withdraw":
            summary["withdraw_count"] += 1
            summary["withdraw_amount"] += t.amount
            summary["withdraw_cny"] += t.cny_amount or 0

    summary["net_amount"] = summary["deposit_cny"] - summary["withdraw_cny"]

    return summary


# ==================== 支付回调 ====================

@router.post("/payment/callback")
async def payment_callback(
    request: Request,
    db: AsyncSession = Depends(get_db)
):
    """支付回调处理"""
    try:
        callback_data = await request.json()

        # 处理回调
        success = await PaymentService.handle_payment_callback(db, callback_data)

        if success:
            # 如果支付成功，激活用户订阅
            order_id = callback_data.get("order_id")
            query = select(Order).where(Order.order_no == order_id)
            result = await db.execute(query)
            order = result.scalar_one_or_none()

            if order and order.status == OrderStatus.PAID:
                # 更新用户订阅
                query_user = select(User).where(User.id == order.user_id)
                result = await db.execute(query_user)
                user = result.scalar_one_or_none()

                if user:
                    if order.product_type == "monthly":
                        days = 30
                    elif order.product_type == "yearly":
                        days = 365
                    else:  # lifetime
                        days = 36500

                    if user.subscription_expires and user.subscription_expires > datetime.utcnow():
                        user.subscription_expires += timedelta(days=days)
                    else:
                        user.subscription_expires = datetime.utcnow() + timedelta(days=days)

                    await db.commit()

            return JSONResponse({"status": "success"})

        return JSONResponse({"status": "failed"}, status_code=400)

    except Exception as e:
        return JSONResponse({"status": "error", "message": str(e)}, status_code=500)


# ==================== 管理员API ====================

@router.get("/admin/users", response_model=List[UserResponse])
async def list_users(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取所有用户列表"""
    query = select(User)
    result = await db.execute(query)
    users = result.scalars().all()
    return users


@router.get("/admin/stats")
async def get_stats(
    current_user: User = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db)
):
    """获取系统统计"""
    # 总用户数
    query = select(func.count(User.id))
    result = await db.execute(query)
    total_users = result.scalar()

    # 总机器人数
    query = select(func.count(BotInstance.id))
    result = await db.execute(query)
    total_bots = result.scalar()

    # 运行中的机器人
    query = select(func.count(BotInstance.id)).where(BotInstance.status == BotStatus.RUNNING)
    result = await db.execute(query)
    running_bots = result.scalar()

    # 总订单数
    query = select(func.count(Order.id))
    result = await db.execute(query)
    total_orders = result.scalar()

    # 已支付订单
    query = select(func.count(Order.id)).where(Order.status == OrderStatus.PAID)
    result = await db.execute(query)
    paid_orders = result.scalar()

    # 总收入
    query = select(func.sum(Order.price)).where(Order.status == OrderStatus.PAID)
    result = await db.execute(query)
    total_revenue = result.scalar() or 0

    return {
        "total_users": total_users,
        "total_bots": total_bots,
        "running_bots": running_bots,
        "total_orders": total_orders,
        "paid_orders": paid_orders,
        "total_revenue": float(total_revenue)
    }
