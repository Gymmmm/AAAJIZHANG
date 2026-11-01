"""
格式化工具
"""
from datetime import datetime
from typing import List, Optional
import pytz
from config import config


class Formatter:
    """消息格式化器"""

    @staticmethod
    def format_transaction(trans, display_mode: str = "pure", currency_mode: str = "single") -> str:
        """格式化单条交易记录（优化版）"""
        # 类型标记
        type_map = {
            'deposit': '💰入款',
            'withdraw': '💸下发',
            'storage': '📦寄存'
        }
        type_mark = type_map.get(trans.transaction_type, '📋记录')

        # 用户名
        user_display = (trans.first_name or trans.username or f"用户{trans.user_id}")[:12]

        def fmt_amount(value, currency):
            if currency == 'USDT':
                return format(float(value), '.6f').rstrip('0').rstrip('.')
            return f"{float(value):.2f}"

        # 金额显示
        if currency_mode == "dual" and trans.currency == "USDT":
            amount_display = f"{fmt_amount(trans.amount, 'USDT')}U ≈ ¥{trans.cny_amount:.2f}"
        elif trans.currency == "USDT":
            amount_display = f"{fmt_amount(trans.amount, 'USDT')}U"
        else:
            amount_display = f"¥{fmt_amount(trans.amount, 'CNY')}"

        # 主行
        name_part = f" {user_display}" if display_mode in ('reply', 'operator') else ""
        main = f"{type_mark}{name_part} {amount_display}"
        if getattr(trans, 'id', None):
            main += f" #{trans.id}"

        extras = []
        if trans.exchange_rate is not None:
            extras.append(f"汇率{trans.exchange_rate}")
        if trans.fee_rate is not None and float(trans.fee_rate) != 0:
            extras.append(f"费率{trans.fee_rate}%")
        if extras:
            main += f" ({' '.join(extras)})"

        lines = [main]

        # 手续费 / 实际到账
        if trans.fee_amount and float(trans.fee_amount) != 0:
            lines.append(f"  手续费 ¥{trans.fee_amount:.2f} → 实际 ¥{trans.final_amount:.2f}")

        # 备注（截断过长）
        if trans.note:
            note = trans.note[:30] + ("…" if len(trans.note) > 30 else "")
            lines.append(f"  备注: {note}")

        # 操作人 / 回复
        if display_mode == "operator":
            op = (trans.operator_first_name or trans.operator_username or f"ID{trans.operator_id}")[:10]
            lines.append(f"  操作: {op}")
        elif display_mode == "reply" and trans.reply_to_message_id:
            lines.append(f"  回复ID: {trans.reply_to_message_id}")

        # 时间（简短）
        stamp = trans.transaction_date
        if stamp.tzinfo is None:
            stamp = pytz.utc.localize(stamp)
        time_display = stamp.astimezone(pytz.timezone(config.TIMEZONE)).strftime("%m-%d %H:%M")
        lines.append(f"  {time_display}")

        return "\n".join(lines)

    @staticmethod
    def format_transaction_list(
        transactions: List,
        title: str = "明细",
        display_mode: str = "pure",
        currency_mode: str = "single",
        limit: Optional[int] = None
    ) -> str:
        """格式化交易列表（更紧凑）"""
        if not transactions:
            return f"📋 {title}\n暂无记录"

        lines = [f"📋 {title}", "—" * 24]

        display_transactions = transactions[:limit] if limit else transactions

        for i, trans in enumerate(display_transactions, 1):
            lines.append(f"{i}. {Formatter.format_transaction(trans, display_mode, currency_mode)}")

        if limit and len(transactions) > limit:
            lines.append(f"\n… 还有 {len(transactions) - limit} 条")

        return "\n".join(lines)

    @staticmethod
    def format_summary(summary: dict, title: str = "账单汇总") -> str:
        """格式化账单汇总（更清晰）"""
        lines = [
            f"📊 {title}",
            "—" * 24,
            f"💰 入款 {summary['deposit_count']}笔  {summary['deposit_amount']:.4f}U  ¥{summary['deposit_cny']:.2f}",
            f"💸 下发 {summary['withdraw_count']}笔  {summary['withdraw_amount']:.4f}U  ¥{summary['withdraw_cny']:.2f}",
            f"📦 寄存 ¥{summary['storage_amount']:.2f}",
            f"💵 手续费 ¥{summary['total_fee']:.2f}",
            "—" * 24,
            f"📈 净额 ¥{summary['net_amount']:.2f}",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_group_config(group) -> str:
        """格式化群组配置信息"""
        status = "✅开启" if group.is_active else "❌停止"
        mute = "🔇禁言" if group.is_muted else "🔊可发言"

        display_modes = {"pure": "纯净", "reply": "显示回复人", "operator": "显示操作人"}
        currency_modes = {"single": "单币", "dual": "双币"}

        lines = [
            f"⚙️ 群组配置 · {group.group_name}",
            "—" * 24,
            f"状态: {status}  |  {mute}",
            f"汇率: {group.exchange_rate}  费率: {group.fee_rate}%",
            f"显示: {display_modes.get(group.display_mode, group.display_mode)}  |  {currency_modes.get(group.currency_mode, group.currency_mode)}",
            f"币种: {group.currency_display}  置顶: {'开' if group.pin_enabled else '关'}",
            f"入款显示{group.deposit_display_count}条  下发显示{group.withdraw_display_count}条",
        ]

        if group.day_cut_time:
            lines.append(f"日切: {group.day_cut_time.strftime('%H:%M')}")
        if group.group_tag:
            lines.append(f"分组: {group.group_tag}")
        if group.withdraw_address:
            lines.append(f"下发地址: {group.withdraw_address[:20]}...")

        return "\n".join(lines)

    @staticmethod
    def format_operators(operators: List, global_operators: List = None) -> str:
        """格式化操作人列表"""
        lines = ["👥 操作人", "—" * 24]

        if global_operators:
            lines.append("🌐 全局:")
            for op in global_operators:
                user_display = (op.first_name or op.username or f"ID{op.user_id}")[:12]
                lines.append(f"  • {user_display}")

        if operators:
            lines.append("👤 本群:")
            for op in operators:
                user_display = (op.first_name or op.username or f"ID{op.user_id}")[:12]
                lines.append(f"  • {user_display}")

        if not operators and not global_operators:
            lines.append("暂无")

        return "\n".join(lines)

    @staticmethod
    def format_user_configs(configs: List) -> str:
        """格式化用户配置列表（费汇配置）"""
        if not configs:
            return "📋 费汇配置\n暂无个人配置"

        lines = ["📋 费汇配置", "—" * 24]

        for cfg in configs:
            user_display = (cfg.first_name or cfg.username or f"ID{cfg.user_id}")[:12]
            parts = []
            if cfg.exchange_rate:
                parts.append(f"汇率{cfg.exchange_rate}")
            if cfg.fee_rate is not None:
                parts.append(f"费率{cfg.fee_rate}%")
            lines.append(f"{user_display}: {' '.join(parts)}")

        return "\n".join(lines)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """转义Markdown特殊字符"""
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
