"""
汇率查询服务
"""
import httpx
from typing import Optional, Dict
from config import config


class ExchangeService:
    """汇率服务类"""

    @staticmethod
    async def get_huobi_usdt_price() -> Optional[float]:
        """
        获取火币USDT价格
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://api.huobi.pro/market/detail/merged",
                    params={"symbol": "usdtcny"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("status") == "ok":
                        tick = data.get("tick", {})
                        close_price = tick.get("close")
                        return float(close_price) if close_price else None
        except Exception as e:
            print(f"Error fetching Huobi price: {e}")
        return None

    @staticmethod
    async def get_okex_usdt_price() -> Optional[float]:
        """
        获取欧易USDT价格
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    "https://www.okex.com/api/v5/market/ticker",
                    params={"instId": "USDT-CNY"},
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    if data.get("code") == "0":
                        ticker_data = data.get("data", [])
                        if ticker_data:
                            last_price = ticker_data[0].get("last")
                            return float(last_price) if last_price else None
        except Exception as e:
            print(f"Error fetching OKEx price: {e}")
        return None

    @staticmethod
    async def get_tron_address_info(address: str) -> Optional[Dict]:
        """
        查询TRC20地址信息
        """
        try:
            async with httpx.AsyncClient() as client:
                # 使用TronScan API
                response = await client.get(
                    f"https://apilist.tronscan.org/api/account",
                    params={"address": address},
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data
        except Exception as e:
            print(f"Error fetching TRON address info: {e}")
        return None

    @staticmethod
    async def get_tron_transactions(address: str, limit: int = 20) -> Optional[list]:
        """
        查询TRC20地址交易记录
        """
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"https://apilist.tronscan.org/api/transaction",
                    params={
                        "address": address,
                        "limit": limit,
                        "sort": "-timestamp"
                    },
                    timeout=10.0
                )
                if response.status_code == 200:
                    data = response.json()
                    return data.get("data", [])
        except Exception as e:
            print(f"Error fetching TRON transactions: {e}")
        return None

    @staticmethod
    async def format_tron_address_info(address_info: Dict) -> str:
        """
        格式化TRC20地址信息
        """
        if not address_info:
            return "❌ 无法获取地址信息"

        lines = [
            "🔍 地址信息",
            "=" * 30,
            f"地址: {address_info.get('address', 'N/A')}",
            f"余额: {address_info.get('balance', 0) / 1_000_000:.2f} TRX",
        ]

        # TRC20代币余额
        tokens = address_info.get("trc20token_balances", [])
        if tokens:
            lines.append("\nTRC20代币:")
            for token in tokens[:5]:  # 只显示前5个
                token_name = token.get("tokenName", "Unknown")
                token_balance = token.get("balance", "0")
                token_decimals = int(token.get("tokenDecimal", 0))
                balance_float = float(token_balance) / (10 ** token_decimals)
                lines.append(f"  • {token_name}: {balance_float:.2f}")

        return "\n".join(lines)

    @staticmethod
    async def format_tron_transactions(transactions: list) -> str:
        """
        格式化TRC20交易记录
        """
        if not transactions:
            return "❌ 暂无交易记录"

        lines = [
            "📝 交易记录",
            "=" * 30,
        ]

        for i, tx in enumerate(transactions[:10], 1):  # 只显示前10条
            tx_hash = tx.get("hash", "N/A")[:16] + "..."
            tx_type = tx.get("contractType", "Unknown")
            timestamp = tx.get("timestamp", 0)

            from datetime import datetime
            date_str = datetime.fromtimestamp(timestamp / 1000).strftime("%Y-%m-%d %H:%M")

            lines.append(f"\n[{i}] {tx_type}")
            lines.append(f"  时间: {date_str}")
            lines.append(f"  哈希: {tx_hash}")

        return "\n".join(lines)
