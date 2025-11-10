"""
命令解析工具
"""
import re
from typing import Optional, Tuple, Dict, Any


class CommandParser:
    """命令解析器"""

    # 入款模式
    DEPOSIT_PATTERNS = [
        r'^\+(\d+(?:\.\d+)?)(u)?(?:/(\d+(?:\.\d+)?))?(?:\*(\d+(?:\.\d+)?)%?)?\s*(.*)$',  # +1000 或 +1000u/7.3*12% 备注
        r'^(.+?)\+(\d+(?:\.\d+)?)(u)?(?:/(\d+(?:\.\d+)?))?(?:\*(\d+(?:\.\d+)?)%?)?\s*(.*)$',  # 张三+1000
    ]

    # 下发模式
    WITHDRAW_PATTERNS = [
        r'^下发(\d+(?:\.\d+)?)(r)?(?:/(\d+(?:\.\d+)?))?(?:\*(\d+(?:\.\d+)?)%?)?\s*(.*)$',  # 下发1000
        r'^(.+?)下发(\d+(?:\.\d+)?)(r)?(?:/(\d+(?:\.\d+)?))?(?:\*(\d+(?:\.\d+)?)%?)?\s*(.*)$',  # 张三下发1000
    ]

    # 寄存模式
    STORAGE_PATTERNS = [
        r'^P([+-])(\d+(?:\.\d+)?)\s*(.*)$',  # P+1000 或 P-1000
    ]

    # 修正模式
    CORRECTION_PATTERNS = [
        r'^-(\d+(?:\.\d+)?)\s*(.*)$',  # -1000 (入款修正)
        r'^下发-(\d+(?:\.\d+)?)\s*(.*)$',  # 下发-1000 (下发修正)
    ]

    @staticmethod
    def parse_deposit(text: str) -> Optional[Dict[str, Any]]:
        """
        解析入款命令
        返回: {
            'username': Optional[str],
            'amount': float,
            'currency': str,
            'exchange_rate': Optional[float],
            'fee_rate': Optional[float],
            'note': str
        }
        """
        for pattern in CommandParser.DEPOSIT_PATTERNS:
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 5:  # +1000 格式
                    amount, currency_suffix, rate, fee, note = groups
                    return {
                        'username': None,
                        'amount': float(amount),
                        'currency': 'USDT' if currency_suffix and currency_suffix.lower() == 'u' else 'CNY',
                        'exchange_rate': float(rate) if rate else None,
                        'fee_rate': float(fee) if fee else None,
                        'note': note.strip() if note else ''
                    }
                elif len(groups) == 6:  # 张三+1000 格式
                    username, amount, currency_suffix, rate, fee, note = groups
                    return {
                        'username': username.strip(),
                        'amount': float(amount),
                        'currency': 'USDT' if currency_suffix and currency_suffix.lower() == 'u' else 'CNY',
                        'exchange_rate': float(rate) if rate else None,
                        'fee_rate': float(fee) if fee else None,
                        'note': note.strip() if note else ''
                    }
        return None

    @staticmethod
    def parse_withdraw(text: str) -> Optional[Dict[str, Any]]:
        """
        解析下发命令
        返回格式同parse_deposit
        """
        for pattern in CommandParser.WITHDRAW_PATTERNS:
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                groups = match.groups()
                if len(groups) == 5:  # 下发1000 格式
                    amount, currency_suffix, rate, fee, note = groups
                    return {
                        'username': None,
                        'amount': float(amount),
                        'currency': 'USDT' if currency_suffix and currency_suffix.lower() == 'r' else 'CNY',
                        'exchange_rate': float(rate) if rate else None,
                        'fee_rate': float(fee) if fee else None,
                        'note': note.strip() if note else ''
                    }
                elif len(groups) == 6:  # 张三下发1000 格式
                    username, amount, currency_suffix, rate, fee, note = groups
                    return {
                        'username': username.strip(),
                        'amount': float(amount),
                        'currency': 'USDT' if currency_suffix and currency_suffix.lower() == 'r' else 'CNY',
                        'exchange_rate': float(rate) if rate else None,
                        'fee_rate': float(fee) if fee else None,
                        'note': note.strip() if note else ''
                    }
        return None

    @staticmethod
    def parse_storage(text: str) -> Optional[Dict[str, Any]]:
        """
        解析寄存命令
        返回: {
            'operation': str,  # '+' or '-'
            'amount': float,
            'note': str
        }
        """
        for pattern in CommandParser.STORAGE_PATTERNS:
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                operation, amount, note = match.groups()
                return {
                    'operation': operation,
                    'amount': float(amount),
                    'note': note.strip() if note else ''
                }
        return None

    @staticmethod
    def parse_correction(text: str) -> Optional[Dict[str, Any]]:
        """
        解析修正命令
        返回: {
            'type': str,  # 'deposit' or 'withdraw'
            'amount': float,
            'note': str
        }
        """
        for i, pattern in enumerate(CommandParser.CORRECTION_PATTERNS):
            match = re.match(pattern, text.strip(), re.IGNORECASE)
            if match:
                if i == 0:  # 入款修正
                    amount, note = match.groups()
                    return {
                        'type': 'deposit',
                        'amount': float(amount),
                        'note': note.strip() if note else ''
                    }
                elif i == 1:  # 下发修正
                    amount, note = match.groups()
                    return {
                        'type': 'withdraw',
                        'amount': float(amount),
                        'note': note.strip() if note else ''
                    }
        return None

    @staticmethod
    def parse_rate_setting(text: str) -> Optional[Dict[str, Any]]:
        """
        解析汇率/费率设置命令
        设置汇率7.3
        设置费率3
        设置张三汇率7.3
        设置张三费率3
        """
        # 设置汇率
        match = re.match(r'^设置汇率(\d+(?:\.\d+)?)$', text.strip())
        if match:
            return {'type': 'exchange_rate', 'username': None, 'value': float(match.group(1))}

        # 设置费率
        match = re.match(r'^设置费率(\d+(?:\.\d+)?)%?$', text.strip())
        if match:
            return {'type': 'fee_rate', 'username': None, 'value': float(match.group(1))}

        # 设置某人汇率
        match = re.match(r'^设置(.+?)汇率(\d+(?:\.\d+)?)$', text.strip())
        if match:
            return {'type': 'exchange_rate', 'username': match.group(1).strip(), 'value': float(match.group(2))}

        # 设置某人费率
        match = re.match(r'^设置(.+?)费率(\d+(?:\.\d+)?)%?$', text.strip())
        if match:
            return {'type': 'fee_rate', 'username': match.group(1).strip(), 'value': float(match.group(2))}

        return None

    @staticmethod
    def parse_display_count(text: str) -> Optional[Dict[str, Any]]:
        """
        解析显示条数设置
        设置入款条数5
        设置下发条数5
        """
        match = re.match(r'^设置(入款|下发)条数(\d+)$', text.strip())
        if match:
            trans_type = 'deposit' if match.group(1) == '入款' else 'withdraw'
            return {'type': trans_type, 'count': int(match.group(2))}
        return None

    @staticmethod
    def parse_currency_display(text: str) -> Optional[str]:
        """
        解析币种显示设置
        设置币种AUD
        """
        match = re.match(r'^设置币种([A-Z]+)$', text.strip())
        if match:
            return match.group(1)
        return None

    @staticmethod
    def parse_day_cut_time(text: str) -> Optional[str]:
        """
        解析日切时间设置
        设置日切时间23:59
        """
        match = re.match(r'^设置日切时间(\d{1,2}):(\d{2})$', text.strip())
        if match:
            hour, minute = match.groups()
            return f"{hour.zfill(2)}:{minute}"
        return None

    @staticmethod
    def is_trc20_address(text: str) -> bool:
        """
        判断是否为TRC20地址
        """
        return bool(re.match(r'^T[A-Za-z0-9]{33}$', text.strip()))
