<div align="center">

# ⚡ ConfigFlow

### A Telegram bot that sells and manages VPN configs

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://www.python.org)
[![Telebot](https://img.shields.io/badge/pyTelegramBotAPI-4.x-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://github.com/eternnoir/pyTelegramBotAPI)
[![SQLite](https://img.shields.io/badge/SQLite-3-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://www.sqlite.org)
[![License](https://img.shields.io/badge/License-MIT-yellow?style=for-the-badge)](LICENSE)
[![Stars](https://img.shields.io/github/stars/Emadhabibnia1385/ConfigFlow?style=for-the-badge&logo=github)](https://github.com/Emadhabibnia1385/ConfigFlow/stargazers)

**Free and open source — no licence, no activation, no lock**

[Quick install](#-quick-install) • [Features](#-features) • [Gateways](#-payment-gateways) • [Admin panel](#️-admin-panel) • [فارسی](README.md)

</div>

---

## 📖 About

ConfigFlow automates the whole VPN-config sales cycle on Telegram — service selection, payment, and delivery — with no manual step in between.

### 💡 The stock-inventory model

Most VPN bots connect to a panel and create a config at purchase time. ConfigFlow delivers from **stock**: the admin loads pre-made configs (one at a time or in bulk) and the bot sells from that inventory.

| Benefit | Why it matters |
|---|---|
| 🔒 Smaller attack surface | The bot holds no live panel credentials, so a compromised bot doesn't expose the panel |
| 🛡️ Independence | Panel downtime or a server migration doesn't stop sales |
| ✅ Quality control | The admin tests each config before it goes on sale |
| 📊 Honest inventory | Available / sold / expired counts are always exact |

**When stock runs out**, the customer's payment is not rejected. The order goes into a manual-delivery queue, admins are notified, and it is fulfilled **automatically** the moment new configs are added.

---

## ✨ Features

### 🛒 Selling
- Service categories with packages (volume / duration / price)
- Five payment methods
- Automatic delivery with a **QR code**
- Free trial, once per service type
- Service renewal
- Order queue with automatic fulfilment on restock

### 📦 Inventory
- Single and bulk config entry
- Strip a common prefix/suffix from service names during bulk import
- Multi-select for bulk delete or expire
- Available / sold / expired split
- Atomic reservation — two simultaneous buyers can never receive the same config

### 💰 Money
- Built-in wallet with top-ups
- Admin approves or rejects receipts, with a reason recorded
- Per-gateway minimum and maximum amounts
- "Secure" gateways shown only to verified users

### 🤝 Reseller system
- Users apply from inside the bot
- Per-reseller pricing: percentage, fixed offset, or a hand-set price per package
- Category-level discounts
- Resellers see their own price, never the public one

### 🎁 Referrals
- A personal invite link per user
- Sign-up reward and first-purchase reward
- Paid out as wallet credit or as a package
- Configurable banner (text + image)

### 🔐 Administration
- 17 separate permissions for sub-admins
- User states: safe / unsafe / restricted
- Forced membership across multiple channels
- Admin group with one topic per event type (purchases, payments, backups, errors)
- Scheduled database backups delivered over Telegram
- Broadcast messages and pinned announcements

---

## 🏗️ Architecture

```
main.py ──┬─ init_db()                   tables + migrations
          ├─ backup thread               periodic DB delivery
          ├─ group-topic thread
          ├─ owner promo thread
          ├─ Flask API (optional, :8080) only when the worker is enabled
          └─ bot.infinity_polling()      the Telegram loop
```

- **One** catch-all callback handler → `on_callback` → `_dispatch_callback` (~250 branches)
- **One** message handler → `universal_handler` over ~90 states
- Raw SQLite in WAL mode; a fresh connection per call
- Non-blocking per-user lock — a rapid double-click is dropped, not queued

### Purchase flow

```
category → package → payment method
      ↓
payment (wallet | card | crypto | gateway)
      ↓
complete_payment()        ← atomic guard: exactly one path wins
      ↓
reserve_first_config()    ← atomic reservation from stock
      ↓
      ├── success  → deliver config + QR, record the purchase
      └── empty/failed → manual-delivery queue + admin notice
```

---

## 💳 Payment gateways

| # | Gateway | Type | Confirmation |
|---|---|---|---|
| 1 | **Wallet** | internal balance | instant |
| 2 | **Card transfer** | manual receipt | admin |
| 3 | **Crypto** | direct transfer (TRX / TON / USDT / USDC / LTC) | admin |
| 4 | **TetraPay** | API gateway | automatic |
| 5 | **SwapWallet** | API gateway (card + crypto) | automatic |
| 6 | **TronsPay** | API gateway (IRR) | automatic |

Each gateway is enabled independently, takes a custom display name, and can carry an amount range. API gateways offer a "check payment" button *and* a background thread that polls for up to 60 minutes.

---

## ⚙️ Admin panel

| Section | What it does |
|---|---|
| 🧩 **Types & packages** | Categories, packages (volume/duration/price), ordering, descriptions, enable/disable |
| 📚 **Configs** | Single/bulk entry, search, edit, bulk delete and expire, lookup links |
| 👥 **Users** | Browse, adjust balance, safe/unsafe state, restrict, assign a config by hand |
| 👮 **Admins** | Add sub-admins with any subset of the 17 permissions |
| 🤝 **Resellers** | Approve/reject applications, set per-reseller pricing |
| 📣 **Broadcast** | Forward to everyone, or only to customers |
| ⚙️ **Settings** | Gateways, forced channels, free trial, referrals, bot status, log group |
| 💾 **Backup** | Immediate or scheduled backups over Telegram |

### Sub-admin permissions

`full` · `types_packages` · `register_config` · `view_configs` · `manage_configs` · `broadcast_all` · `broadcast_cust` · `view_users` · `agency` · `assign_config` · `manage_balance` · `user_status` · `full_users` · `settings` · `approve_payments` · `approve_renewal` · `manage_panels`

---

## 🚀 Quick install

### Automated (recommended)

```bash
bash <(curl -Ls https://raw.githubusercontent.com/Emadhabibnia1385/ConfigFlow/main/install.sh)
```

The installer sets up `/opt/configflow-<name>`, a virtualenv, a systemd unit, and auto-update. Several bots can live side by side on one server.

> ⚠️ **Auto-update runs every minute** and uses `git reset --hard origin/main`, which discards any local edit. Disable it from the installer menu before patching files by hand.

### Manual

```bash
git clone https://github.com/Emadhabibnia1385/ConfigFlow.git
cd ConfigFlow
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp env.example .env      # fill in BOT_TOKEN and ADMIN_IDS
python3 main.py
```

---

## 🔧 Environment

### `.env` — the bot

| Variable | Description | Example |
|---|---|---|
| `BOT_TOKEN` | Token from [@BotFather](https://t.me/BotFather) | `123456:ABC...` |
| `ADMIN_IDS` | Numeric admin ids, comma separated | `111,222` |
| `DB_NAME` | Database filename | `configflow.db` |

### `config.env` — the Iran worker (optional)

| Variable | Description | Default |
|---|---|---|
| `BOT_API_URL` | API address on the foreign server | — |
| `WORKER_API_KEY` | Shared secret (16+ characters) | — |
| `PANEL_IP` / `PANEL_PORT` | 3x-ui panel address | `127.0.0.1` / `2053` |
| `PANEL_USERNAME` / `PANEL_PASSWORD` | Panel login | — |
| `INBOUND_ID` | Inbound to add clients to | `1` |
| `PROTOCOL` | `vless` / `vmess` / `trojan` | `vless` |
| `POLL_INTERVAL` | Job poll interval in seconds | `10` |

> 🔐 With `BOT_API_URL` on plain `http://`, the shared key and every delivered config link travel **unencrypted**. Use `https://`, or an SSH/WireGuard tunnel between the two servers.

---

## 🧪 3x-ui worker — status: built, not yet wired to sales

The "Iran worker" design exists for the case where the panel sits inside Iran and the bot outside it. The foreign server usually cannot reach in, but the Iranian one can reach out — so the direction is inverted and **the worker polls from inside**.

```
bot ──writes job──▶ xui_jobs table
                        ▲   │
   api.py (:8080)       │   │ GET /jobs/pending
        ▲               │   ▼
        └─── result ─ worker.py (in Iran) ──▶ 3x-ui: create client, build VLESS link
```

Every piece is present — the tables, `api.py`, `worker.py`, and the "3x-ui panels" admin screen. **No purchase path creates a job yet**, so the queue stays empty. All selling currently runs through the stock model.

---

## 📁 Project layout

```
ConfigFlow/
├── main.py              entry point: DB, threads, polling
├── api.py               Flask API for the Iran worker (:8080)
├── worker.py            Iran-side poller (standard library only)
├── install.sh           installer, systemd units, auto-update
│
└── bot/
    ├── config.py        env, the 17 permissions, coins
    ├── bot_instance.py  the bot object, USER_STATE
    ├── db.py            20 tables, all CRUD, migrations
    ├── helpers.py       state, admin auth, number/price formatting
    ├── payments.py      pricing, gateway choice, admin approval
    ├── group_manager.py admin group and log topics
    │
    ├── gateways/
    │   ├── base.py               availability and amount ranges
    │   ├── crypto.py             live coin prices
    │   ├── tetrapay.py           order create/verify
    │   ├── swapwallet_crypto.py  card + crypto invoices
    │   └── tronpays_rial.py      IRR invoices
    │
    ├── ui/
    │   ├── helpers.py       send_or_edit, forced-channel join
    │   ├── keyboards.py     main menu and admin panel
    │   ├── menus.py         profile, my configs, support
    │   └── notifications.py delivery, QR, notices, referrals
    │
    ├── admin/
    │   ├── renderers.py  admin screens
    │   └── backup.py     manual and scheduled backups
    │
    └── handlers/
        ├── start.py      /start and referral links
        ├── callbacks.py  on_callback → _dispatch_callback
        └── messages.py   universal_handler (text input)
```

---

## 🖥️ Running

```bash
python3 main.py     # the bot (foreign server)
python3 worker.py   # the worker (Iranian server)
python3 api.py      # the API standalone — main.py can also start it
```

With systemd after the automated install:

```bash
systemctl status configflow-<name>
journalctl -u configflow-<name> -f
```

---

## 🔌 Dependencies

`pyTelegramBotAPI` · `qrcode` · `pillow` · `python-dotenv` · `flask` · `requests`

Six, deliberately — a self-hosted bot should install cleanly anywhere. `worker.py` needs none of them and runs on the Python standard library alone.

---

## 🤝 Support

- **Telegram:** [@Emad_Habibnia](https://t.me/Emad_Habibnia)
- **GitHub:** [Emadhabibnia1385/ConfigFlow](https://github.com/Emadhabibnia1385/ConfigFlow)

---

## 📄 Licence

Released under the [MIT License](LICENSE) — use, modify, and distribute freely.
