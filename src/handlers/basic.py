"""
基础功能处理器
"""
from datetime import datetime, timedelta
from telegram import Update, ChatMember
from telegram.ext import ContextTypes
from sqlalchemy import select

from ..models import Group, get_db
from .operator import require_manager


async def start_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """开始记账"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id
    chat_title = update.effective_chat.title or "Private Chat"

    async for db in get_db():
        # 查找或创建群组
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if not group:
            # 创建新群组，自动给 1 天免费试用
            now = datetime.utcnow()
            group = Group(
                group_id=chat_id,
                group_name=chat_title,
                group_type=update.effective_chat.type,
                is_active=True,
                trial_expires=now + timedelta(days=1)
            )
            from config import config
            group.exchange_rate = config.DEFAULT_EXCHANGE_RATE
            group.fee_rate = config.DEFAULT_FEE_RATE
            db.add(group)
            trial_msg = f"\n🎉 免费试用 1 天，到期时间：{(now + timedelta(days=1)).strftime('%m-%d %H:%M')} UTC"
        else:
            group.is_active = True
            trial_msg = ""

        await db.commit()

        await update.message.reply_text(f"✅ 记账功能已开启{trial_msg}")


async def stop_billing(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """停止记账"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    async for db in get_db():
        query = select(Group).where(Group.group_id == chat_id)
        result = await db.execute(query)
        group = result.scalar_one_or_none()

        if group:
            group.is_active = False
            await db.commit()
            await update.message.reply_text("⛔ 记账功能已停止")
        else:
            await update.message.reply_text("❌ 未找到群组配置")


async def mute_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """下课（禁言模式）- 需要机器人为管理员"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 设置禁言
        from telegram import ChatPermissions
        permissions = ChatPermissions(can_send_messages=False)
        await context.bot.set_chat_permissions(chat_id, permissions)

        async for db in get_db():
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.is_muted = True
                await db.commit()

        await update.message.reply_text("🔇 群组已进入禁言模式（下课）")

    except Exception as e:
        await update.message.reply_text(f"❌ 操作失败: {str(e)}")


async def unmute_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """上课（解除禁言）- 需要机器人为管理员"""
    if not update.message or not update.effective_chat:
        return

    if not await require_manager(update, context):
        return

    chat_id = update.effective_chat.id

    try:
        # 检查机器人是否为管理员
        bot_member = await context.bot.get_chat_member(chat_id, context.bot.id)
        if bot_member.status not in [ChatMember.ADMINISTRATOR, ChatMember.OWNER]:
            await update.message.reply_text("❌ 机器人需要管理员权限才能执行此操作")
            return

        # 解除禁言
        from telegram import ChatPermissions
        permissions = ChatPermissions(can_send_messages=True, can_send_audios=True, can_send_documents=True,
            can_send_photos=True, can_send_videos=True, can_send_video_notes=True, can_send_voice_notes=True,
            can_send_polls=True, can_send_other_messages=True, can_add_web_page_previews=True)
        await context.bot.set_chat_permissions(chat_id, permissions)

        async for db in get_db():
            query = select(Group).where(Group.group_id == chat_id)
            result = await db.execute(query)
            group = result.scalar_one_or_none()

            if group:
                group.is_muted = False
                await db.commit()

        await update.message.reply_text("🔊 群组已解除禁言（上课）")

    except Exception as e:
        await update.message.reply_text(f"❌ 操作失败: {str(e)}")


async def set_group_access(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """管理员设置群组使用权限（白名单 / 延长）"""
    if not update.message or not update.effective_user:
        return
    # 仅机器人所有者可操作（通过环境变量或简单判断）
    from config import config
    if update.effective_user.id not in getattr(config, 'ADMIN_IDS', []):
        await update.message.reply_text("❌ 仅机器人所有者可操作")
        return

    text = update.message.text.strip()
    parts = text.split()
    if len(parts) < 2:
        await update.message.reply_text("格式：\n开通群组 群ID\n白名单 群ID\n取消白名单 群ID")
        return

    action = parts[0]
    try:
        target_gid = int(parts[1])
    except ValueError:
        await update.message.reply_text("❌ 群ID 必须为数字")
        return

    async for db in get_db():
        group = (await db.execute(select(Group).where(Group.group_id == target_gid))).scalar_one_or_none()
        if not group:
            await update.message.reply_text("❌ 未找到该群组，请先在群内发送「开始」")
            return

        if action == "开通群组":
            days = int(parts[2]) if len(parts) > 2 else 30
            group.access_expires = datetime.utcnow() + timedelta(days=days)
            await db.commit()
            await update.message.reply_text(f"✅ 已开通群组 {target_gid} ，有效期 {days} 天")
        elif action == "白名单":
            group.is_whitelisted = True
            await db.commit()
            await update.message.reply_text(f"✅ 已将群组 {target_gid} 加入白名单（永久可用）")
        elif action == "取消白名单":
            group.is_whitelisted = False
            await db.commit()
            await update.message.reply_text(f"✅ 已取消群组 {target_gid} 白名单")
        else:
            await update.message.reply_text("❌ 未知操作")


async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示帮助信息"""
    if not update.message:
        return

    help_text = """📚 记账助手操作说明,支持功能定制
📄 操作人权限说明

上课下课 ▫️ 上课 / 下课（管理员操作，机器人需有禁言权限）

增加记员 ▫️ 添加操作人 @aaa @bbb
删除记员 ▫️ 删除操作人 @aaa @bbb

增加记员 ▫️ 回复指定人消息：添加操作人
删除记员 ▫️ 回复指定人消息：删除操作人

查看记员 ▫️ 显示操作人

全员记账 ▫️ 设置全员
取消全员 ▫️ 取消全员

全局记员 ▫️ 添加全局操作人 @aaa
删除全局 ▫️ 删除全局操作人 @aaa
查看全局 ▫️ 显示全局操作人

权限范围：
• 群管理员：管理本群操作人、全员模式及上课下课。
• 本群操作人：可在本群记账及调整账单参数。
• 全局操作人：可跨群记账，不因此获得群管理员权限。
• 机器人所有者：可添加、删除全局操作人。
• @成员前，该成员需在本群发过言；也可直接回复其消息操作。

1️⃣ 基本操作（点击指令可复制）
配置费率▫️设置费率10   (支持负数%)
配置汇率▫️设置汇率8
设置实时汇率▫️设置实时汇率
关闭实时汇率▫️关闭实时汇率
添加操作员▫️ 添加操作人@xxxx
删除操作员▫️ 删除操作人@xxxx
查看操作人▫️显示操作人
记账入账▫️+10000
记账入账▫️+10000/7.8
代付减账▫️-10000
代付减账▫️-10000/7.8
下发回分▫️下发5000
撤销上一笔入款 ▫️ 撤销入款
撤销上一笔出款▫️撤销下发
删除账单▫️删除账单
总账单▫️ 显示账单
删除全部账单▫️删除全部账单
上课▫️上课 (解除群禁言需管理员)
下课▫️下课 (群禁言群组需管理员)
开始▫️开始
停止▫️停止

2️⃣ 附加操作
记账备注▫️+1000 空格备注
快捷记账▫️+1000*0.1
快捷记账▫️+1000 张三*0.1
快捷记账▫️+1000 张三/10*0.1
快捷记账▫️+1000/7.8
群员自查▫️发送 /我
定时日切▫️设置日切时间12
设置所有人操作员▫️设置全员
删除所有人操作员▫️取消全员
查询汇率▫️z0 (默认欧易)
火币汇率▫️h0
查U余额▫️直接发送TRC20地址
查U交易▫️查U记录
查身份证▫️查4205041990****
距离▫️两地距离 北京-上海
群发广播▫️群发广播 内容
艾特群员▫️通知所有人
开启群切账▫️设置日切时间06:00
关闭群切账▫️关闭日切
设置入款条数▫️设置入款条数5
设置下发条数▫️设置下发条数5
显示模式1▫️显示模式1
显示模式2▫️显示模式2
显示模式3▫️显示模式3
双币模式▫️双币模式
单币模式▫️单币模式
纯净模式▫️纯净模式
记账置顶▫️记账置顶
置顶关闭▫️置顶关闭

入款样式 ▫️ 入款样式

3️⃣ 团队与导出
创建团队▫️创建团队xx
团队列表▫️团队列表
归档团队▫️归档团队xx
导出账单▫️导出账单
网页账单▫️网页账单
黄金价格▫️黄金价格
法币汇率▫️法币汇率CNY
设置代收▫️设置代收
设置代付▫️设置代付
拉停▫️拉停

❖ 操作人管理由群管理员执行；全局操作人由机器人所有者管理。
❖ 点击▫️后的文字，可快速复制指令"""

    from html import escape

    # Inline code makes command examples selectable/copyable in Telegram.
    lines = []
    for line in help_text.splitlines():
        if "▫️" in line:
            label, command = line.split("▫️", 1)
            lines.append(f"{escape(label.rstrip())} ▫️ <code>{escape(command.strip())}</code>")
        else:
            lines.append(escape(line))
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

