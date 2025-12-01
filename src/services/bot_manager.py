"""
机器人实例管理器
"""
import asyncio
import subprocess
import os
import signal
import json
from typing import Optional, Dict, List
from pathlib import Path
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..models import BotInstance, BotStatus, User
import logging

logger = logging.getLogger(__name__)


class BotInstanceManager:
    """机器人实例管理器"""

    def __init__(self, instances_dir: str = "./bot_instances"):
        """
        初始化管理器

        Args:
            instances_dir: 机器人实例目录
        """
        self.instances_dir = Path(instances_dir)
        self.instances_dir.mkdir(exist_ok=True, parents=True)
        self.running_processes: Dict[int, subprocess.Popen] = {}

    def _get_instance_dir(self, bot_id: int) -> Path:
        """
        获取机器人实例目录

        Args:
            bot_id: 机器人ID

        Returns:
            实例目录路径
        """
        return self.instances_dir / f"bot_{bot_id}"

    def _create_instance_files(self, bot_id: int, bot_token: str, user_id: int):
        """
        创建机器人实例文件

        Args:
            bot_id: 机器人ID
            bot_token: Bot Token
            user_id: 用户ID
        """
        instance_dir = self._get_instance_dir(bot_id)
        instance_dir.mkdir(exist_ok=True, parents=True)

        # 创建.env文件
        env_content = f"""# Bot Configuration
BOT_TOKEN={bot_token}
BOT_USERNAME=

# Database Configuration
DATABASE_URL=sqlite+aiosqlite:///{instance_dir}/bot.db

# Admin Configuration
SUPER_ADMIN_ID={user_id}

# Default Settings
DEFAULT_CURRENCY=USDT
DEFAULT_EXCHANGE_RATE=7.3
DEFAULT_FEE_RATE=3

# Timezone
TIMEZONE=Asia/Shanghai
"""
        env_file = instance_dir / ".env"
        env_file.write_text(env_content)

        # 创建启动脚本
        start_script = f"""#!/usr/bin/env python3
import sys
import os

# 添加父目录到路径
parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, parent_dir)

# 切换工作目录
os.chdir("{instance_dir}")

# 导入并运行机器人
from src.bot import main

if __name__ == "__main__":
    main()
"""
        start_file = instance_dir / "start.py"
        start_file.write_text(start_script)
        start_file.chmod(0o755)

    async def create_instance(
        self,
        db: AsyncSession,
        user_id: int,
        bot_token: str
    ) -> BotInstance:
        """
        创建机器人实例

        Args:
            db: 数据库会话
            user_id: 用户ID
            bot_token: Bot Token

        Returns:
            机器人实例对象
        """
        # 创建数据库记录
        bot_instance = BotInstance(
            user_id=user_id,
            bot_token=bot_token,
            status=BotStatus.CREATING
        )
        db.add(bot_instance)
        await db.commit()
        await db.refresh(bot_instance)

        try:
            # 创建实例文件
            self._create_instance_files(bot_instance.id, bot_token, user_id)

            # 获取Bot信息
            from telegram import Bot
            bot = Bot(token=bot_token)
            bot_info = await bot.get_me()

            # 更新Bot信息
            bot_instance.bot_username = bot_info.username
            bot_instance.bot_name = bot_info.first_name
            bot_instance.status = BotStatus.STOPPED

            await db.commit()
            await db.refresh(bot_instance)

        except Exception as e:
            logger.error(f"Failed to create bot instance: {e}")
            bot_instance.status = BotStatus.ERROR
            await db.commit()
            raise

        return bot_instance

    async def start_instance(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> bool:
        """
        启动机器人实例

        Args:
            db: 数据库会话
            bot_id: 机器人ID

        Returns:
            是否启动成功
        """
        # 查询实例
        query = select(BotInstance).where(BotInstance.id == bot_id)
        result = await db.execute(query)
        bot_instance = result.scalar_one_or_none()

        if not bot_instance:
            return False

        if bot_instance.status == BotStatus.RUNNING:
            return True

        try:
            # 启动进程
            instance_dir = self._get_instance_dir(bot_id)
            start_file = instance_dir / "start.py"

            process = subprocess.Popen(
                ["python3", str(start_file)],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                cwd=str(instance_dir)
            )

            # 保存进程信息
            self.running_processes[bot_id] = process
            bot_instance.process_id = process.pid
            bot_instance.status = BotStatus.RUNNING
            bot_instance.started_at = asyncio.get_event_loop().time()

            await db.commit()
            logger.info(f"Bot instance {bot_id} started with PID {process.pid}")
            return True

        except Exception as e:
            logger.error(f"Failed to start bot instance {bot_id}: {e}")
            bot_instance.status = BotStatus.ERROR
            await db.commit()
            return False

    async def stop_instance(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> bool:
        """
        停止机器人实例

        Args:
            db: 数据库会话
            bot_id: 机器人ID

        Returns:
            是否停止成功
        """
        # 查询实例
        query = select(BotInstance).where(BotInstance.id == bot_id)
        result = await db.execute(query)
        bot_instance = result.scalar_one_or_none()

        if not bot_instance:
            return False

        if bot_instance.status != BotStatus.RUNNING:
            return True

        try:
            # 停止进程
            if bot_id in self.running_processes:
                process = self.running_processes[bot_id]
                process.terminate()
                process.wait(timeout=10)
                del self.running_processes[bot_id]
            elif bot_instance.process_id:
                # 尝试通过PID停止
                os.kill(bot_instance.process_id, signal.SIGTERM)

            # 更新状态
            bot_instance.status = BotStatus.STOPPED
            bot_instance.stopped_at = asyncio.get_event_loop().time()
            bot_instance.process_id = None

            await db.commit()
            logger.info(f"Bot instance {bot_id} stopped")
            return True

        except Exception as e:
            logger.error(f"Failed to stop bot instance {bot_id}: {e}")
            return False

    async def restart_instance(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> bool:
        """
        重启机器人实例

        Args:
            db: 数据库会话
            bot_id: 机器人ID

        Returns:
            是否重启成功
        """
        await self.stop_instance(db, bot_id)
        await asyncio.sleep(2)  # 等待2秒
        return await self.start_instance(db, bot_id)

    async def delete_instance(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> bool:
        """
        删除机器人实例

        Args:
            db: 数据库会话
            bot_id: 机器人ID

        Returns:
            是否删除成功
        """
        # 先停止实例
        await self.stop_instance(db, bot_id)

        # 删除实例文件
        instance_dir = self._get_instance_dir(bot_id)
        if instance_dir.exists():
            import shutil
            shutil.rmtree(instance_dir)

        # 删除数据库记录
        query = select(BotInstance).where(BotInstance.id == bot_id)
        result = await db.execute(query)
        bot_instance = result.scalar_one_or_none()

        if bot_instance:
            await db.delete(bot_instance)
            await db.commit()

        logger.info(f"Bot instance {bot_id} deleted")
        return True

    async def get_user_instances(
        self,
        db: AsyncSession,
        user_id: int
    ) -> List[BotInstance]:
        """
        获取用户的所有机器人实例

        Args:
            db: 数据库会话
            user_id: 用户ID

        Returns:
            机器人实例列表
        """
        query = select(BotInstance).where(BotInstance.user_id == user_id)
        result = await db.execute(query)
        return result.scalars().all()

    async def check_instance_status(
        self,
        db: AsyncSession,
        bot_id: int
    ) -> str:
        """
        检查实例运行状态

        Args:
            db: 数据库会话
            bot_id: 机器人ID

        Returns:
            运行状态
        """
        if bot_id in self.running_processes:
            process = self.running_processes[bot_id]
            if process.poll() is None:
                return BotStatus.RUNNING
            else:
                # 进程已退出
                del self.running_processes[bot_id]
                # 更新数据库状态
                query = select(BotInstance).where(BotInstance.id == bot_id)
                result = await db.execute(query)
                bot_instance = result.scalar_one_or_none()
                if bot_instance:
                    bot_instance.status = BotStatus.STOPPED
                    bot_instance.process_id = None
                    await db.commit()
                return BotStatus.STOPPED

        # 检查数据库记录
        query = select(BotInstance).where(BotInstance.id == bot_id)
        result = await db.execute(query)
        bot_instance = result.scalar_one_or_none()

        if bot_instance:
            return bot_instance.status

        return BotStatus.ERROR


# 全局机器人管理器实例
bot_manager = BotInstanceManager()
