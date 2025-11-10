#!/usr/bin/env python3
"""
Web服务器启动脚本
"""
import uvicorn
import os
from src.web.app import app

if __name__ == "__main__":
    # 从环境变量获取配置
    host = os.getenv("WEB_HOST", "0.0.0.0")
    port = int(os.getenv("WEB_PORT", "8000"))

    # 启动服务器
    uvicorn.run(
        "src.web.app:app",
        host=host,
        port=port,
        reload=True,  # 开发模式，生产环境设为False
        log_level="info"
    )
