#!/usr/bin/env python3
"""
父Bot（主Bot）启动脚本
"""
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ConversationHandler
)

from config import config
from src.models import init_db, close_db
from src.handlers import master_bot

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def post_init(application: Application):
    """应用初始化后的操作"""
    await init_db()
    logger.info("Database initialized")


async def post_shutdown(application: Application):
    """应用关闭时的清理操作"""
    await close_db()
    logger.info("Database closed")


def main():
    """主函数"""
    # 验证配置
    config.validate()

    # 创建应用
    application = (
        Application.builder()
        .token(config.BOT_TOKEN)
        .post_init(post_init)
        .post_shutdown(post_shutdown)
        .build()
    )

    # 注册处理器
    # 开始命令
    application.add_handler(CommandHandler("start", master_bot.start_master))

    # 创建机器人对话
    conv_handler = ConversationHandler(
        entry_points=[],
        states={
            master_bot.WAITING_BOT_TOKEN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, master_bot.receive_bot_token)
            ],
        },
        fallbacks=[],
    )
    application.add_handler(conv_handler)

    # 按钮回调
    application.add_handler(CallbackQueryHandler(master_bot.button_callback))

    # 运行机器人
    logger.info("Starting Master Bot...")
    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
