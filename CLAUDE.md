<!-- Uses dotclaude-dev-ops plugin + personal ~/.claude/CLAUDE.md -->

# Personal Bankin — Home Assistant Integration

## Project Overview

A secure Home Assistant add-on and integration for personal finance management. Pulls live banking data via the Enable Banking PSD2 Open Banking API (JWT-signed), auto-categorizes transactions, and provides household budget tracking with configurable multi-person split models.

This is Alberto's personal fork (agarridob/ha-personal-bankin) of Jerry0022/homeassistant-finance, rebranded "Personal Bankin" and tuned for Spanish banks (Caja Rural de Zamora, BBVA). The internal domain stays `finance_dashboard`.

**Hard rule — cache vs. live fetch**: Cache reads (HTTP endpoints, sensor attributes, coordinator state) are unbounded. Live Enable-Banking calls are ONLY allowed from explicit user-triggered paths (refresh button, service call, setup bootstrap). Enable Banking enforces a 4/day ASPSP rate limit, so background polling is forbidden.

## Working Agreements (Alberto's standing orders)

1. **Language split**: everything that lands in the repo — commit messages, PR titles/bodies, code comments, docs — is written in **English**. Conversation with Alberto is in Spanish.
2. **Branch + PR workflow**: never commit directly to `main`. Each feature/fix goes on its own branch (`feat/...`, `fix/...`, `chore/...`) with a PR to `main`. Alberto approves merges (he may delegate the merge explicitly).
3. **Conventional commits**: `feat(scope):`, `fix(scope):`, `chore(scope):` etc. — these prefixes drive the changelog tooling.
4. **Release flow** (after merging to `main`): add a BUILDLOG.md entry → `python scripts/sync_changelog.py --version X.Y.Z` → tag `vX.Y.Z` on the merge commit → push the tag. The tag-triggered workflow (`.github/workflows/release.yml`) creates the GitHub Release; if Actions are disabled, `gh release create vX.Y.Z` with the CHANGELOG section as notes. HACS must always offer numbered versions, never commit hashes.
5. **Version bumps**: `python scripts/bump_versions.py --part patch|minor|major` on the feature branch (keeps manifest.json, config.yaml and const.py aligned). Patch for fixes, minor for features.
6. **Payload sync is mandatory**: after touching anything under `custom_components/`, run `python scripts/sync_addon_payload.py` — CI fails otherwise. Never edit `finance_dashboard_companion/payload/` by hand.
7. **Local tooling**: the system `python3` is 3.7 — always use `.venv/bin/python` (3.12) for tests and scripts. Tests: `.venv/bin/python -m pytest tests/ -q`. Lint: `.venv/bin/ruff check custom_components/ tests/` + `ruff format`.
8. **i18n policy**: English is the base language; Spanish (`es`) is the supported translation. German was removed — do not reintroduce it. Every user-visible frontend string goes through `tSync()`/locale files (`frontend/locales/en.json` + `es.json`); HA config-flow strings live in `strings.json` + `translations/en.json` + `translations/es.json` (keep all in sync). No hardcoded UI strings in components or Python.
9. **Branding**: all icons/logos derive from `custom_components/finance_dashboard/brand/logo-source.png` via `scripts/generate_branding_assets.py` — never hand-edit the generated PNGs.
10. **Rate-limit discipline when testing**: a live `refresh_transactions` costs 1 of 4 daily Enable Banking calls per account. Prefer cache reads (`/refresh_status`, `/balances`, sensors) for diagnosis; ask before burning quota.
11. **Frontend gotcha**: panel components load as ES modules with isolated scopes — no implicit shared globals between files (use `window._fd` or per-file constants). Bump the version (cache-busting `?v=`) whenever frontend files change.

## Architecture

```
homeassistant-finance/
├── custom_components/finance_dashboard/   # HA Integration
│   ├── __init__.py              # Setup, services, HTTP endpoints, restart polling
│   ├── manifest.json            # Integration metadata + dependencies
│   ├── config_flow.py           # Config + Options + Reconfigure flows
│   ├── const.py                 # All constants, categories, service names
│   ├── manager/                 # Core orchestrator (package)
│   │   ├── __init__.py          # FinanceDashboardManager + cache reads + household
│   │   ├── _refresh.py          # RefreshMixin — all live-fetch + OAuth + rate-limit
│   │   └── _persistence.py      # PersistenceMixin — storage read/write
│   ├── api/                     # HTTP endpoints (package)
│   │   ├── __init__.py          # View registration
│   │   ├── _helpers.py          # Manager lookup, OAuth state, setup-client factory
│   │   ├── data.py              # /balances, /transactions, /summary
│   │   ├── demo.py              # Demo mode toggle
│   │   ├── refresh.py           # /refresh, /refresh_status
│   │   ├── setup.py             # Setup wizard + OAuth callback
│   │   └── static.py            # Static file serving
│   ├── credential_manager.py    # Fernet encryption, JWT signing key, audit log
│   ├── enablebanking_client.py  # Enable Banking API client (PSD2, JWT RS256)
│   ├── coordinator.py           # DataUpdateCoordinator (cache-only reads)
│   ├── categorizer.py           # Rule-based transaction auto-categorization
│   ├── panel.py                 # Sidebar panel registration
│   ├── repairs.py               # Re-export fix-flow + issue-creation context docs
│   ├── services.yaml            # Service definitions for HA
│   ├── strings.json             # UI strings (EN default)
│   ├── frontend/                # Web components (sidebar panel)
│   └── translations/            # i18n (en.json, es.json)
├── finance_dashboard_companion/           # HA Companion Add-on
│   ├── config.yaml              # Add-on metadata (version, arch)
│   ├── Dockerfile               # Alpine-based container
│   ├── run.sh                   # Smart payload installer (version-aware)
│   └── payload/                 # Bundled integration + Lovelace assets
├── www/community/finance-dashboard/       # Lovelace card (HACS install)
├── scripts/                               # Dev tooling
│   ├── bump_versions.py         # Sync versions across manifest/addon/const
│   ├── sync_addon_payload.py    # Copy integration → add-on payload
│   └── sync_changelog.py       # Sync BUILDLOG → CHANGELOG (both root + addon)
└── .github/workflows/validate.yml         # CI: syntax + version + payload validation
```

## Security Model

**CRITICAL — Banking-Grade Security Requirements:**

1. **No financial data in git**: Zero runtime data (balances, transactions, account numbers, tokens) may ever be committed. The `.gitignore` enforces this.
2. **Encrypted storage**: All credentials use Fernet symmetric encryption (AES-128-CBC + HMAC) on top of HA's `.storage/` directory.
3. **JWT auth**: Short-lived (60s) RS256-signed JWTs per request — no long-lived bearer tokens stored. RSA private key held only in memory. PSU session validity capped at 180 days (Enable Banking / EU RTS 2022/2360), forced re-auth after 90 days by policy.
4. **Session timeouts**: Credential access times out after 30 minutes of inactivity.
5. **Audit trail**: Every credential operation is logged (timestamp + event type only, never values).
6. **IBAN masking**: API responses truncate IBANs to last 4 digits for frontend display.
7. **Header security**: API endpoints require HA Bearer token authentication.
8. **No external calls**: Only the Enable Banking API is contacted. No telemetry, no analytics.
9. **Rate-limit discipline**: Live fetches only on explicit user action. Cache-read endpoints (`/balances`, `/summary`, `/refresh_status`) never hit the bank.

**Before every commit, verify:**
- `git diff --cached` contains zero financial data (account numbers, balances, tokens)
- No `.storage/` files are staged
- No `credentials.json` or `tokens.json` files are staged

## Tech Stack

- **Language**: Python 3.12+ (integration), JavaScript (frontend)
- **Banking API**: Enable Banking (PSD2, JWT-signed, RS256). 4/day/ASPSP rate limit.
- **Encryption**: `cryptography` library (Fernet for storage, RSA for JWT signing)
- **Frontend**: Vanilla Web Components (Custom Elements API)
- **HA APIs**: Config Entries, Services, HTTP Views, Repairs, Frontend Panel
- **CI**: GitHub Actions (Python/JS syntax, version alignment, payload sync)

## Version Management

Three files must always have aligned versions:
1. `custom_components/finance_dashboard/manifest.json` → `version` field
2. `finance_dashboard_companion/config.yaml` → `version` field
3. `custom_components/finance_dashboard/const.py` → `VERSION` constant

Use `python scripts/bump_versions.py --part [patch|minor|major]` to bump all three atomically. The script also auto-syncs the add-on payload.

### CHANGELOG Sync (mandatory after every BUILDLOG entry)

After writing a BUILDLOG entry, run `python scripts/sync_changelog.py` to propagate the entry to both `CHANGELOG.md` (keep-a-changelog format) and `finance_dashboard_companion/CHANGELOG.md` (simplified). The script parses conventional commit prefixes (`feat()`, `fix()`, `refactor()`) and groups changes by Added/Changed/Fixed. Use `--check` to verify sync status.

## Key Patterns (from Golden Sample)

### Companion Add-on
The add-on is a thin installer — it copies the integration code into HA's `custom_components/` directory. The `run.sh` script:
- Compares bundled vs installed version
- Only copies if versions differ
- Writes restart marker for integration to detect
- Falls back to persistent notification via HA Supervisor API

### Config Flow
Three-step flow: `user` (Enable Banking application_id + RSA private key) → `link_bank` (ASPSP authorization via PSU redirect) → `options` (settings). Real-time validation via Enable Banking API call during setup.

### Service API
8 Services: `refresh_accounts`, `refresh_transactions` (both return refresh-stats dict via `SupportsResponse.OPTIONAL`), `get_balance`, `get_monthly_summary`, `categorize_transactions`, `set_budget_limit`, `export_csv`, `toggle_demo`. `refresh_transactions` is the only live-fetch entry point and always updates balances + transactions + recurring in one atomic round.

### Refresh Flow (user-triggered)
1. Frontend refresh button → `POST /api/finance_dashboard/refresh`
2. Endpoint calls `manager.async_refresh_transactions()` (async-lock-guarded)
3. Manager hits Enable Banking for transactions + balances in one pass
4. On HTTP 429 → `_rate_limited_until = midnight`, persisted across HA restart
5. Stats (`outcome`, `accounts`, `transactions`, `new`, `duration_ms`, `errors`) written to cache
6. Coordinator pushes updated state to sensors
7. Endpoint returns `{ok, status: {stats, rate_limited_until, cache_age_seconds, ...}}`
8. Frontend shows toast: "5 Konten, 243 Transaktionen, 2 neu in 3.1s" or the rate-limit message

Cache-read endpoints (`/balances`, `/summary`, `/refresh_status`, `/transactions`) are unbounded and never hit the bank.

### Entity Architecture
- **Sensor** (per account): `sensor.fd_{bank}_{account}` — balance with bank logo, IBAN masked
- **Sensor** (aggregate, optional off): `sensor.fd_total_balance` — sum of all accounts
- **Sensor** (monthly): `sensor.fd_monthly_summary` — income, expenses, categories
- **Sensor** (per person): `sensor.fd_budget_{person}` — Spielgeld after split
- **Number** (per category): `number.fd_budget_{category}` — budget limit, dashboard-steuerbar
- **Select**: `select.fd_split_model` — equal / proportional / custom
- **Events**: `fd_transaction_new`, `fd_balance_changed`, `fd_budget_exceeded`, `fd_recurring_detected`

### Privacy-First Display
- Default: only aggregated data visible (categories, sums, trends)
- Individual transactions: **HA-Admin only** — normal users see only pre-built summaries
- No financial data in URL parameters, logs, or git

### Month Cycle Logic
- Configurable per person: **calendar month** OR **salary-based cycle**
- Recurring transactions assigned to their **logical month** (bank day correction: rent on Feb 28 due to weekend → counts as March)
- Salary tolerance window: ±5 days for income detection

### Bonus Detection
- Income ≥15% above 3-month average → HA notification for confirmation
- Threshold configurable in settings
- Confirmed bonus → goes to Spielgeld, NOT into monthly balance/split calculation

### Split Model
Three modes for cost distribution:
- **Equal**: 50/50 (2P), 33/33/33 (3P), etc.
- **Proportional**: based on net income ratio
- **Custom**: user sets percentages manually per person

Additional:
- **Remainder split**: choosable — "no split" (each keeps their rest) OR "equal distribution"
- **Category-level override**: optional — global split default, overridable per cost category

## Commands

```bash
# Version management
python scripts/bump_versions.py --check        # Verify alignment
python scripts/bump_versions.py --part patch    # Bump version

# Payload sync
python scripts/sync_addon_payload.py            # Sync files
python scripts/sync_addon_payload.py --check    # Verify sync

# CHANGELOG sync (BUILDLOG → CHANGELOG + addon CHANGELOG)
python scripts/sync_changelog.py                # Sync current version
python scripts/sync_changelog.py --check        # Verify CHANGELOG is up-to-date
python scripts/sync_changelog.py --version X.Y.Z  # Sync specific version

# Validation (same as CI)
python -m py_compile custom_components/finance_dashboard/__init__.py
node --check custom_components/finance_dashboard/frontend/finance-dashboard-panel.js

# Deploy to local HA for testing (no release needed)
scp -r custom_components/finance_dashboard/ ha-remote:/config/custom_components/finance_dashboard/
# Then reload the integration in HA: Settings → Integrations → Personal Bankin → ⋮ → Reload
```

## Local HA Instance

- **SSH alias**: `ha-remote` → `root@192.168.0.103:22222` (configured in `~/.ssh/config`)
- **Integration path on HA**: `/config/custom_components/finance_dashboard/`
- **SSH add-on**: Terminal & SSH, port 22222, key-based auth (no password)
- **`rsync` not available** in the HA container — use `scp -r` instead
- After deploying: reload via HA UI, no full restart needed for Python/JS changes

## Development Phases

### Phase 1 — Scaffold + MVP (completed v0.12.1)
- [x] Repository structure mirroring YouTube Music Connector golden sample
- [x] Enable Banking API client (replaced GoCardless skeleton)
- [x] Credential manager with encryption + audit
- [x] Transaction categorizer (rule-based, 9 categories from household sheet)
- [x] Companion add-on with smart installer
- [x] Sidebar panel + Lovelace card
- [x] CI/CD pipeline
- [x] Branding (dual-tone coin icon)
- [x] Design sprint (requirements, architecture, UI mockups)
- [x] End-to-end Enable Banking OAuth flow (DE banks only)
- [x] Account balance sensors (1 per account, bank logo, optional aggregate)
- [x] Monthly summary sensor
- [x] Privacy-first API responses (IBAN masking, admin-only details)

> Next version: **0.13.0** — audit-synthesis wave A-F (backend refactor + Polish)

### Phase 2 — Household Budget
- [x] N-person model with configurable split (equal/proportional/custom)
- [x] Personal vs. shared account assignment (at link + in options)
- [x] Auto-detection of recurring transactions
- [ ] Income recognition with ±5d tolerance window
- [ ] Bonus detection (≥15%, notification + confirmation → Spielgeld)
- [ ] Month cycle logic (calendar vs. salary-based, per person)
- [ ] Logical month assignment for recurring costs (bank day correction)
- [x] Remainder split (no split / equal distribution)
- [ ] Category-level split override (optional)
- [x] Budget limits as Number entities (per category)
- [x] Split model as Select entity (dashboard-steuerbar)
- [ ] Budget Config Lovelace Card (slider, dropdown, live preview)
- [x] 4 automation events (transaction_new, balance_changed, budget_exceeded, recurring_detected)
- [ ] 6-month trend chart

### Phase 3 — Analytics + Polish (frozen — Phase 2 freeze per audit DN1=einfrieren)
- [ ] Benchmark auto-crawl (Destatis, Bundesbank) with source attribution (text, no gauges)
- [ ] Drag & drop transaction categorization (system learns)
- [ ] Spending trend analysis
- [ ] CSV export service (local download, no git)
- [ ] set_budget_limit service + automation trigger

## Labels

| Type | Prefix |
|------|--------|
| `type:feature` | `[FEATURE]` |
| `type:bug` | `[BUG]` |
| `type:security` | `[SECURITY]` |
| `type:refactor` | `[REFACTOR]` |

| Role | Scope |
|------|-------|
| `role:core` | Manager, API client, credential manager |
| `role:frontend` | Panel, Lovelace cards, web components |
| `role:security` | Encryption, audit, token management |
| `role:addon` | Companion add-on, Dockerfile, run.sh |

| Module | Scope |
|--------|-------|
| `module:enablebanking` | Banking API integration |
| `module:categorizer` | Transaction categorization |
| `module:household` | Multi-person budget model |
| `module:frontend` | UI components |
| `module:addon` | Companion add-on |
