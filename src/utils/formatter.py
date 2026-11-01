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
        """
        格式化单条交易记录

        Args:
            trans: 交易记录对象
            display_mode: 显示模式 (pure/reply/operator)
            currency_mode: 币种模式 (single/dual)
        """
        lines = []

        # 交易类型标记
        if trans.transaction_type == 'deposit':
            type_mark = "💰 入款"
        elif trans.transaction_type == 'withdraw':
            type_mark = "💸 下发"
        else:
            type_mark = "📦 寄存"

        # 用户信息
        user_display = trans.first_name or trans.username or f"用户{trans.user_id}"

        def original_amount(value):
            return format(value, '.6f').rstrip('0').rstrip('.') if trans.currency == 'USDT' else format(value, '.2f')
        # 金额信息
        if currency_mode == "dual":
            if trans.currency == "USDT":
                amount_display = f"{original_amount(trans.amount)} USDT ≈ ¥{trans.cny_amount:.2f}"
            else:
                amount_display = f"¥{trans.amount:.2f}"
        else:
            amount_display = f"{original_amount(trans.amount)} {trans.currency}"

        # 基本信息行
        name = f" {user_display}:" if display_mode in ('reply', 'operator') else ''
        line = f"{type_mark}{name} {amount_display}"
        if getattr(trans, 'id', None):
            line += f" · #{trans.id}"

        # 添加汇率和费率信息
        if trans.exchange_rate is not None:
            line += f" (汇率:{trans.exchange_rate})"
        if trans.fee_rate is not None:
            line += f" (费率:{trans.fee_rate}%)"

        lines.append(line)

        # 最终金额（如果有手续费）
        if trans.fee_amount:
            lines.append(f"   手续费: ¥{trans.fee_amount:.2f}")
            lines.append(f"   实际到账: ¥{trans.final_amount:.2f}")

        # 备注
        if trans.note:
            lines.append(f"   备注: {trans.note}")

        # 显示操作人或回复人
        if display_mode == "operator":
            operator_display = trans.operator_first_name or trans.operator_username or f"操作人{trans.operator_id}"
            lines.append(f"   操作人: {operator_display}")
        elif display_mode == "reply" and trans.reply_to_message_id:
            lines.append(f"   回复消息ID: {trans.reply_to_message_id}")

        # 时间
        stamp = trans.transaction_date
        if stamp.tzinfo is None:
            stamp = pytz.utc.localize(stamp)
        time_display = stamp.astimezone(pytz.timezone(config.TIMEZONE)).strftime("%Y-%m-%d %H:%M:%S")
        lines.append(f"   时间: {time_display}")

        return "\n".join(lines)

    @staticmethod
    def format_transaction_list(
        transactions: List,
        title: str = "账单列表",
        display_mode: str = "pure",
        currency_mode: str = "single",
        limit: Optional[int] = None
    ) -> str:
        """
        格式化交易列表
        """
        if not transactions:
            return f"📋 {title}\n\n暂无记录"

        lines = [f"📋 {title}", "=" * 30]

        display_transactions = transactions[:limit] if limit else transactions

        for i, trans in enumerate(display_transactions, 1):
            lines.append(f"\n[{i}]")
            lines.append(Formatter.format_transaction(trans, display_mode, currency_mode))

        if limit and len(transactions) > limit:
            lines.append(f"\n... 还有 {len(transactions) - limit} 条记录")

        return "\n".join(lines)

    @staticmethod
    def format_summary(summary: dict, title: str = "账单汇总") -> str:
        """
        格式化账单汇总
        """
        lines = [
            f"📊 {title}",
            "=" * 30,
            "",
            f"💰 入款: {summary['deposit_count']}笔",
            f"   折合: {summary['deposit_amount']:.6f} USDT",
            f"   人民币: ¥{summary['deposit_cny']:.2f}",
            "",
            f"💸 下发: {summary['withdraw_count']}笔",
            f"   折合: {summary['withdraw_amount']:.6f} USDT",
            f"   人民币: ¥{summary['withdraw_cny']:.2f}",
            "",
            f"📦 寄存: ¥{summary['storage_amount']:.2f}",
            "",
            f"💵 手续费: ¥{summary['total_fee']:.2f}",
            "",
            f"📈 净额: ¥{summary['net_amount']:.2f}",
        ]
        return "\n".join(lines)

    @staticmethod
    def format_group_config(group) -> str:
        """
        格式化群组配置信息
        """
        status = "✅ 开启" if group.is_active else "❌ 停止"
        mute = "🔇 禁言中" if group.is_muted else "🔊 可发言"

        display_modes = {
            "pure": "纯净模式",
            "reply": "显示回复人",
            "operator": "显示操作人"
        }

        currency_modes = {
            "single": "单币模式",
            "dual": "双币模式"
        }

        lines = [
            f"⚙️ 群组配置 - {group.group_name}",
            "=" * 30,
            "",
            f"📌 状态: {status}",
            f"🔊 发言: {mute}",
            "",
            f"💱 汇率: {group.exchange_rate}",
            f"💰 费率: {group.fee_rate}%",
            "",
            f"📺 显示模式: {display_modes.get(group.display_mode, group.display_mode)}",
            f"💵 币种模式: {currency_modes.get(group.currency_mode, group.currency_mode)}",
            f"🏷️ 显示币种: {group.currency_display}",
            f"📍 置顶: {'开启' if group.pin_enabled else '关闭'}",
            "",
            f"📊 入款显示: {group.deposit_display_count}条",
            f"📊 下发显示: {group.withdraw_display_count}条",
            "",
            f"🔖 分类: {'开启' if group.category_enabled else '关闭'}",
        ]

        if group.day_cut_time:
            lines.append(f"⏰ 日切时间: {group.day_cut_time.strftime('%H:%M')}")

        if group.group_tag:
            lines.append(f"🏷️ 分组: {group.group_tag}")

        if group.withdraw_address:
            lines.append(f"📫 下发地址: {group.withdraw_address}")

        return "\n".join(lines)

    @staticmethod
    def format_operators(operators: List, global_operators: List = None) -> str:
        """
        格式化操作人列表
        """
        lines = ["👥 操作人列表", "=" * 30]

        if global_operators:
            lines.append("\n🌐 全局操作人:")
            for op in global_operators:
                user_display = op.first_name or op.username or f"用户{op.user_id}"
                lines.append(f"  • {user_display}")

        if operators:
            lines.append("\n👤 群组操作人:")
            for op in operators:
                user_display = op.first_name or op.username or f"用户{op.user_id}"
                lines.append(f"  • {user_display}")

        if not operators and not global_operators:
            lines.append("\n暂无操作人")

        return "\n".join(lines)

    @staticmethod
    def format_user_configs(configs: List) -> str:
        """
        格式化用户配置列表（费汇配置）
        """
        if not configs:
            return "📋 费汇配置\n\n暂无个人配置"

        lines = ["📋 费汇配置", "=" * 30]

        for config in configs:
            user_display = config.first_name or config.username or f"用户{config.user_id}"
            lines.append(f"\n👤 {user_display}:")
            if config.exchange_rate:
                lines.append(f"   汇率: {config.exchange_rate}")
            if config.fee_rate is not None:
                lines.append(f"   费率: {config.fee_rate}%")

        return "\n".join(lines)

    @staticmethod
    def escape_markdown(text: str) -> str:
        """
        转义Markdown特殊字符
        """
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text
