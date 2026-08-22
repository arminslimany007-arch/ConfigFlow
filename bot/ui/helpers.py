# -*- coding: utf-8 -*-
"""
Core Telegram UI helpers: message editing/sending, bot commands,
and multi-channel forced-join enforcement.
"""
import json
import logging

from telebot import types

from ..db import setting_get
from ..bot_instance import bot

logger = logging.getLogger(__name__)

# ── Bot commands ───────────────────────────────────────────────────────────────
def set_bot_commands():
    try:
        bot.set_my_commands([types.BotCommand("start", "شروع ربات")])
    except Exception:
        pass


# ── Message send/edit ──────────────────────────────────────────────────────────
def send_or_edit(call_or_msg, text, reply_markup=None, disable_preview=True):
    """Edit an existing message (from a callback) or send a new one."""
    try:
        if hasattr(call_or_msg, "message"):
            bot.edit_message_text(
                text,
                call_or_msg.message.chat.id,
                call_or_msg.message.message_id,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_preview,
            )
        else:
            bot.send_message(
                call_or_msg.chat.id, text,
                reply_markup=reply_markup,
                disable_web_page_preview=disable_preview
            )
    except Exception:
        try:
            chat_id = (
                call_or_msg.message.chat.id
                if hasattr(call_or_msg, "message")
                else call_or_msg.chat.id
            )
            bot.send_message(chat_id, text,
                             reply_markup=reply_markup,
                             disable_web_page_preview=disable_preview)
        except Exception:
            pass




# ── Forced Join (multi-channel) ────────────────────────────────────────────────

def get_forced_channels() -> list:
    """
    Return ALL forced channels as a list of dicts:
        {"name": str, "id": str, "username": str}

    Combines:
      • legacy `channel_id` setting (single channel, backward compat)
      • new `forced_channels` setting (JSON array of channel dicts)
    """
    channels: list = []

    # Legacy single-channel setting
    old_cid = setting_get("channel_id", "").strip()
    if old_cid:
        channels.append({
            "name":     "کانال ما",
            "id":       old_cid,
            "username": old_cid if old_cid.startswith("@") else "",
        })

    # New multi-channel JSON setting
    try:
        extra = json.loads(setting_get("forced_channels", "[]") or "[]")
        if isinstance(extra, list):
            for ch in extra:
                if isinstance(ch, dict) and (ch.get("id") or ch.get("username")):
                    channels.append(ch)
    except Exception:
        pass

    return channels


def _channel_join_url(ch: dict) -> str:
    """Build a t.me invite URL for a channel dict."""
    ch_id    = str(ch.get("id")       or "").strip()
    username = str(ch.get("username") or "").strip()
    if username.startswith("@"):
        return f"https://t.me/{username.lstrip('@')}"
    if ch_id.startswith("@"):
        return f"https://t.me/{ch_id.lstrip('@')}"
    if ch_id.startswith("-100"):
        return f"https://t.me/c/{ch_id[4:]}"
    return f"https://t.me/{ch_id}"


def _is_member(ch_id_str: str, user_id: int) -> bool:
    """Check membership of user_id in the given channel id/username string."""
    try:
        member = bot.get_chat_member(ch_id_str, user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as exc:
        logger.debug("Membership check error for channel %s: %s", ch_id_str, exc)
        return True  # on API error assume OK (don't block on Telegram outage)


def check_channel_membership(user_id: int) -> bool:
    """Return True only when the user is a member of ALL forced channels."""
    for ch in get_forced_channels():
        ch_id = str(ch.get("id") or ch.get("username", "")).strip()
        if not ch_id:
            continue
        if not _is_member(ch_id, user_id):
            return False
    return True


def get_unjoined_channels(user_id: int) -> list:
    """Return only the channels the user has NOT yet joined."""
    result = []
    for ch in get_forced_channels():
        ch_id = str(ch.get("id") or ch.get("username", "")).strip()
        if not ch_id:
            continue
        if not _is_member(ch_id, user_id):
            result.append(ch)
    return result


def channel_lock_message(target, uid: int = None):
    """
    Show the forced-join message listing every channel the user hasn't joined yet.
    Works for both Message objects and CallbackQuery objects.
    """
    if uid is None:
        if hasattr(target, "from_user") and target.from_user:
            uid = target.from_user.id
        elif hasattr(target, "message") and target.message and target.message.from_user:
            uid = target.message.from_user.id

    unjoined = get_unjoined_channels(uid) if uid else get_forced_channels()
    if not unjoined:
        # Fallback: list all channels
        unjoined = get_forced_channels()

    kb = types.InlineKeyboardMarkup()
    for ch in unjoined:
        name = ch.get("name") or "کانال"
        kb.add(types.InlineKeyboardButton(
            f"📢 عضویت در {name}",
            url=_channel_join_url(ch),
        ))
    kb.add(types.InlineKeyboardButton("✅ عضو شدم، بررسی کن", callback_data="check_channel"))

    send_or_edit(
        target,
        "🔒 <b>برای استفاده از ربات، باید در همه کانال‌های اجباری عضو شوید.</b>\n\n"
        "پس از عضویت، روی «عضو شدم» بزنید.",
        kb,
    )
