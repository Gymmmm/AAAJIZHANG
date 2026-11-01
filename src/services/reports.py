"""Read-only exports. All text cells remain text, including formula-like notes."""
import base64
import hashlib
import hmac
import io
import json
import os
import time
import zipfile
from html import escape
from xml.sax.saxutils import escape as xml_escape
from config import config
from .billing_service import BillingService

HEADERS = ['编号','时间（本地）','类型','入账人','操作人','原币金额','原币','汇率','费率%','折合CNY','手续费CNY','净额CNY','备注','状态','操作审计（UTC）']

def values(rows):
    import pytz
    tz = pytz.timezone(config.TIMEZONE)
    for r in rows:
        stamp = pytz.utc.localize(r.transaction_date).astimezone(tz)
        yield [r.id, stamp.strftime('%Y-%m-%d %H:%M:%S'), {'deposit':'入款','withdraw':'下发','storage':'寄存'}[r.transaction_type],
               r.first_name or r.username or r.user_id, r.operator_first_name or r.operator_id, r.amount, r.currency,
               r.exchange_rate, r.fee_rate, r.cny_amount, r.fee_amount, r.final_amount, r.note or '', '已撤销' if r.is_deleted else '有效',getattr(r,'audit_history','')]

def xlsx_bytes(rows):
    def col(n):
        result = ''
        while n:
            n, m = divmod(n-1, 26); result = chr(65+m) + result
        return result
    cells = []
    for i, row in enumerate([HEADERS] + list(values(rows)), 1):
        parts = []
        for j, value in enumerate(row, 1):
            # Inline strings prevent Excel formula execution and precision loss on long identifiers.
            text = xml_escape(str(value if value is not None else ''))
            text = ''.join(c for c in text if ord(c) >= 32 or c in '\n\t\r')
            parts.append(f'<c r="{col(j)}{i}" t="inlineStr"><is><t xml:space="preserve">{text}</t></is></c>')
        cells.append(f'<row r="{i}">' + ''.join(parts) + '</row>')
    buf = io.BytesIO()
    with zipfile.ZipFile(buf,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr('[Content_Types].xml','<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/></Types>')
        z.writestr('_rels/.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>')
        z.writestr('xl/workbook.xml','<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="账单" sheetId="1" r:id="rId1"/></sheets></workbook>')
        z.writestr('xl/_rels/workbook.xml.rels','<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/></Relationships>')
        z.writestr('xl/worksheets/sheet1.xml','<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><sheetData>'+''.join(cells)+'</sheetData></worksheet>')
    return buf.getvalue()

def html_text(rows, title='账单明细'):
    from ..utils.calculator import Calculator
    from ..utils.formatter import Formatter
    summary = escape(Formatter.format_summary(Calculator.calculate_summary(rows)))
    table = '<tr>' + ''.join(f'<th>{escape(x)}</th>' for x in HEADERS) + '</tr>'
    for row in values(rows):
        table += '<tr>' + ''.join(f'<td>{escape(str(x if x is not None else ""))}</td>' for x in row) + '</tr>'
    return '<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>'+escape(title)+'</title><style>body{font:16px system-ui;margin:20px;color:#17212b;background:#f5f7fa}pre{white-space:pre-wrap;background:white;padding:16px;border-radius:12px}table{border-collapse:collapse;background:white;font-size:14px}td,th{padding:10px;border:1px solid #ddd;white-space:nowrap}th{background:#eaf0f7;position:sticky;top:0}.table{overflow:auto}h1{font-size:24px}</style><h1>'+escape(title)+'</h1><p>以原币和单笔实际费汇为准；撤销记录保留，汇总不计入。</p><pre>'+summary+'</pre><div class="table"><table>'+table+'</table></div></html>'

def report_token(gid, now=None):
    payload = base64.urlsafe_b64encode(json.dumps({'g':gid, 'e':int(now or time.time())+3600}, separators=(',',':')).encode()).decode().rstrip('=')
    signature = hmac.new(config.BOT_TOKEN.encode(), ('yam-report:'+payload).encode(),hashlib.sha256).hexdigest()
    return payload + '.' + signature

def read_report_token(token, now=None):
    try:
        payload, signature = token.split('.')
        expected = hmac.new(config.BOT_TOKEN.encode(), ('yam-report:'+payload).encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise ValueError()
        value=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
        if value['e'] < int(now or time.time()):
            raise ValueError()
        return int(value['g'])
    except Exception:
        raise ValueError('链接无效或已过期，请在机器人中重新打开网页账单。')
