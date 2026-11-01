"""
计算工具
"""
from typing import Optional, Dict, Any


class Calculator:
    """金额计算器"""

    @staticmethod
    def calculate_transaction(
        amount: float,
        currency: str = "USDT",
        exchange_rate: Optional[float] = None,
        fee_rate: Optional[float] = None
    ) -> Dict[str, Any]:
        """
        计算交易金额

        Args:
            amount: 原始金额
            currency: 币种 (USDT/CNY)
            exchange_rate: 汇率
            fee_rate: 费率(%)

        Returns:
            {
                'amount': float,  # 原始金额
                'currency': str,
                'cny_amount': float,  # 人民币金额
                'fee_amount': float,  # 手续费
                'final_amount': float  # 最终金额
            }
        """
        from decimal import Decimal, ROUND_HALF_UP
        D = lambda value: Decimal(str(value))
        amount = D(amount)
        rate = D(exchange_rate) if exchange_rate is not None else None
        fee = D(fee_rate) if fee_rate is not None else Decimal(0)
        if not amount.is_finite() or (rate is not None and (not rate.is_finite() or rate <= 0)):
            raise ValueError('金额或汇率无效。')
        if not fee.is_finite() or not -100 <= fee <= 100:
            raise ValueError('费率无效。')
        cents = lambda value: value.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
        base = amount * rate if currency == 'USDT' and rate else amount
        charge = cents(base * fee / 100)
        return dict(amount=amount, currency=currency, cny_amount=cents(base),
                    fee_amount=charge, final_amount=cents(base - charge))

    @staticmethod
    def evaluate_expression(expression: str) -> Optional[float]:
        """
        安全计算数学表达式
        只支持基本的四则运算
        """
        try:
            # 只允许数字、运算符和括号
            allowed_chars = set('0123456789+-*/.()')
            if not all(c in allowed_chars or c.isspace() for c in expression):
                return None

            # 使用eval计算（已经过滤了危险字符）
            result = eval(expression, {"__builtins__": {}}, {})
            return round(float(result), 2)
        except Exception:
            return None

    @staticmethod
    def format_currency(amount: float, currency: str = "CNY") -> str:
        """
        格式化货币显示
        """
        if currency == "USDT":
            return f"{amount:.2f} USDT"
        else:
            return f"¥{amount:.2f}"

    @staticmethod
    def calculate_summary(transactions: list) -> Dict[str, Any]:
        """
        计算交易汇总

        Args:
            transactions: 交易记录列表

        Returns:
            汇总数据字典
        """
        from decimal import Decimal
        D = lambda value: Decimal(str(value or 0))
        summary = dict(deposit_count=0, deposit_amount=Decimal(0), deposit_cny=Decimal(0),
                       withdraw_count=0, withdraw_amount=Decimal(0), withdraw_cny=Decimal(0),
                       storage_amount=Decimal(0), total_fee=Decimal(0), net_amount=Decimal(0))
        for trans in transactions:
            if trans.is_deleted:
                continue
            kind = trans.transaction_type
            if kind == 'storage':
                summary['storage_amount'] += D(trans.amount)
                continue
            if kind not in ('deposit', 'withdraw'):
                continue
            summary[kind + '_count'] += 1
            # Normalize mixed currencies rather than labelling CNY amounts as USDT.
            rate = D(trans.exchange_rate)
            u = D(trans.amount) if trans.currency == 'USDT' else (D(trans.amount) / rate if rate else Decimal(0))
            summary[kind + '_amount'] += u
            summary[kind + '_cny'] += D(trans.cny_amount)
            summary['total_fee'] += D(trans.fee_amount) if kind == 'deposit' else -D(trans.fee_amount)
        summary['net_amount'] = summary['deposit_cny'] - summary['withdraw_cny'] - summary['total_fee']
        return {key: (value.quantize(Decimal('0.01')) if isinstance(value, Decimal) else value)
                for key, value in summary.items()}
