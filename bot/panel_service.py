# -*- coding: utf-8 -*-
"""
تحویل سرویس از روی پنل 3x-ui (در برابر تحویل از انبار).

مرز این ماژول عمداً باریک است: ورودی، سطرِ پنل و سطرِ پکیج؛ خروجی، ایمیل
سرویس و لینک‌ها. هیچ‌چیزی از تلگرام اینجا نمی‌آید، تا همین منطق را هم ربات
(وقتی به پنل دسترسی دارد) و هم ورکر ایران (وقتی ندارد) بتوانند اجرا کنند.
"""
import time

from .xui_api import XuiError, client_from_row
from .db import get_panel_package_inbound_ids

GB = 1024 ** 3


def build_service_email(user_id, purchase_ref):
    """
    شناسهٔ یکتای سرویس روی پنل.

    ایمیل در 3x-ui کلید یکتای کلاینت است، پس باید بین همهٔ مشتریانِ همهٔ
    ربات‌ها یکتا بماند. الگوی cf-<user>-<ref> هم یکتاست و هم موقع دیباگ
    روی پنل معلوم می‌کند این سرویس مال کیست.
    """
    return f"cf-{int(user_id)}-{purchase_ref}"


def compute_limits(pp_row):
    """(بایت, میلی‌ثانیهٔ انقضا) از روی پکیج. صفر یعنی نامحدود — قرارداد خود پنل."""
    try:
        gb = float(pp_row["volume_gb"] or 0)
    except (TypeError, ValueError):
        gb = 0.0
    try:
        days = int(pp_row["duration_days"] or 0)
    except (TypeError, ValueError):
        days = 0
    total_bytes = int(gb * GB) if gb > 0 else 0
    expiry_ms   = int((time.time() + days * 86400) * 1000) if days > 0 else 0
    return total_bytes, expiry_ms


def provision(panel_row, pp_row, user_id, purchase_ref):
    """
    ساخت سرویس روی پنل و برگرداندن {email, links, config}.

    اگر پکیج به هیچ اینباندی وصل نباشد، همین‌جا و با پیام روشن شکست می‌خورد؛
    ساختن کلاینتِ بی‌اینباند روی پنل موفق می‌شود ولی هیچ لینکی نمی‌دهد و
    مشتری یک سرویسِ ظاهراً سالمِ بی‌فایده می‌گیرد.
    """
    inbound_ids = get_panel_package_inbound_ids(pp_row)
    if not inbound_ids:
        raise XuiError("این پکیج به هیچ اینباندی وصل نیست.")

    email                  = build_service_email(user_id, purchase_ref)
    total_bytes, expiry_ms = compute_limits(pp_row)
    limit_ip               = _int_col(pp_row, "limit_ip", 0)

    cli = client_from_row(panel_row)
    cli.add_client(email, inbound_ids,
                   total_bytes=total_bytes, expiry_ms=expiry_ms,
                   limit_ip=limit_ip, comment=f"ConfigFlow user {user_id}")

    links = cli.client_links(email)
    if not links:
        # کلاینت ساخته شد ولی لینکی درنیامد: معمولاً یعنی اینباند پروتکلِ
        # لینک‌پذیر نیست (socks/http/wireguard). سرویس را پاک نمی‌کنیم تا
        # ادمین بتواند روی پنل ببیندش و تصمیم بگیرد.
        raise XuiError("کلاینت ساخته شد ولی پنل لینکی برنگرداند — "
                       "پروتکل اینباند را بررسی کنید.")
    return {"email": email, "links": links, "config": links[0]}


def renew(panel_row, email, pp_row):
    """تمدید سرویس موجود با همان حجم و مدت پکیج."""
    total_bytes, _ = compute_limits(pp_row)
    days           = _int_col(pp_row, "duration_days", 0)
    cli = client_from_row(panel_row)
    cli.extend_client(email, add_days=days, add_bytes=total_bytes)
    return True


def usage(panel_row, email):
    """مصرف فعلی سرویس: {up, down, total, expiryTime} یا None اگر پیدا نشد."""
    try:
        return client_from_row(panel_row).client_traffic(email)
    except XuiError:
        return None


def test_connection(panel_row):
    """(ok, پیام) — پشت دکمهٔ «تست اتصال» در پنل ادمین."""
    try:
        cli    = client_from_row(panel_row)
        status = cli.server_status() or {}
        xray   = (status.get("xray") or {})
        return True, (f"اتصال برقرار شد — Xray: {xray.get('state', 'نامشخص')}"
                      f" {xray.get('version', '')}".strip())
    except XuiError as e:
        return False, str(e)
    except Exception as e:
        return False, f"خطای غیرمنتظره: {e}"


def sync_inbounds(panel_row):
    """(ok, تعداد یا پیام خطا) — اینباندهای پنل را می‌گیرد و در کش می‌نویسد."""
    from .db import save_panel_inbounds, update_panel_field
    from .helpers import now_str
    try:
        inbounds = client_from_row(panel_row).list_inbounds()
    except XuiError as e:
        update_panel_field(panel_row["id"], "last_error", str(e))
        return False, str(e)
    n = save_panel_inbounds(panel_row["id"], inbounds)
    update_panel_field(panel_row["id"], "last_error", "")
    update_panel_field(panel_row["id"], "last_sync_at", now_str())
    return True, n


def _int_col(row, name, default=0):
    try:
        v = row[name]
    except (IndexError, KeyError):
        return default
    try:
        return int(v)
    except (TypeError, ValueError):
        return default
