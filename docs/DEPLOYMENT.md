# 部署指南

## 部署方式

### 方式一：直接运行

适用于开发和测试环境。

#### 1. 准备环境
```bash
# 确保Python版本 >= 3.9
python --version

# 创建虚拟环境（推荐）
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows
```

#### 2. 安装依赖
```bash
pip install -r requirements.txt
```

#### 3. 配置环境变量
```bash
# 复制配置文件模板
cp .env.example .env

# 编辑.env文件，填入必要配置
nano .env
```

#### 4. 运行机器人
```bash
python main.py
```

### 方式二：使用systemd服务（Linux）

适用于生产环境，支持自动启动和重启。

#### 1. 创建服务文件
```bash
sudo nano /etc/systemd/system/tg-accounting-bot.service
```

#### 2. 添加以下内容
```ini
[Unit]
Description=Telegram Accounting Bot
After=network.target

[Service]
Type=simple
User=your-username
WorkingDirectory=/path/to/AAAJIZHANG
Environment="PATH=/path/to/venv/bin"
ExecStart=/path/to/venv/bin/python main.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

#### 3. 启动服务
```bash
# 重载systemd配置
sudo systemctl daemon-reload

# 启动服务
sudo systemctl start tg-accounting-bot

# 设置开机自启
sudo systemctl enable tg-accounting-bot

# 查看服务状态
sudo systemctl status tg-accounting-bot

# 查看日志
sudo journalctl -u tg-accounting-bot -f
```

### 方式三：使用Docker

适用于容器化部署。

#### 1. 创建Dockerfile
```dockerfile
FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 运行机器人
CMD ["python", "main.py"]
```

#### 2. 创建docker-compose.yml
```yaml
version: '3.8'

services:
  bot:
    build: .
    container_name: tg-accounting-bot
    restart: always
    env_file:
      - .env
    volumes:
      - ./data:/app/data
      - ./logs:/app/logs
```

#### 3. 运行容器
```bash
# 构建并启动
docker-compose up -d

# 查看日志
docker-compose logs -f

# 停止
docker-compose down

# 重启
docker-compose restart
```

### 方式四：使用进程管理器（PM2）

适用于Node.js环境或需要进程监控的场景。

#### 1. 安装PM2
```bash
npm install -g pm2
```

#### 2. 创建ecosystem配置
```javascript
// ecosystem.config.js
module.exports = {
  apps: [{
    name: 'tg-accounting-bot',
    script: 'main.py',
    interpreter: 'python3',
    cwd: '/path/to/AAAJIZHANG',
    instances: 1,
    autorestart: true,
    watch: false,
    max_memory_restart: '500M',
    env_file: '.env'
  }]
}
```

#### 3. 启动应用
```bash
# 启动
pm2 start ecosystem.config.js

# 查看状态
pm2 status

# 查看日志
pm2 logs tg-accounting-bot

# 重启
pm2 restart tg-accounting-bot

# 停止
pm2 stop tg-accounting-bot

# 开机自启
pm2 startup
pm2 save
```

## 数据库配置

### SQLite（默认）

默认使用SQLite数据库，无需额外配置。

```env
DATABASE_URL=sqlite+aiosqlite:///./accounting_bot.db
```

数据库文件会自动创建在项目根目录。

### PostgreSQL（推荐生产环境）

#### 1. 安装PostgreSQL
```bash
# Ubuntu/Debian
sudo apt-get install postgresql postgresql-contrib

# CentOS/RHEL
sudo yum install postgresql-server postgresql-contrib
```

#### 2. 创建数据库和用户
```bash
sudo -u postgres psql

CREATE DATABASE accounting_bot;
CREATE USER bot_user WITH PASSWORD 'your_password';
GRANT ALL PRIVILEGES ON DATABASE accounting_bot TO bot_user;
\q
```

#### 3. 更新配置
```env
DATABASE_URL=postgresql+asyncpg://bot_user:your_password@localhost/accounting_bot
```

#### 4. 安装异步驱动
```bash
pip install asyncpg
```

## 获取Bot Token

### 1. 创建Bot

1. 在Telegram中找到 [@BotFather](https://t.me/BotFather)
2. 发送 `/newbot`
3. 按提示设置机器人名称和用户名
4. 获得Bot Token（格式：`1234567890:ABCdefGHIjklMNOpqrsTUVwxyz`）

### 2. 配置Bot

```bash
# 设置Bot描述
/setdescription

# 设置Bot简介
/setabouttext

# 设置Bot头像
/setuserpic

# 设置命令列表
/setcommands
```

推荐的命令列表：
```
start - 开始使用机器人
help - 查看帮助信息
我 - 查看我的账单
```

### 3. 获取用户ID

发送消息给 [@userinfobot](https://t.me/userinfobot) 获取你的用户ID，用于设置超级管理员。

## 性能优化

### 1. 数据库优化

#### SQLite
```python
# 在config.py中添加
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
}
```

#### PostgreSQL
```python
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 20,
    'max_overflow': 10,
    'pool_pre_ping': True,
    'pool_recycle': 3600,
}
```

### 2. 启用日志

```python
# 在main.py中配置
import logging

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.FileHandler('logs/bot.log'),
        logging.StreamHandler()
    ]
)
```

### 3. 定期备份

```bash
# 添加到crontab
0 2 * * * /path/to/backup.sh

# backup.sh内容
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
cp /path/to/accounting_bot.db /path/to/backups/accounting_bot_$DATE.db
# 保留最近30天的备份
find /path/to/backups -name "accounting_bot_*.db" -mtime +30 -delete
```

## 监控和维护

### 1. 日志监控

```bash
# 实时查看日志
tail -f logs/bot.log

# 搜索错误
grep ERROR logs/bot.log

# 分析日志
cat logs/bot.log | grep "$(date +%Y-%m-%d)" | wc -l
```

### 2. 性能监控

```bash
# 查看进程资源使用
top -p $(pgrep -f main.py)

# 查看数据库大小
du -h accounting_bot.db

# 查看连接数（PostgreSQL）
sudo -u postgres psql -c "SELECT count(*) FROM pg_stat_activity WHERE datname='accounting_bot';"
```

### 3. 定期维护

```bash
# 清理旧日志（保留最近7天）
find logs/ -name "*.log" -mtime +7 -delete

# 优化数据库（SQLite）
sqlite3 accounting_bot.db "VACUUM;"

# 优化数据库（PostgreSQL）
sudo -u postgres psql accounting_bot -c "VACUUM ANALYZE;"
```

## 故障排查

### 常见问题

#### 1. Bot无响应
```bash
# 检查进程是否运行
ps aux | grep main.py

# 查看最近的错误日志
tail -n 50 logs/bot.log | grep ERROR

# 检查网络连接
curl -I https://api.telegram.org
```

#### 2. 数据库连接失败
```bash
# 检查数据库文件权限
ls -l accounting_bot.db

# PostgreSQL连接测试
psql -h localhost -U bot_user -d accounting_bot

# 查看数据库日志
tail -f /var/log/postgresql/postgresql-*.log
```

#### 3. 内存占用过高
```bash
# 查看内存使用
free -h

# 重启服务
sudo systemctl restart tg-accounting-bot

# 考虑增加swap
sudo fallocate -l 2G /swapfile
sudo chmod 600 /swapfile
sudo mkswap /swapfile
sudo swapon /swapfile
```

## 安全建议

1. **不要泄露Bot Token**
   - 将.env添加到.gitignore
   - 不要在公共场合分享Token
   - 定期更换Token

2. **限制访问权限**
   - 设置文件权限：`chmod 600 .env`
   - 使用专用用户运行服务
   - 配置防火墙规则

3. **数据备份**
   - 定期备份数据库
   - 测试恢复流程
   - 异地存储备份

4. **更新依赖**
   ```bash
   pip list --outdated
   pip install --upgrade package_name
   ```

## 扩展部署

### 多实例部署

如果需要服务多个不同的机器人：

```bash
# 复制项目目录
cp -r AAAJIZHANG bot1
cp -r AAAJIZHANG bot2

# 分别配置不同的.env
cd bot1 && nano .env
cd bot2 && nano .env

# 使用不同的服务名
sudo systemctl start tg-accounting-bot-1
sudo systemctl start tg-accounting-bot-2
```

### 负载均衡

对于大规模部署，可以考虑：
- 使用Redis作为会话存储
- 部署多个Bot实例
- 使用消息队列处理请求

## 技术支持

遇到问题？

1. 查看日志文件
2. 检查配置是否正确
3. 确认网络连接正常
4. 查阅项目文档
5. 提交Issue寻求帮助
