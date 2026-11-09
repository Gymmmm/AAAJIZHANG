"""Safe, presentation-only deposit templates."""
from decimal import Decimal, ROUND_HALF_UP
from string import Formatter
import pytz
from config import config

STYLES = {
    'simple': ('📝 简洁版', '{time} {money}'),
    'usdt': ('💎 简洁版(U金额)', '{time} {usum}U'),
    'dual': ('🔄 简洁版(双金额)', '{time} {money} | {usum}U'),
    'standard': ('📋 标准版', '{time} {money}{rate_calc} ={usum}u'),
    'detail': ('📄 详细版', '💰  {time} {money}{rate_calc} ={usum}u  {username}'),
}
VARIABLES = {'time', 'money', 'username', 'signname', 'rate_calc', 'usum'}

def validate_template(template):
    if not template.strip() or len(template) > 300:
        raise ValueError('模板须为 1～300 个字符。')
    try:
        fields = list(Formatter().parse(template))
    except ValueError:
        raise ValueError('模板花括号不完整。')
    for _, name, spec, conversion in fields:
        if name is not None and (name not in VARIABLES or spec or conversion):
            raise ValueError('仅支持 {time} {money} {username} {signname} {rate_calc} {usum}，不支持格式表达式。')
    return template

def deposit_usdt(trans):
    """Use the persisted net CNY amount, including its original fee rounding."""
    D = lambda x: Decimal(str(x))
    rate = D(trans.exchange_rate) if trans.exchange_rate is not None else None
    if rate and rate > 0:
        return D(trans.final_amount) / rate
    if trans.currency == 'USDT':
        return D(trans.amount) * (1 - D(trans.fee_rate or 0) / 100)
    return Decimal(0)

def render_deposit(trans, style):
    stamp = trans.transaction_date
    if stamp.tzinfo is None:
        stamp = pytz.utc.localize(stamp)
    D = lambda x: Decimal(str(x))
    number = lambda x: format(D(x), 'f').rstrip('0').rstrip('.') if '.' in format(D(x), 'f') else format(D(x), 'f')
    amount = D(trans.amount)
    rate = D(trans.exchange_rate) if trans.exchange_rate is not None else None
    fee = D(trans.fee_rate or 0)
    multiplier = 1 - fee / 100
    if trans.currency == 'USDT':
        # Stored final_amount is CNY; without a conversion rate use the U basis.
        u = deposit_usdt(trans)
        rate_calc = '*' + number(multiplier)
    else:
        if not rate or rate <= 0:
            return stamp.astimezone(pytz.timezone(config.TIMEZONE)).strftime('%m-%d %H:%M') + ' ' + number(amount) + '（缺少有效汇率）'
        u = deposit_usdt(trans)
        rate_calc = '/' + number(rate) + '*' + number(multiplier)
    values = {
        'time': stamp.astimezone(pytz.timezone(config.TIMEZONE)).strftime('%m-%d %H:%M'),
        'money': number(amount) + ('U' if trans.currency == 'USDT' else ''),
        'username': (trans.first_name or trans.username or str(trans.user_id))[:64],
        'signname': (trans.operator_first_name or trans.operator_username or str(trans.operator_id))[:64],
        'rate_calc': rate_calc,
        'usum': format(u.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP), '.2f'),
    }
    template = style.get('template', '') if style.get('name') == 'custom' else STYLES.get(style.get('name'), STYLES['usdt'])[1]
    try:
        validate_template(template)
    except ValueError:
        template = STYLES['usdt'][1]
    return template.format_map(values)
