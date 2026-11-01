"""
命令解析工具
"""
import re
from typing import Optional, Tuple, Dict, Any


class CommandParser:
    """命令解析器"""

    @staticmethod
    def _parse_entry(text, withdraw=False, correction=False):
        from decimal import Decimal
        number = r"\d+(?:\.\d+)?"
        prefix = r"(?P<name>[^+*/\s]+?)?下发" if withdraw else r"(?P<name>[^+*/\s]+?)?\+"
        if correction and not withdraw:
            prefix = "-"
        sign = "-" if correction and withdraw else ""
        pattern = prefix + sign + r"(?P<amount>" + number + r")(?P<suffix>[uUrR])?(?:/(?P<rate>" + number + r"))?(?:\*(?P<fee>-?" + number + r")%?)?(?:\s+(?P<note>.*))?"
        match = re.fullmatch(pattern, text.strip())
        if not match:
            return None
        g = match.groupdict()
        amount = Decimal(g['amount'])
        suffix = (g.get('suffix') or '').upper()
        if suffix == 'U':
            currency = 'USDT'
        elif suffix == 'R':
            currency = 'CNY'
        else:
            currency = 'CNY'  # 默认 CNY
        if amount <= 0 or amount >= Decimal('1000000000000'):
            raise ValueError('金额必须大于 0，且小于一万亿元。')
        quantum = Decimal('0.000001') if currency == 'USDT' else Decimal('0.01')
        if amount != amount.quantize(quantum):
            raise ValueError('人民币最多两位小数，USDT 最多六位小数。')
        rate = Decimal(g['rate']) if g.get('rate') else None
        fee = Decimal(g['fee']) if g.get('fee') is not None else None
        if rate is not None and not Decimal('0') < rate < Decimal('1000000'):
            raise ValueError('汇率必须大于 0，且小于 1000000。')
        if fee is not None and not Decimal('-100') <= fee <= Decimal('100'):
            raise ValueError('费率须在 -100% 到 100% 之间。')
        return dict(username=g.get('name'), amount=-amount if correction else amount,
                    currency=currency, exchange_rate=rate, fee_rate=fee,
                    note=(g.get('note') or '').strip(), is_correction=correction)

    @staticmethod
    def parse_deposit(text):
        return CommandParser._parse_entry(text)

    @staticmethod
    def parse_withdraw(text):
        return CommandParser._parse_entry(text, withdraw=True)

    @staticmethod
    def parse_storage(text):
        from decimal import Decimal
        match = re.fullmatch(r'P([+-])(\d+(?:\.\d{1,2})?)(?:\s+(.*))?', text.strip(), re.I)
        if not match:
            return None
        op, amount, note = match.groups()
        value = Decimal(amount)
        if value <= 0 or value >= Decimal('1000000000000'):
            raise ValueError('寄存金额不正确。')
        return dict(operation=op, amount=value, note=note or '')

    @staticmethod
    def parse_correction(text):
        withdraw = text.strip().startswith('下发-')
        value = CommandParser._parse_entry(text, withdraw=withdraw, correction=True)
        if value:
            value['type'] = 'withdraw' if withdraw else 'deposit'
        return value

    @staticmethod
    def parse_rate_setting(text):
        from decimal import Decimal
        match = re.fullmatch(r'设置(.*?)(汇率|费率)(-?\d+(?:\.\d+)?)(%)?', text.strip())
        if not match:
            return None
        name, kind, value, percent = match.groups()
        value = Decimal(value)
        if kind == '汇率' and (percent or not Decimal('0') < value < Decimal('1000000')):
            raise ValueError('汇率必须大于 0，且小于 1000000。')
        if kind == '费率' and not Decimal('-100') <= value <= Decimal('100'):
            raise ValueError('费率须在 -100% 到 100% 之间。')
        return dict(type='exchange_rate' if kind == '汇率' else 'fee_rate',
                    username=name.removesuffix('的') or None, value=value)

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
        match = re.match(r'^设置日切(?:时间)?(\d{1,2})(?::(\d{2}))?$', text.strip())
        if match:
            hour, minute = match.groups()
            return f"{hour.zfill(2)}:{minute or '00'}"
        return None

    @staticmethod
    def is_trc20_address(text: str) -> bool:
        """
        判断是否为TRC20地址
        """
        return bool(re.match(r'^T[A-Za-z0-9]{33}$', text.strip()))
