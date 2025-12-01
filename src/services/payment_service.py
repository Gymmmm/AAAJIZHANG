"""
支付服务 - epusdt集成
"""
import hashlib
import time
from typing import Optional, Dict, Any
import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import Order, PaymentCallback, OrderStatus, SystemConfig


class EpusdtService:
    """epusdt支付服务"""

    def __init__(self, api_url: str, api_key: str):
        """
        初始化epusdt服务

        Args:
            api_url: epusdt API地址
            api_key: API密钥
        """
        self.api_url = api_url.rstrip('/')
        self.api_key = api_key

    def _generate_sign(self, params: dict) -> str:
        """
        生成签名

        Args:
            params: 请求参数

        Returns:
            签名字符串
        """
        # 按key排序
        sorted_params = sorted(params.items())
        # 拼接成 key=value& 格式
        sign_str = '&'.join([f"{k}={v}" for k, v in sorted_params if v is not None])
        # 加上API密钥
        sign_str += f"&key={self.api_key}"
        # MD5加密
        return hashlib.md5(sign_str.encode()).hexdigest()

    async def create_order(
        self,
        order_id: str,
        amount: float,
        notify_url: str,
        redirect_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            order_id: 订单号
            amount: 金额
            notify_url: 回调通知URL
            redirect_url: 支付后跳转URL

        Returns:
            订单信息
        """
        params = {
            "order_id": order_id,
            "amount": amount,
            "notify_url": notify_url,
            "redirect_url": redirect_url or notify_url,
        }

        # 添加签名
        params["sign"] = self._generate_sign(params)

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{self.api_url}/api/v1/order/create",
                json=params,
                timeout=10.0
            )
            return response.json()

    async def query_order(self, order_id: str) -> Dict[str, Any]:
        """
        查询订单状态

        Args:
            order_id: 订单号

        Returns:
            订单信息
        """
        params = {
            "order_id": order_id,
        }

        params["sign"] = self._generate_sign(params)

        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/api/v1/order/query",
                params=params,
                timeout=10.0
            )
            return response.json()

    def verify_callback(self, callback_data: dict) -> bool:
        """
        验证回调签名

        Args:
            callback_data: 回调数据

        Returns:
            是否验证通过
        """
        sign = callback_data.get("sign")
        if not sign:
            return False

        # 移除sign字段
        params = {k: v for k, v in callback_data.items() if k != "sign"}
        # 生成签名
        calculated_sign = self._generate_sign(params)

        return sign == calculated_sign


class PaymentService:
    """支付服务"""

    @staticmethod
    async def get_epusdt_service(db: AsyncSession) -> Optional[EpusdtService]:
        """
        获取epusdt服务实例

        Args:
            db: 数据库会话

        Returns:
            EpusdtService实例或None
        """
        # 获取配置
        query = select(SystemConfig).where(SystemConfig.key == "epusdt_api_url")
        result = await db.execute(query)
        api_url_config = result.scalar_one_or_none()

        query = select(SystemConfig).where(SystemConfig.key == "epusdt_api_key")
        result = await db.execute(query)
        api_key_config = result.scalar_one_or_none()

        if not api_url_config or not api_key_config:
            return None

        return EpusdtService(
            api_url=api_url_config.value,
            api_key=api_key_config.value
        )

    @staticmethod
    async def create_payment_order(
        db: AsyncSession,
        order: Order,
        notify_url: str,
        redirect_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        创建支付订单

        Args:
            db: 数据库会话
            order: 订单对象
            notify_url: 回调通知URL
            redirect_url: 支付后跳转URL

        Returns:
            支付订单信息
        """
        epusdt = await PaymentService.get_epusdt_service(db)
        if not epusdt:
            raise ValueError("epusdt service not configured")

        result = await epusdt.create_order(
            order_id=order.order_no,
            amount=order.price,
            notify_url=notify_url,
            redirect_url=redirect_url
        )

        # 更新订单支付地址
        if result.get("code") == 200 and result.get("data"):
            order.payment_address = result["data"].get("payment_url")
            await db.commit()

        return result

    @staticmethod
    async def handle_payment_callback(
        db: AsyncSession,
        callback_data: dict
    ) -> bool:
        """
        处理支付回调

        Args:
            db: 数据库会话
            callback_data: 回调数据

        Returns:
            是否处理成功
        """
        # 验证签名
        epusdt = await PaymentService.get_epusdt_service(db)
        if not epusdt:
            return False

        if not epusdt.verify_callback(callback_data):
            return False

        # 保存回调记录
        import json
        callback_record = PaymentCallback(
            trade_id=callback_data.get("trade_id", ""),
            order_id=callback_data.get("order_id", ""),
            amount=float(callback_data.get("amount", 0)),
            actual_amount=float(callback_data.get("actual_amount", 0)),
            token=callback_data.get("token", ""),
            block_transaction_id=callback_data.get("block_transaction_id"),
            status=int(callback_data.get("status", 0)),
            callback_data=json.dumps(callback_data),
            processed=False
        )
        db.add(callback_record)

        # 查找订单
        order_id = callback_data.get("order_id")
        query = select(Order).where(Order.order_no == order_id)
        result = await db.execute(query)
        order = result.scalar_one_or_none()

        if not order:
            await db.commit()
            return False

        # 更新订单状态
        if callback_data.get("status") == 1:  # 已支付
            order.status = OrderStatus.PAID
            order.payment_amount = float(callback_data.get("actual_amount", 0))
            order.payment_tx = callback_data.get("block_transaction_id")
            order.payment_time = callback_data.get("payment_time")

            # 标记回调已处理
            callback_record.processed = True
            callback_record.processed_at = callback_data.get("payment_time")

        await db.commit()
        return True

    @staticmethod
    async def query_order_status(
        db: AsyncSession,
        order_no: str
    ) -> Optional[Dict[str, Any]]:
        """
        查询订单支付状态

        Args:
            db: 数据库会话
            order_no: 订单号

        Returns:
            订单状态信息
        """
        epusdt = await PaymentService.get_epusdt_service(db)
        if not epusdt:
            return None

        return await epusdt.query_order(order_no)
