# -*- coding: utf-8 -*-
"""
کلاینت پنل 3x-ui نسل ۳ (Sanaei).

فقط کتابخانهٔ استاندارد پایتون استفاده می‌شود تا worker.py هم — که روی سرور
ایران و بدون venv اجرا می‌شود — بتواند همین ماژول را وارد کند.

دو نکته که کل طراحی را شکل می‌دهند:

۱. در نسل ۳، «کلاینت» موجودیت مستقلی است، نه فیلدی داخل یک اینباند. یک کلاینت
   با یک ایمیل ساخته می‌شود و به چند اینباند وصل می‌شود؛ همان هویت، همان
   حجم، همان انقضا، روی همهٔ آن‌ها. برای ما یعنی: یک سرویس = یک ایمیل.

۲. لینک اشتراک را دیگر خودمان نمی‌سازیم. پنل با /clients/links/{email} همان
   رشته‌ای را می‌دهد که دکمهٔ Copy URL خودش کپی می‌کند — با تمام جزئیات
   reality و flow و host که ساختن دستی‌شان منبع همیشگی باگ بود.

مرجع: /panel/api/openapi.json روی هر پنل (نسخهٔ 3.x).
"""
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request

_UA      = "ConfigFlow/2.0"
_TIMEOUT = 20


class XuiError(RuntimeError):
    """خطای قابل نمایش از سمت پنل — پیام فارسی/انگلیسی خودِ پنل را حمل می‌کند."""


def build_base_url(scheme, host, port, base_path=""):
    """آدرس پایهٔ پنل: https://host:2053/8cArBwxibFyFA23bqd (بدون اسلش آخر)."""
    scheme = (scheme or "https").strip().lower()
    host   = (host or "").strip().rstrip("/")
    # اگر کاربر کل URL را در فیلد آدرس چسبانده باشد، همان را می‌پذیریم
    if host.startswith("http://") or host.startswith("https://"):
        parsed = urllib.parse.urlparse(host)
        scheme = parsed.scheme
        host   = parsed.hostname or ""
        port   = parsed.port or port
        if parsed.path.strip("/"):
            base_path = parsed.path
    base = f"{scheme}://{host}"
    if port:
        base += f":{int(port)}"
    bp = (base_path or "").strip().strip("/")
    if bp:
        base += f"/{bp}"
    return base


class XuiClient:
    """
    یک پنل 3x-ui نسل ۳.

    احراز هویت به دو شکل ممکن است و ترتیبش مهم است: اگر توکن API داده شده
    باشد از آن استفاده می‌شود (بدون session، بدون CSRF، بدون انقضا)، وگرنه
    با نام کاربری و رمز لاگین می‌کنیم و کوکی را نگه می‌داریم. توکن روش
    توصیه‌شده است — رمز پنل را جای دیگری پخش نمی‌کند و session منقضی نمی‌شود.
    """

    def __init__(self, base_url, api_token="", username="", password="",
                 verify_tls=True, timeout=_TIMEOUT):
        self.base       = (base_url or "").rstrip("/")
        self.api_token  = (api_token or "").strip()
        self.username   = username or ""
        self.password   = password or ""
        self.timeout    = timeout
        ctx = None
        if not verify_tls:
            # پنل‌ها معمولاً گواهی self-signed دارند؛ اپراتور باید بتواند
            # آگاهانه بررسی را خاموش کند، وگرنه هیچ پنلی وصل نمی‌شود.
            ctx = ssl.create_default_context()
            ctx.check_hostname = False
            ctx.verify_mode    = ssl.CERT_NONE
        self._ssl_ctx = ctx
        self._opener  = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(),
            *( [urllib.request.HTTPSHandler(context=ctx)] if ctx else [] )
        )
        self._logged_in = False

    # ── لایهٔ انتقال ─────────────────────────────────────────────────────────
    def _request(self, method, path, body=None, _retry=True):
        url     = f"{self.base}{path}"
        headers = {"User-Agent": _UA, "Accept": "application/json"}
        if self.api_token:
            headers["Authorization"] = f"Bearer {self.api_token}"
        data = None
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        try:
            with self._opener.open(req, timeout=self.timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
            # ۴۰۱ با کوکی یعنی session پریده؛ یک‌بار دوباره لاگین می‌کنیم.
            if e.code in (401, 403) and not self.api_token and _retry:
                self._logged_in = False
                if self.login():
                    return self._request(method, path, body, _retry=False)
            raise XuiError(_extract_msg(raw) or f"HTTP {e.code} از {path}")
        except Exception as e:
            raise XuiError(f"اتصال به پنل ممکن نشد: {e}")

        try:
            payload = json.loads(raw)
        except ValueError:
            # یک صفحهٔ HTML یعنی معمولاً base_path اشتباه است یا لاگین نشده‌ایم
            raise XuiError("پاسخ پنل JSON نبود — مسیر پایه یا توکن را بررسی کنید.")
        if isinstance(payload, dict) and payload.get("success") is False:
            raise XuiError(payload.get("msg") or "پنل درخواست را رد کرد.")
        return payload.get("obj") if isinstance(payload, dict) else payload

    def _ensure_auth(self):
        if self.api_token or self._logged_in:
            return
        if not self.login():
            raise XuiError("ورود به پنل ناموفق بود.")

    def login(self):
        """لاگین با نام کاربری/رمز. فقط وقتی لازم است که توکن API نداریم."""
        if self.api_token:
            return True
        try:
            self._request("POST", "/login", {
                "username": self.username,
                "password": self.password,
            }, _retry=False)
        except XuiError:
            return False
        self._logged_in = True
        return True

    # ── سلامت و کشف ──────────────────────────────────────────────────────────
    def server_status(self):
        """برای دکمهٔ «تست اتصال»: اگر این جواب داد، احراز هویت و مسیر درست‌اند."""
        self._ensure_auth()
        return self._request("GET", "/panel/api/server/status")

    def list_inbounds(self):
        """
        اینباندهای پنل به‌صورت سبک (id, remark, protocol, port, enable).

        عمداً از options استفاده می‌شود نه list: روی پنلی با هزاران کلاینت،
        list کل settings و clientStats را هم می‌فرستد و مگابایت‌ها می‌شود.
        """
        self._ensure_auth()
        rows = self._request("GET", "/panel/api/inbounds/options") or []
        out  = []
        for r in rows:
            out.append({
                "id":       r.get("id"),
                "remark":   r.get("remark") or r.get("tag") or f"inbound {r.get('id')}",
                "protocol": r.get("protocol") or "",
                "port":     r.get("port") or 0,
                "enable":   bool(r.get("enable", True)),
            })
        return out

    # ── چرخهٔ عمر کلاینت ─────────────────────────────────────────────────────
    def add_client(self, email, inbound_ids, total_bytes=0, expiry_ms=0,
                   limit_ip=0, comment="", tg_id=0):
        """
        ساخت کلاینت و وصل کردنش به یک یا چند اینباند، در یک فراخوانی.

        هیچ راز پروتکلی نمی‌فرستیم: پنل خودش UUID (برای vless/vmess)، رمز
        (trojan/shadowsocks)، auth (hysteria) و کلید (wireguard) را می‌سازد.
        این عمدی است — تولید کلید سمت ما یعنی تکرار منطق پنل و ریسک ساختن
        مقداری که آن پروتکل قبولش ندارد.

        total_bytes = 0 یعنی نامحدود، expiry_ms = 0 یعنی بی‌انقضا (قرارداد خود پنل).
        """
        self._ensure_auth()
        client = {
            "email":      email,
            "enable":     True,
            "totalGB":    int(total_bytes),   # نام فیلد GB است ولی واحدش بایت است
            "expiryTime": int(expiry_ms),
            "limitIp":    int(limit_ip),
            "tgId":       int(tg_id),
            "comment":    comment or "",
        }
        return self._request("POST", "/panel/api/clients/add", {
            "client":     client,
            "inboundIds": [int(i) for i in inbound_ids],
        })

    def get_client(self, email):
        self._ensure_auth()
        return self._request("GET", f"/panel/api/clients/get/{urllib.parse.quote(email)}")

    def client_links(self, email):
        """
        همهٔ لینک‌های اشتراک این کلاینت، دقیقاً همان‌طور که خود پنل می‌سازد.

        این جایگزین ساختن دستی vless:// است؛ پارامترهای reality/flow/host را
        پنل بهتر از ما می‌داند و با هر آپدیت خودش به‌روز می‌شود.
        """
        self._ensure_auth()
        return self._request("GET", f"/panel/api/clients/links/{urllib.parse.quote(email)}") or []

    def client_traffic(self, email):
        """مصرف و انقضای کلاینت — برای نمایش «حجم باقی‌مانده» به کاربر."""
        self._ensure_auth()
        return self._request("GET", f"/panel/api/clients/traffic/{urllib.parse.quote(email)}")

    def extend_client(self, email, add_days=0, add_bytes=0):
        """
        تمدید: افزودن روز و/یا حجم به کلاینت موجود.

        پنل خودش کلاینتی را که فقط به‌خاطر اتمام حجم یا انقضا غیرفعال شده
        دوباره فعال می‌کند، ولی کلاینتی که دستی غیرفعال شده دست‌نخورده
        می‌ماند — یعنی تمدید، تصمیم اپراتور را بازنمی‌گرداند.
        """
        self._ensure_auth()
        return self._request("POST", "/panel/api/clients/bulkAdjust", {
            "emails":   [email],
            "addDays":  int(add_days),
            "addBytes": int(add_bytes),
        })

    def set_enabled(self, email, enabled):
        self._ensure_auth()
        path = "/panel/api/clients/bulkEnable" if enabled else "/panel/api/clients/bulkDisable"
        return self._request("POST", path, {"emails": [email]})

    def reset_traffic(self, email):
        self._ensure_auth()
        return self._request(
            "POST", f"/panel/api/clients/resetTraffic/{urllib.parse.quote(email)}")

    def delete_client(self, email, keep_traffic=False):
        self._ensure_auth()
        q = "?keepTraffic=1" if keep_traffic else ""
        return self._request(
            "POST", f"/panel/api/clients/del/{urllib.parse.quote(email)}{q}")


def _extract_msg(raw):
    try:
        return (json.loads(raw) or {}).get("msg") or ""
    except Exception:
        return ""


def client_from_row(panel_row, timeout=_TIMEOUT):
    """
    یک XuiClient از سطر جدول panels.

    ستون‌های نسل قدیم (ip/port/patch/username/password) هنوز خوانده می‌شوند
    تا پنل‌هایی که قبلاً ثبت شده‌اند بدون ویرایش کار کنند.
    """
    def _col(name, default=None):
        try:
            v = panel_row[name]
        except (IndexError, KeyError):
            return default
        return default if v is None else v

    base = build_base_url(
        _col("scheme", "https"),
        _col("ip", ""),
        _col("port", 2053),
        _col("base_path", "") or _col("patch", ""),
    )
    return XuiClient(
        base,
        api_token  = _col("api_token", "") or "",
        username   = _col("username", "") or "",
        password   = _col("password", "") or "",
        verify_tls = bool(int(_col("verify_tls", 0) or 0)),
        timeout    = timeout,
    )
