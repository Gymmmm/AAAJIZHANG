"""
Telegram记账机器人主程序
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes
)

from config import config
from .models import init_db, close_db
from .services.schedule_service import ScheduleService
from .handlers import basic, operator, billing, settings, query, reports
from .services.identity import remember_update

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)


class AccountingBot:
    """记账机器人主类"""

    def __init__(self):
        """初始化机器人"""
        self.application = None
        self.schedule_service = None

    async def post_init(self, application: Application):
        """应用初始化后的操作"""
        operator.permission_bot = application.bot
        # 初始化数据库
        await init_db()
        logger.info("Database initialized")

        # 初始化定时任务服务
        self.schedule_service = ScheduleService(application.bot)
        application.bot_data["schedule_service"] = self.schedule_service
        await self.schedule_service.start()
        logger.info("Schedule service started")

    async def post_shutdown(self, application: Application):
        """应用关闭时的清理操作"""
        # 停止定时任务
        if self.schedule_service:
            await self.schedule_service.stop()
            logger.info("Schedule service stopped")

        # 关闭数据库连接
        await close_db()
        logger.info("Database closed")

    def setup_handlers(self, application: Application):
        """设置命令处理器"""

        application.add_handler(MessageHandler(filters.ALL, remember_update), group=-1)
        application.add_handler(MessageHandler(filters.Regex(r'^(撤销|撤销恢复|恢复)$'), billing.revoke_record))
        application.add_handler(MessageHandler(filters.Regex(r'^(-\\d|下发-\\d)'), billing.handle_correction))
        application.add_handler(MessageHandler(filters.Regex(r'^(导出账单|导出Excel)$'), reports.export_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^网页账单$'), reports.web_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^删除全局操作人'), operator.remove_global_operator))
        application.add_handler(MessageHandler(filters.Regex(r'^(查账单.+|账单)$'), billing.show_my_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^(删除全部账单|清除全部账单|清除今日账单)$'), billing.delete_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^关闭日切$'), settings.set_day_cut_time))
        # 基础命令
        application.add_handler(CommandHandler("start", basic.start_billing))
        application.add_handler(CommandHandler("help", basic.show_help))
        application.add_handler(MessageHandler(filters.Regex(r'^开始$'), basic.start_billing))
        application.add_handler(MessageHandler(filters.Regex(r'^停止$'), basic.stop_billing))
        application.add_handler(MessageHandler(filters.Regex(r'^上课$'), basic.unmute_group))
        application.add_handler(MessageHandler(filters.Regex(r'^下课$'), basic.mute_group))

        # 操作人管理
        application.add_handler(MessageHandler(filters.Regex(r'^添加操作[人员]'), operator.add_operator))
        application.add_handler(MessageHandler(filters.Regex(r'^删除操作[人员]'), operator.remove_operator))
        application.add_handler(MessageHandler(filters.Regex(r'^显示操作人$'), operator.show_operators))
        application.add_handler(MessageHandler(filters.Regex(r'^设置全员$'), operator.enable_all_members))
        application.add_handler(MessageHandler(filters.Regex(r'^取消全员$'), operator.disable_all_members))
        application.add_handler(MessageHandler(filters.Regex(r'^显示全局操作人$'), operator.show_global_operators))
        application.add_handler(MessageHandler(filters.Regex(r'^添加全局操作人'), operator.add_global_operator))

        application.add_handler(MessageHandler(filters.Regex(r"^\+0$"), billing.show_bills))
        application.add_handler(MessageHandler(filters.Regex(r"^/我(?:@\w+)?$"), billing.show_my_bills))

        # 账单操作
        application.add_handler(MessageHandler(filters.Regex(r'^\+\\d+'), billing.handle_deposit))
        application.add_handler(MessageHandler(filters.Regex(r'^.+?\+\\d+'), billing.handle_deposit))
        application.add_handler(MessageHandler(filters.Regex(r'^下发\\d+'), billing.handle_withdraw))
        application.add_handler(MessageHandler(filters.Regex(r'^.+?下发\\d+'), billing.handle_withdraw))
        application.add_handler(MessageHandler(filters.Regex(r'^P[+-]\\d+'), billing.handle_storage))
        application.add_handler(MessageHandler(filters.Regex(r'^余额[+-]\\d+'), billing.handle_balance))

        # 账单查询
        application.add_handler(MessageHandler(filters.Regex(r'^(显示账单|\+0)$'), billing.show_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^全部账单$'), billing.show_all_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^账单汇总$'), billing.show_summary))
        application.add_handler(CommandHandler("my", billing.show_my_bills))

        # 账单管理
        application.add_handler(MessageHandler(filters.Regex(r'^撤销入款$'), billing.revoke_deposit))
        application.add_handler(MessageHandler(filters.Regex(r'^撤销下发$'), billing.revoke_withdraw))
        application.add_handler(MessageHandler(filters.Regex(r'^删除账单$'), billing.delete_bills))
        application.add_handler(MessageHandler(filters.Regex(r'^保存账单$'), billing.save_bills))

        # 参数设置
        application.add_handler(MessageHandler(filters.Regex(r'^设置汇率'), settings.set_exchange_rate))
        application.add_handler(MessageHandler(filters.Regex(r'^设置.+?汇率\\d+'), settings.set_exchange_rate))
        application.add_handler(MessageHandler(filters.Regex(r'^设置费率'), settings.set_fee_rate))
        application.add_handler(MessageHandler(filters.Regex(r'^设置.+?费率\\d+'), settings.set_fee_rate))
        application.add_handler(MessageHandler(filters.Regex(r'^(查看费汇配置|费汇配置)$'), settings.show_user_configs))
        application.add_handler(MessageHandler(filters.Regex(r'^删除.*? 配置$'), settings.delete_user_config))

        # 显示设置
        application.add_handler(MessageHandler(filters.Regex(r'^设置(入款|下发)条数\\d+$'), settings.set_display_count))
        application.add_handler(MessageHandler(filters.Regex(r'^(显示模式1|显示模式2|显示模式3)$'), settings.set_classic_display_mode))
        application.add_handler(MessageHandler(filters.Regex(r'^设置币种[A-Z]+$'), settings.set_currency_display))
        application.add_handler(MessageHandler(filters.Regex(r'^(记账置顶|置顶关闭|开启置顶|关闭置顶)$'), settings.toggle_pin))
        application.add_handler(MessageHandler(filters.Regex(r'^(双币模式|单币模式)$'), settings.toggle_currency_mode))
        application.add_handler(MessageHandler(filters.Regex(r'^(纯净模式|显示回复人|显示入账人)$'), settings.toggle_display_mode))
        application.add_handler(MessageHandler(filters.Regex(r'^设置日切'), settings.set_day_cut_time))
        application.add_handler(MessageHandler(filters.Regex(r'^群组配置$'), settings.show_group_config))

        # 下发地址
        application.add_handler(MessageHandler(filters.Regex(r'^设置下发地址'), settings.set_withdraw_address))
        application.add_handler(MessageHandler(filters.Regex(r'^下发地址$'), settings.show_withdraw_address))

        # 查询功能
        application.add_handler(MessageHandler(filters.Regex(r'^h0$'), query.query_huobi_price))
        application.add_handler(MessageHandler(filters.Regex(r'^z0$'), query.query_okex_price))
        application.add_handler(MessageHandler(filters.Regex(r'^T[A-Za-z0-9]{33}$'), query.query_trc20_address))
        application.add_handler(MessageHandler(filters.Regex(r'^计算.+'), query.calculate_expression))

        # 辅助功能
        application.add_handler(MessageHandler(filters.Regex(r'^通知所有人$'), query.mention_all))
        application.add_handler(MessageHandler(filters.Regex(r'^设置分组'), query.set_group_tag))

        logger.info("All handlers registered")

    async def error_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """错误处理器"""
        logger.error("Yam handler failure: %s", type(context.error).__name__, exc_info=context.error)

        # 如果有消息，尝试回复错误信息
        if update and update.effective_message:
            try:
                await update.effective_message.reply_text(
                    "❌ 处理您的请求时出现错误，请稍后重试。"
                )
            except Exception:
                pass

    def run(self):
        """运行机器人"""
        # 验证配置
        config.validate()

        # 创建应用
        self.application = (
            Application.builder()
            .token(config.BOT_TOKEN)
            .post_init(self.post_init)
            .post_shutdown(self.post_shutdown)
            .build()
        )

        # 注册处理器
        self.setup_handlers(self.application)

        # 注册错误处理器
        self.application.add_error_handler(self.error_handler)

        # 运行机器人
        logger.info("Starting bot...")
        self.application.run_polling(allowed_updates=Update.ALL_TYPES)


def main():
    """主函数"""
    bot = AccountingBot()
    bot.run()


if __name__ == "__main__":
    main()
