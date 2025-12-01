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
        result = {
            'amount': amount,
            'currency': currency,
            'cny_amount': 0.0,
            'fee_amount': 0.0,
            'final_amount': amount
        }

        # 如果是USDT，需要转换为人民币
        if currency == 'USDT' and exchange_rate:
            result['cny_amount'] = amount * exchange_rate
            base_amount = result['cny_amount']
        else:
            result['cny_amount'] = amount
            base_amount = amount

        # 计算手续费
        if fee_rate:
            result['fee_amount'] = base_amount * (fee_rate / 100)
            result['final_amount'] = base_amount - result['fee_amount']
        else:
            result['final_amount'] = base_amount

        # 保留2位小数
        result['cny_amount'] = round(result['cny_amount'], 2)
        result['fee_amount'] = round(result['fee_amount'], 2)
        result['final_amount'] = round(result['final_amount'], 2)

        return result

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
        summary = {
            'deposit_count': 0,
            'deposit_amount': 0.0,
            'deposit_cny': 0.0,
            'withdraw_count': 0,
            'withdraw_amount': 0.0,
            'withdraw_cny': 0.0,
            'storage_amount': 0.0,
            'total_fee': 0.0,
            'net_amount': 0.0
        }

        for trans in transactions:
            if trans.is_deleted:
                continue

            if trans.transaction_type == 'deposit':
                summary['deposit_count'] += 1
                summary['deposit_amount'] += trans.amount
                summary['deposit_cny'] += trans.cny_amount or 0
                summary['total_fee'] += trans.fee_amount or 0
            elif trans.transaction_type == 'withdraw':
                summary['withdraw_count'] += 1
                summary['withdraw_amount'] += trans.amount
                summary['withdraw_cny'] += trans.cny_amount or 0
                summary['total_fee'] += trans.fee_amount or 0
            elif trans.transaction_type == 'storage':
                summary['storage_amount'] += trans.amount

        summary['net_amount'] = summary['deposit_cny'] - summary['withdraw_cny']

        # 保留2位小数
        for key in summary:
            if isinstance(summary[key], float):
                summary[key] = round(summary[key], 2)

        return summary
