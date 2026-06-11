# Personal Bankin — Finance Dashboard for Home Assistant

**Your personal finance command center — right inside Home Assistant.**

[![Version](https://img.shields.io/badge/version-0.13.1-blue?style=flat-square)](https://github.com/agarridob/ha-personal-bankin/releases)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![HACS](https://img.shields.io/badge/HACS-compatible-orange?style=flat-square)](https://hacs.xyz)
[![CI](https://img.shields.io/github/actions/workflow/status/agarridob/ha-personal-bankin/validate.yml?style=flat-square&label=CI)](https://github.com/agarridob/ha-personal-bankin/actions)
[![HA](https://img.shields.io/badge/Home%20Assistant-2024.1+-41BDF5?style=flat-square&logo=homeassistant&logoColor=white)](https://www.home-assistant.io)

This is a personal fork of [Jerry0022/homeassistant-finance](https://github.com/Jerry0022/homeassistant-finance), adapted and maintained by [@agarridob](https://github.com/agarridob).

## 🔀 What's different in this fork?

- **Country-aware bank list** — the upstream setup wizard hardcoded Germany (`DE`); this fork resolves the country from the Home Assistant core setting (**Settings → System → General → Country**), so Spanish banks (or any other Enable Banking market) show up automatically. Falls back to `DE` when no country is configured.
- **Rebranded** as *Personal Bankin* (HACS listing, integration name, sidebar panel, companion add-on).
- **Documentation updated** to reflect the actual banking provider: the integration uses **Enable Banking**, not GoCardless (the upstream README was out of date — the code migrated to Enable Banking, keeping GoCardless-compatible field names internally).

## 💡 What is this?

Personal Bankin connects your bank accounts to Home Assistant via the [Enable Banking](https://enablebanking.com) PSD2 Open Banking API, giving you a real-time overview of balances, transactions, and household budgets. Track spending across multiple people, auto-categorize transactions, and see where your money goes — all from your HA dashboard, with banking-grade security.

## ✨ Features

- 🏦 **Live Banking Data** — Connect European banks via the Enable Banking PSD2 API (free for personal use)
- 📊 **Auto-Categorization** — Transactions are automatically classified (housing, food, transport, subscriptions, etc.)
- 👥 **Multi-Person Households** — Configurable budget split models for any number of household members
- 🔒 **Banking-Grade Security** — Fernet encryption, per-request JWT signing, session timeouts, full audit trail
- 📱 **Sidebar Panel** — Dedicated finance overview accessible from the HA sidebar
- 🎴 **Lovelace Card** — Compact balance widget for any dashboard
- 🔄 **Companion Add-on** — One-click installation with automatic updates
- 🌍 **Multilingual** — English and German translations included
- 🤖 **HA Automations** — Expose services for balance checks, transaction refresh, and monthly summaries

## 🚀 Getting Started

### Prerequisites

- Home Assistant 2024.1 or newer, **reachable over HTTPS** (Nabu Casa or your own TLS setup) — bank authorization redirects require it
- A free [Enable Banking](https://enablebanking.com) account
- A bank supported by Enable Banking in your country (check the public catalogue, e.g. `https://enablebanking.com/api/aspsps?country=ES`)

### Installation via HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to **Integrations** → **Custom Repositories**
3. Add `https://github.com/agarridob/ha-personal-bankin` as an **Integration**
4. Install **Personal Bankin**
5. Restart Home Assistant

### Installation via Companion Add-on

1. Add this repository URL to your Home Assistant add-on store
2. Install the **Personal Bankin** add-on
3. Start the add-on — it automatically installs the integration
4. Restart Home Assistant when prompted

### Manual Installation

1. Copy `custom_components/finance_dashboard/` to your HA `config/custom_components/` directory
2. Copy `www/community/finance-dashboard/` to your HA `config/www/community/` directory
3. Restart Home Assistant

## 📖 How to Use

### 1. Register an Enable Banking application

1. Sign up at [enablebanking.com](https://enablebanking.com) and open the Control Panel
2. Register a **Production** application (Sandbox only connects to mock banks)
   - Generate the RSA key pair in the browser and **save the private key (`.pem`) somewhere safe** — it is shown only once and must never be committed or shared
   - Add your HA HTTPS origin(s) as allowed redirect URLs, with the path `/api/finance_dashboard/oauth/callback`, e.g. `https://your-ha-domain/api/finance_dashboard/oauth/callback`
3. Activate the application in **restricted mode** by linking your own bank accounts — free for personal use, no contract or KYB required
4. Note your **Application ID**

### 2. Configure the Integration

1. Make sure your country is set in **Settings → System → General** — the bank list follows it
2. Go to **Settings** → **Devices & Services** → **Add Integration**
3. Search for **Personal Bankin**
4. Enter your Enable Banking Application ID and paste the private key PEM
5. Open the sidebar panel **through one of your HTTPS URLs** and follow the wizard to link your bank — you will be redirected to your bank to authorize (consent lasts up to 180 days)

> **Rate limit:** Enable Banking allows 4 API calls per day per linked bank. The integration enforces this quota; if you hit it while testing, wait until the next day.

### 3. View Your Finances

- **Sidebar**: Click the Personal Bankin icon in the HA sidebar for the full overview
- **Lovelace Card**: Add a `custom:finance-dashboard-card` to any dashboard

```yaml
type: custom:finance-dashboard-card
show_transactions: true
max_transactions: 5
```

### 4. Use in Automations

```yaml
# Refresh transactions daily
automation:
  - alias: "Daily Finance Refresh"
    trigger:
      - platform: time
        at: "08:00:00"
    action:
      - service: finance_dashboard.refresh_transactions
```

## 🏗 Architecture

```
┌─────────────────────────────────────────────────┐
│                 Home Assistant                   │
│                                                  │
│  ┌──────────────┐  ┌─────────────────────────┐  │
│  │  Sidebar      │  │  Lovelace Card          │  │
│  │  Panel (JS)   │  │  (JS Web Component)     │  │
│  └──────┬───────┘  └──────────┬──────────────┘  │
│         │     HTTP API         │                 │
│  ┌──────┴──────────────────────┴──────────────┐  │
│  │         Personal Bankin Integration         │  │
│  │  ┌──────────┐ ┌────────────┐ ┌──────────┐  │  │
│  │  │ Manager  │ │ Categorizer│ │ Cred Mgr │  │  │
│  │  └────┬─────┘ └────────────┘ └──┬───────┘  │  │
│  │       │                          │          │  │
│  │  ┌────┴──────────────────────────┴───────┐  │  │
│  │  │      Enable Banking API Client        │  │  │
│  │  └────────────────┬──────────────────────┘  │  │
│  └───────────────────┼─────────────────────────┘  │
│                      │                            │
│  ┌───────────────────┼─────────────────────────┐  │
│  │  Companion Add-on │ (Payload Installer)     │  │
│  └───────────────────┘                         │  │
└──────────────────────┼─────────────────────────┘
                       │ HTTPS (signed JWT per request)
              ┌────────┴────────┐
              │ Enable Banking  │
              │  (Open Banking) │
              └────────┬────────┘
                       │ PSD2
              ┌────────┴────────┐
              │   Your Bank     │
              └─────────────────┘
```

The integration's internal domain remains `finance_dashboard` (storage keys, API routes and entity IDs are unchanged from upstream).

## 🔒 Security

Personal Bankin follows banking-grade security practices:

| Layer | Protection |
|-------|-----------|
| **Credential Storage** | Fernet symmetric encryption (AES-128-CBC + HMAC) in HA `.storage/` |
| **API Authentication** | JWT signed per request with your RSA private key (RS256); no long-lived tokens |
| **Token Management** | Auto-rotation before expiry, forced re-auth after 90 days |
| **Session Security** | 30-minute inactivity timeout |
| **Data Display** | IBANs masked to last 4 digits in all API responses |
| **Audit Trail** | Every credential operation logged (event type + timestamp only) |
| **API Security** | All endpoints require HA Bearer token authentication |
| **Git Safety** | `.gitignore` blocks all runtime data, credentials, and tokens |
| **Network** | HTTPS-only communication with Enable Banking; no telemetry |

**No financial data is ever stored in git, logs, or configuration files.**

## 🤝 Contributing

This is a personal fork — generic improvements are best contributed upstream to [Jerry0022/homeassistant-finance](https://github.com/Jerry0022/homeassistant-finance). Please note the strict security requirements — any PR that could leak financial data will be rejected.

1. Fork the repository
2. Create a feature branch (`feat/42-your-feature`)
3. Run validation: `python scripts/bump_versions.py --check`
4. Submit a Pull Request

## 📄 License

[MIT](LICENSE) — Copyright (c) 2026 Jerry0022. Fork modifications by [@agarridob](https://github.com/agarridob).
