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

    help_text = """📚 记账机器人操作说明

<>️ 基础功能
开始记账▫️开始
停止记账▫️停止
打开发言▫️上课
停止发言▫️下课

<>️ 操作人设置
增加记员▫️添加操作人 @aaa
删除记员▫️删除操作人 @aaa
查看记员▫️显示操作人
全部记员▫️设置全员
取消全员▫️取消全员

<>️ 账单显示
账单条数▫️设置入款条数5
账单条数▫️设置下发条数5
置顶开启▫️记账置顶
置顶关闭▫️置顶关闭
双币模式▫️双币模式
单币模式▫️单币模式
纯净模式▫️纯净模式
显示回复人▫️显示回复人
显示入账人▫️显示入账人
显示模式1▫️显示模式1（最近3笔）
显示模式2▫️显示模式2（最近1笔）
显示模式3▫️显示模式3（仅汇总）

<>️ 账单参数
入款汇率▫️设置汇率7.3
入款费率▫️设置费率3
单独汇率▫️设置张三汇率7.3
单独费率▫️设置张三费率3
删除费汇▫️删除张三配置
查看费汇▫️费汇配置
实时汇率▫️设置实时汇率
定时日切▫️设置日切时间06:00
关闭日切▫️关闭日切

<>️ 账单操作
显示账单▫️显示账单 或 +0
全部账单▫️全部账单
账单汇总▫️账单汇总
我的账单▫️/我
指定账单▫️查账单张三
保存账单▫️保存账单
删除账单▫️删除账单
删除全部▫️删除全部账单
撤销入款▫️撤销入款
撤销下发▫️撤销下发
回复撤销▫️回复消息：撤销

<>️ 记账入账
记账入账▫️+1000
单独汇率▫️+1000/7.3
单独费率▫️+1000*0.12
记账入账▫️+1000u
组合入账▫️+1000u/7.3*0.12
指定入账▫️张三+1000
备注入账▫️+1000 备注
入账修正▫️-1000
记账下发▫️下发1000
记账下发▫️下发1000r
指定下发▫️张三下发1000
下发修正▫️下发-1000
余额调整▫️余额+100

<>️ 查询功能
火币U价▫️h0
欧易U价▫️z0
查U地址▫️直接发送TRC20地址
查U记录▫️查U记录
黄金价格▫️黄金价格
查身份证▫️查4205041990****
法币汇率▫️法币汇率CNY
两地距离▫️回复地址后发两地距离 目标地址
计算功能▫️计算 100+200

<>️ 辅助功能
下发地址▫️设置下发地址Txxxx
下发地址▫️下发地址
爱特群员▫️通知所有人
群组分组▫️设置分组 AA
群发广播▫️群发广播 内容
设置代收▫️设置代收
设置代付▫️设置代付
拉停▫️拉停
开启分类▫️开启分类
关闭分类▫️关闭分类

<>️ 团队功能
创建团队▫️创建团队xx
团队列表▫️团队列表
归档团队▫️归档团队xx

<>️ 导出
导出账单▫️导出账单
网页账单▫️网页账单

❖ 以上为本机器人所有功能配置及指令示例
❖ 点击▫️后的文字，可快速复制指令"""

    await update.message.reply_text(help_text)
