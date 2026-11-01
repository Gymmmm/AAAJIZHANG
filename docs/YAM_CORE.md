# Yam 核心记账交付

- CNY 最多两位小数，USDT 最多六位小数。使用 Decimal 计算，人民币按分四舍五入；原始精确值另存于 ledger_receipts，不改变历史金额。
- 费率统一为百分数：设置费率3、设置费率3%、单笔 *3% 均为 3%；*0.12 为 0.12%。个人配置和单笔配置中的零不会回落为群默认费率。
- 汇率单位为 CNY / USDT。CNY、USDT 的原始金额分别保留；混币汇总先按单笔汇率折算，不能将人民币原额标作 USDT。
- 已有入款和下发均按原有群费率处理，单笔费率优先，个人其次，群默认最后。净额为入款净额减下发净额；寄存独立显示，不混入净额。
- 负数修正新增一笔记录，不修改原账。精确撤销支持回复原消息或机器人回执；恢复及撤销写入 ledger_audit。
- 消息去重由 group_id + message_id 数据库唯一约束保障，涵盖并发重试和已撤销消息。发送确认失败不会删除已保存的账。
- 人名及 @用户名仅匹配本群实际见过的 Telegram 身份；重名、未见过的名字拒绝猜测，可回复成员消息操作。
- 手动保存结束本期，自动日切按群设置与 Asia/Phnom_Penh 时区结账。历史原始记录保留，报表可导出。
- Excel 包含原币金额、费汇、操作人、状态及撤销/恢复审计。所有自由文本存为文本单元格，避免作为 Excel 公式执行。
- 网页账单为按群签名的一小时只读链接，持有链接即可查看该群账单，仅分享给对账人员。过期重新申请。
- Web 进程仅监听 127.0.0.1:8082，Caddy 将 /yam/* strip 后转发。YAM_REPORT_URL 配置为 https://gymmm-api.50.114.74.120.sslip.io/yam。
- 模型升级仅新增 ledger_receipts、ledger_audit、known_members、ledger_periods 四张表，不覆盖旧账目。

验证：`PYTHONPATH=. python -m unittest discover -s tests -p 'test_*.py'`，以及 `PYTHONPATH=. python tests/smoke_single_bot.py`。
