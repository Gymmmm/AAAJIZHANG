"""Display regression tests, isolated from production credentials and ledger data."""
import importlib.util
import sys
import types
import unittest
from pathlib import Path
from datetime import datetime
from unittest.mock import AsyncMock, patch
from decimal import Decimal

ROOT = Path(__file__).resolve().parents[1]

def load_modules():
    config_module = types.ModuleType('config')
    config_module.config = types.SimpleNamespace(TIMEZONE='Asia/Shanghai')
    package = types.ModuleType('_style_test')
    package.__path__ = [str(ROOT / 'src/utils')]
    with patch.dict(sys.modules, {'config': config_module, '_style_test': package}):
        modules = []
        for name in ['deposit_style', 'formatter']:
            spec = importlib.util.spec_from_file_location('_style_test.' + name, ROOT / ('src/utils/' + name + '.py'))
            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)
            modules.append(module)
    return modules

style, formatter = load_modules()

def transaction(**overrides):
    data = dict(transaction_date=datetime(2026, 10, 31, 3, 45), amount=11000,
        exchange_rate=9.7, fee_rate=0, final_amount=11000, cny_amount=11000,
        fee_amount=0, currency='CNY', transaction_type='deposit', is_deleted=False,
        first_name='张三', username=None, user_id=1, operator_first_name='李四',
        operator_username=None, operator_id=2, note='', reply_to_message_id=None)
    data.update(overrides)
    return types.SimpleNamespace(**data)

def group(**overrides):
    data = dict(exchange_rate=9.7, fee_rate=0, deposit_style=None)
    data.update(overrides)
    return types.SimpleNamespace(**data)

def summary():
    return dict(deposit_cny=11000, deposit_amount=11000/9.7,
                withdraw_cny=0, withdraw_amount=0)

class DisplayTests(unittest.TestCase):
    def test_exact_requested_bill(self):
        actual = formatter.Formatter.format_classic_bill([transaction()], summary(), group())
        self.assertEqual(actual, '入款：（1笔）\n11:45  11000 / 9.7 = 1134.02\n\n下发：（0笔）\n 暂无下发\n\n总入款：11000\n当前费率：0%\n固定汇率：9.7\n\n应下发：1134.02 USDT\n已下发：0 USDT\n未下发：1134.02 USDT')

    def test_presets(self):
        t = transaction(amount=1000, exchange_rate=7.2, fee_rate=2, final_amount=980)
        expected = {
            'simple':'10-31 11:45 1000',
            'usdt':'10-31 11:45 136.11U',
            'dual':'10-31 11:45 1000 | 136.11U',
            'standard':'10-31 11:45 1000/7.2*0.98 =136.11u',
            'detail':'💰  10-31 11:45 1000/7.2*0.98 =136.11u  张三',
        }
        for name, result in expected.items():
            with self.subTest(name=name):
                self.assertEqual(style.render_deposit(t, {'name': name}), result)

    def test_custom_variables(self):
        result = style.render_deposit(transaction(), {'name':'custom', 'template':'{username}|{signname}|{money}|{rate_calc}|{usum}|{time}'})
        self.assertEqual(result, '张三|李四|11000|/9.7*1|1134.02|10-31 11:45')

    def test_invalid_templates(self):
        for template in ['', 'x'*301, '{unknown}', '{username.__class__}', '{money[0]}', '{money!r}', '{money:1000000}', '{']:
            with self.subTest(template=template), self.assertRaises(ValueError):
                style.validate_template(template)

    def test_u_deposit_and_negative_fee(self):
        self.assertEqual(style.render_deposit(transaction(amount=100, currency='USDT', exchange_rate=7, final_amount=686, fee_rate=2), {'name':'usdt'}), '10-31 11:45 98.00U')
        self.assertEqual(style.deposit_usdt(transaction(amount=100, currency='USDT', exchange_rate=None, final_amount=101, fee_rate=-1)), Decimal(101))

    def test_bill_uses_saved_net_and_counts_all_rows(self):
        rows = [transaction(amount=1000, exchange_rate=7.2, fee_rate=2, final_amount=980), transaction(is_deleted=True)]
        body = formatter.Formatter.format_classic_bill(rows, dict(deposit_cny=1000,deposit_amount=1000/7.2,withdraw_cny=0,withdraw_amount=0), group(deposit_style={'name':'dual'}), display_limit=1)
        self.assertIn('入款：（1笔）', body)
        self.assertIn('1000 | 136.11U', body)
        self.assertIn('应下发：136.11 USDT', body)

    def test_empty_bill(self):
        body = formatter.Formatter.format_classic_bill([], dict(deposit_cny=0, deposit_amount=0,withdraw_cny=0,withdraw_amount=0), group())
        self.assertIn('入款：（0笔）\n 暂无入款',body)
        self.assertIn('未下发：0 USDT', body)

    def test_history_and_receipt_use_selected_style(self):
        t = transaction()
        selected = {'name':'usdt'}
        self.assertEqual(formatter.Formatter.format_transaction(t, deposit_style=selected), '10-31 11:45 1134.02U')
        self.assertIn('10-31 11:45 1134.02U', formatter.Formatter.format_transaction_list([t], deposit_style=selected))

    def test_missing_rate_does_not_invent_conversion(self):
        self.assertIn('缺少有效汇率',style.render_deposit(transaction(exchange_rate=None),{'name':'usdt'}))

if __name__ == '__main__':
    unittest.main()
