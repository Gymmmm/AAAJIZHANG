
# TG记账机器人 - SaaS多租户系统完整指南

## 📖 系统概述

本系统是一个完整的SaaS多租户Telegram记账机器人平台，支持：

- 🤖 **父子机器人架构** - 主Bot用于销售和管理，子Bot为用户服务
- 💳 **epusdt支付集成** - 自动识别支付并激活服务
- 🌐 **Web管理后台** - 管理员后台、租户后台、网页账单
- 🔐 **完整用户系统** - 自动创建账户、密码管理
- 📊 **实时统计** - 订单、收入、机器人运行状态

## 🏗️ 系统架构

```
┌─────────────────────────────────────────────────────────────┐
│                         用户端                                │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  Telegram用户 ──► 父Bot(主Bot) ──► 购买服务 ──► epusdt支付  │
│                      │                                         │
│                      └──► 提供Bot Token ──► 创建子Bot实例     │
│                                                               │
│  群组成员 ──► 子Bot(记账Bot) ──► 记账功能                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                        Web管理端                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  租户登录 ──► 租户后台 ──► 管理机器人 ──► 查看账单          │
│                           │                                    │
│                           └──► 修改密码                       │
│                                                               │
│  管理员登录 ──► 管理员后台 ──► 用户管理 ──► 系统统计        │
│                              ├──► 订单管理                    │
│                              └──► 配置管理                    │
│                                                               │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                         后端服务                              │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  • Bot实例管理器 - 创建/启动/停止子Bot                       │
│  • 支付服务 - epusdt集成和回调处理                           │
│  • 用户认证 - JWT Token认证                                  │
│  • 数据库 - SQLAlchemy异步ORM                                │
│  • 定时任务 - 日切、状态检查                                 │
│                                                               │
└─────────────────────────────────────────────────────────────┘
```

## 💾 数据库设计

### SaaS相关表

```sql
-- 用户表
users:
  - id, username, password_hash
  - telegram_id, telegram_username
  - role (super_admin/admin/tenant)
  - subscription_expires, max_bots

-- 订单表
orders:
  - order_no, user_id
  - product_name, product_type, price
  - payment_address, payment_amount, payment_tx
  - status (pending/paid/expired)

-- 机器人实例表
bot_instances:
  - user_id, bot_token, bot_username
  - status (creating/running/stopped/error)
  - process_id, total_groups, total_transactions

-- 支付回调表
payment_callbacks:
  - trade_id, order_id, amount
  - block_transaction_id, status
  - processed

-- 系统配置表
system_configs:
  - key, value, description
```

### 记账业务表

```sql
-- 群组配置表
groups:
  - group_id, group_name, is_active
  - exchange_rate, fee_rate
  - display_mode, currency_mode
  - day_cut_time

-- 交易记录表
transactions:
  - group_id, user_id, operator_id
  - transaction_type, amount, currency
  - exchange_rate, fee_rate
  - cny_amount, fee_amount, final_amount

-- 每日汇总表
daily_summaries:
  - group_id, summary_date
  - total_deposit_*, total_withdraw_*
  - total_fee_amount, net_amount
```

## 🚀 快速开始

### 1. 环境准备

```bash
# 安装依赖
pip install -r requirements.txt

# 配置环境变量
cp .env.example .env
nano .env
```

### 2. 配置.env文件

```env
# 主Bot Token（父Bot）
BOT_TOKEN=your_master_bot_token_here

# 超级管理员
SUPER_ADMIN_ID=your_telegram_user_id

# 数据库
DATABASE_URL=sqlite+aiosqlite:///./saas_bot.db

# epusdt配置（需要先部署epusdt系统）
EPUSDT_API_URL=http://your-epusdt-domain.com
EPUSDT_API_KEY=your_api_key

# Web服务配置
WEB_HOST=0.0.0.0
WEB_PORT=8000
WEB_DOMAIN=http://your-domain.com
```

### 3. 初始化系统

```bash
# 初始化数据库
python -m src.init_db

# 创建超级管理员
python -m src.create_admin
```

### 4. 启动服务

```bash
# 方式1：分别启动
# 启动父Bot（主Bot）
python master_bot.py

# 启动Web服务
python web_server.py

# 方式2：使用进程管理器
pm2 start ecosystem.config.js
```

## 📱 父Bot（主Bot）使用流程

### 用户购买服务

1. **用户启动父Bot**
   ```
   用户: /start
   Bot: 显示欢迎消息和功能菜单
   ```

2. **选择购买服务**
   ```
   用户: 点击"购买服务"
   Bot: 显示价格方案（月付/年付/永久）
   ```

3. **选择方案并支付**
   ```
   用户: 选择"月付 - 10 USDT"
   Bot: 生成订单和支付地址
   用户: 向地址转账10 USDT
   ```

4. **自动激活**
   ```
   epusdt: 检测到支付 → 发送回调
   系统: 验证回调 → 激活用户订阅
   Bot: 发送激活成功通知
   ```

### 创建机器人实例

1. **用户选择创建机器人**
   ```
   用户: 点击"创建机器人"
   Bot: 要求提供Bot Token
   ```

2. **用户创建Bot并提供Token**
   ```
   用户: 找到@BotFather → /newbot → 获得Token
   用户: 发送Token给父Bot
   ```

3. **自动创建和启动**
   ```
   系统: 验证Token
   系统: 创建机器人实例目录和配置
   系统: 启动机器人进程
   Bot: 发送创建成功通知
   ```

4. **获取登录凭据**
   ```
   Bot: 发送Web后台登录信息
   用户名: user_123456789
   密码: 随机生成的12位密码
   后台地址: http://your-domain.com/dashboard
   ```

## 🌐 Web后台功能

### 租户后台 (/dashboard)

**功能列表：**

1. **机器人管理**
   - 查看机器人列表
   - 启动/停止/重启机器人
   - 查看机器人状态
   - 删除机器人

2. **账单查看**
   - 按群组查看账单
   - 按日期筛选
   - 查看统计汇总
   - 导出账单数据

3. **个人设置**
   - 修改用户名
   - 修改密码
   - 查看订阅状态

### 管理员后台 (/admin)

**功能列表：**

1. **用户管理**
   - 查看所有用户
   - 修改用户权限
   - 延长/缩短订阅
   - 增加机器人配额

2. **订单管理**
   - 查看所有订单
   - 订单状态管理
   - 手动确认支付

3. **系统统计**
   - 总用户数
   - 总机器人数
   - 运行中的机器人
   - 总收入统计

4. **系统配置**
   - epusdt API配置
   - 价格方案配置
   - 系统参数配置

## 💳 epusdt支付集成

### 1. 部署epusdt系统

参考epusdt官方文档部署：
```bash
git clone https://github.com/assimon/epusdt
cd epusdt
# 按照文档配置和部署
```

### 2. 配置回调地址

在epusdt后台设置回调URL：
```
http://your-domain.com/api/payment/callback
```

### 3. 获取API密钥

在epusdt后台生成API密钥，填入.env文件。

### 4. 支付流程

```
1. 用户选择购买方案
   ↓
2. 系统调用epusdt创建订单
   ↓
3. 返回支付地址和二维码
   ↓
4. 用户扫码支付
   ↓
5. epusdt检测到支付
   ↓
6. epusdt发送回调到我们的系统
   ↓
7. 系统验证签名
   ↓
8. 更新订单状态为已支付
   ↓
9. 激活用户订阅
   ↓
10. 发送Telegram通知
```

## 🤖 子Bot实例管理

### 实例目录结构

```
bot_instances/
├── bot_1/
│   ├── .env          # 实例配置
│   ├── start.py      # 启动脚本
│   └── bot.db        # 实例数据库
├── bot_2/
│   ├── .env
│   ├── start.py
│   └── bot.db
└── ...
```

### 实例管理命令

```python
# Python代码示例

# 创建实例
bot_instance = await bot_manager.create_instance(
    db=db,
    user_id=user.id,
    bot_token="your_bot_token"
)

# 启动实例
await bot_manager.start_instance(db, bot_instance.id)

# 停止实例
await bot_manager.stop_instance(db, bot_instance.id)

# 重启实例
await bot_manager.restart_instance(db, bot_instance.id)

# 删除实例
await bot_manager.delete_instance(db, bot_instance.id)
```

## 🔐 安全注意事项

1. **密钥安全**
   - 不要将BOT_TOKEN提交到代码仓库
   - 定期更换epusdt API密钥
   - 使用强密码策略

2. **支付安全**
   - 验证所有支付回调的签名
   - 记录所有支付日志
   - 防止重放攻击

3. **数据安全**
   - 定期备份数据库
   - 加密敏感信息
   - 限制API访问权限

4. **访问控制**
   - 使用JWT Token认证
   - 实现角色权限控制
   - 记录操作日志

## 📊 API文档

### 认证相关

```
POST /api/auth/login
Body: {username, password}
Response: {access_token, token_type}

GET /api/auth/me
Headers: Authorization: Bearer {token}
Response: {用户信息}

POST /api/auth/change-password
Body: {old_password, new_password}
Response: {message}
```

### 机器人管理

```
GET /api/bots
Response: [{机器人列表}]

POST /api/bots/{bot_id}/start
Response: {message}

POST /api/bots/{bot_id}/stop
Response: {message}

DELETE /api/bots/{bot_id}
Response: {message}
```

### 账单查询

```
GET /api/bills/{bot_id}
Query: group_id, start_date, end_date
Response: [{交易记录}]

GET /api/bills/{bot_id}/summary
Query: group_id, start_date, end_date
Response: {汇总统计}
```

### 管理员API

```
GET /api/admin/users
Response: [{用户列表}]

GET /api/admin/stats
Response: {系统统计}
```

## 🐛 故障排查

### 常见问题

**1. 子Bot无法启动**
```bash
# 检查进程
ps aux | grep python

# 查看日志
tail -f bot_instances/bot_1/logs/bot.log

# 检查配置
cat bot_instances/bot_1/.env
```

**2. 支付回调未触发**
```bash
# 检查epusdt日志
# 验证回调URL是否可访问
curl -X POST http://your-domain.com/api/payment/callback

# 查看数据库记录
sqlite3 saas_bot.db "SELECT * FROM payment_callbacks ORDER BY id DESC LIMIT 10;"
```

**3. Web后台无法访问**
```bash
# 检查服务是否运行
netstat -tuln | grep 8000

# 检查防火墙
sudo ufw status

# 查看日志
tail -f logs/web.log
```

## 📈 性能优化

1. **数据库优化**
   - 使用PostgreSQL替代SQLite
   - 添加适当的索引
   - 定期清理过期数据

2. **缓存优化**
   - 使用Redis缓存热点数据
   - 缓存用户会话
   - 缓存账单统计

3. **负载均衡**
   - 使用Nginx反向代理
   - 部署多个Web实例
   - 使用消息队列处理异步任务

## 📝 开发指南

### 添加新功能

1. **添加数据模型**
   - 在`src/models/`中定义新模型
   - 运行数据库迁移

2. **添加API接口**
   - 在`src/web/api.py`中添加路由
   - 实现业务逻辑

3. **添加前端页面**
   - 在`templates/`中创建模板
   - 在`src/web/app.py`中添加路由

### 测试

```bash
# 单元测试
pytest tests/

# API测试
pytest tests/test_api.py

# 集成测试
pytest tests/test_integration.py
```

## 📞 技术支持

- 文档：http://your-domain.com/docs
- 问题反馈：GitHub Issues
- 邮件：support@your-domain.com
- Telegram群：@your_group

## 📄 许可证

MIT License
