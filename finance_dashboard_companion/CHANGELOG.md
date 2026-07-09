# Changelog



























## 0.24.0
- Track the timestamp of the last *successful* transaction fetch per account (_last_success_by_account). A live fetch that raises (stale session, 422, rate-limit) skips the update and keeps the previous timestamp, so an account whose bank is failing silently no longer looks refreshed. Persisted in the transaction cache and surfaced via get_last_success_dates()
- Migrate pre-feature caches by seeding the per-account success map from the global last_refresh, so existing installs show the last known refresh instead of a misleading "never" until the next refresh diverges the values
- Track the last refresh error per account (_last_error_by_account) with a classified type — session_expired, auth_error or error — set on failure and cleared on the next success; persisted and exposed via get_account_errors()
- /setup/status now returns last_success_refresh and refresh_error per account alongside oldest_transaction
- The "Edit accounts" cards show "Last successful refresh: <datetime>" under "Oldest transaction" (red/bold when older than 48h or never) plus an explicit "⚠ Session expired — reconnect this bank" line when the last refresh failed, so a silently-failing bank like BBVA is obvious and actionable
- Preserve transaction history across a bank re-link: match old→new accounts by their stable IBAN and migrate the cached history onto the fresh session-scoped ids before the stale-bucket prune runs, instead of losing everything older than 90 days
- Add wizard.step.3.last_success[_never] and wizard.step.3.refresh_error[_session_expired] to en/es locale files
- Test(manager): add coverage for get_last_success_dates scoping, the global-refresh backfill migration, error classification, get_account_errors scoping, and account-id remap on re-link

## 0.23.2
- The /transactions endpoint served only the first 100 cached rows, so the panel's transaction log (and its date/category/search filters, which run client-side) could never reach older movements even though up to 24 months are cached. It now serves the full cached history by default (bounded by HISTORY_RETENTION_MONTHS), with an optional ?limit= override
- Get_cached_transactions(limit=None) now returns the whole cache (a copy) instead of defaulting to 100
- Cap the expanded transaction log at EXPANDED_MAX (500) rendered rows with a "showing first N of M — narrow with filters" hint, so loading the full 24-month history never janks the panel; filters still apply before the cap so any specific date range surfaces matches across all history
- Add transactions.capped_hint to en/es locale files
- Test(manager): add tests/test_cached_transactions_limit.py covering full-cache return, explicit limit, and copy-not-reference semantics

## 0.23.1
- Persist transactions, balances and refresh stats in a single write at the END of the refresh round — previously _persist_transactions ran before the balance leg and stats build, so freshly-fetched balances/stats were saved one round late (or never, freezing the displayed balance). Root cause of accounts showing a stale balance despite daily auto-refresh
- The 422 WRONG_TRANSACTIONS_PERIOD fallback now retries with progressively smaller windows (TX_FALLBACK_WINDOWS = [30, 7]) instead of re-requesting the identical 90-day window that was just rejected; an account is only marked failed once every window is rejected
- Prune cache buckets (transactions + balances) for accounts that are no longer linked — residue from re-linking a bank under a new Enable Banking session that caused duplicate transactions on every load and stale balance entries
- Extract _fetch_account_txns_with_fallback and _ingest_account_txns helpers, removing the duplicated tag/categorize/merge block between the primary fetch and the fallback path
- Test(manager): add tests/test_refresh_fixes.py covering stale-account pruning, the descending-window 422 fallback, and ingest tagging + historical merge

## 0.23.0
- Show balance per account — the total-balance KPI card is now clickable and expands an accordion listing each account (bank logo, custom name, masked IBAN ****1234, balance) below the stats row; collapsed by default, keyboard-accessible (role=button, Enter/Space, aria-expanded)
- Expose the account bank logo to the panel by copying entity_picture into data.accounts[].logo in fd-data-provider (falls back to the bank/account initial when no logo is set)
- Add stats.balance.toggle_accounts label to en/es locale files

## 0.22.0
- Add opt-in once-a-day scheduled refresh — new options "auto_refresh_enabled" and "auto_refresh_hour" (0–23) arm a single live refresh per day at a user-chosen hour via async_track_time_change; disabled by default
- The scheduled callback reuses the manual-refresh path (async_refresh_transactions + coordinator.async_refresh) and skips when demo mode is active or the daily rate limit is exhausted, so Enable Banking's 4/day per-ASPSP quota is never exceeded by the scheduler
- Reload the config entry on options change so the scheduler is re-armed with the new hour/enabled flag; the time-change unsub is registered via entry.async_on_unload for automatic cleanup
- Remove the unused "refresh_interval_minutes" option (vestigial from the golden sample; it implied non-existent interval polling)
- Add auto_refresh_enabled / auto_refresh_hour labels and drop refresh_interval_minutes from strings.json, translations/en.json, translations/es.json
- Test(core): add tests/test_auto_refresh.py covering enabled/disabled arming, configured hour, and rate-limit / demo-mode skip gates

## 0.21.1
- Fall back to the 90-day window (DEFAULT_REFRESH_DAYS) when a bank rejects the 365-day backfill with HTTP 422 WRONG_TRANSACTIONS_PERIOD, so recent transactions are still fetched instead of losing the whole account
- Add TransactionPeriodExceeded exception (distinct from the 429 rate-limit path) raised on 422 WRONG_TRANSACTIONS_PERIOD
- Add get_oldest_transaction_dates() helper returning the oldest booked date per account
- Surface the period fallback in the setup wizard messaging

## 0.20.0
- Auto-select 365-day window on first refresh (INITIAL_SYNC_DAYS); subsequent refreshes use DEFAULT_REFRESH_DAYS (90). Flag initial_sync_complete persisted in transaction store so the backfill survives HA restarts and is idempotent
- Add fetch_full_history service (admin-only) to reset the flag and re-fetch 365 days on demand — useful after adding a second bank account
- Add initial_sync_pending HA Repair issue shown on startup when backfill not yet done; fix flow triggers fetch_full_history service; issue auto-dismissed after first successful 365-day refresh
- Add initial_sync_pending issue strings to strings.json, translations/en.json, translations/es.json
- Update wizard step 4 body to inform user that 12 months of history are being fetched

## 0.19.1
- Hide demo button in fd-header when demo mode is inactive; button only shows when demo is running so users can stop it
- Rename "Actualizar" to "Refrescar" in Spanish header button and empty-state hint
- Change timestamp label from "Última:" (es) / "Last:" (en) to "Refrescado:" / "Refreshed:" in both locales

## 0.19.0
- Add "Edit accounts" button to fd-header — visible only when at least one account is linked; dispatches fd-open-edit-wizard event
- Add edit mode to fd-setup-wizard — opens at step 3 with existing accounts loaded from setup/status; calls POST setup/update_accounts on save; dispatches fd-accounts-updated on success
- Fd-accounts-updated triggers data rebuild in panel so display names refresh immediately after saving
- Add wizard.edit_title, wizard.step.3.edit_subtitle, wizard.step.3.save, wizard.step.4.edit_title, wizard.step.4.edit_body, header.edit_accounts, header.edit_accounts_title to en.json and es.json

## 0.18.0
- Add 7-filter bar to fd-transactions-log — direction pills (all/income/expense), category dropdown, account dropdown (hidden when single account), text search on creditor/description, amount range (> € / < €), date range (from/to), pending-only toggle
- Filter state preserved across list updates; count badge shows filtered/total when any filter is active; "Clear filters" button appears automatically
- Add transactions.filter.* keys to en.json and es.json

## 0.17.0
- Accumulate transaction history — each refresh merges new transactions into storage instead of overwriting; historical booked txns outside the 90-day fetch window are preserved up to 24 months (HISTORY_RETENTION_MONTHS)
- /api/finance_dashboard/summary now accepts ?month=M&year=Y query params to serve any historical period from the accumulated cache without a live bank API call
- Add ‹ › month navigation arrows to fd-header; next-month button disabled when at current month; dispatches fd-month-changed event
- Fd-data-provider.setMonth() fetches historical summaries from API and dispatches fd-data-updated so all dashboard components reflect the selected period

## 0.16.1
- Switch fd-categorize.js from tSync() to await t() — prevents instruction and admin-only strings rendering as raw keys on first load
- Cache-bust locale fetch in fd-shared-styles.js using ?v= from module URL so updated locale files are picked up after version bumps
- Chore(docs): document local HA instance SSH alias and deploy command in CLAUDE.md

## 0.16.0
- Add pets category — veterinario, kiwoko, tiendanimal, zooplus, royal canin, etc.
- Add clothing category — zara, h&m, mango, primark, bershka, shein, zapatos, etc.
- Add charity category — donacion, unicef, cruz roja, caritas, greenpeace, etc.
- Add cards category — liquidacion/cargo/cuota tarjeta for credit card bill payments
- Add cat.pets, cat.clothing, cat.charity, cat.cards to en.json and es.json
- Add pets, clothing, charity, cards to categorize drag&drop card and CAT_COLORS

## 0.15.5
- Remove manual __init__ from OptionsFlow — HA 2024.4+ sets config_entry as a read-only property, causing 500 on options form open
- Add missing demo_mode key to strings.json, en.json and es.json so options form renders all fields

## 0.15.4
- Replace hardcoded German instruction text in categorize card with tSync() calls
- Add categorize.instructions and categorize.admin_only keys to es.json and en.json
- Cat.groceries, cat.dining, cat.health, cat.leisure were missing from the locale served to tSync — locale files now include all four keys so CAT_LABELS resolves them correctly

## 0.15.3
- Split food into groceries (supermarkets) and dining (restaurants + delivery)
- Add health category — farmacia, clinica, dentista, fisio, optica, psicolog, etc.
- Add leisure category — cine, teatro, gym, gimnasio, decathlon, ticketmaster, etc.
- Keep food as legacy alias in CAT_COLORS and CAT_LABELS so cached transactions still render
- Update drag&drop card category list to include groceries, dining, health, leisure
- Add cat.groceries, cat.dining, cat.health, cat.leisure to es.json and en.json

## 0.15.2
- Add configurable month cycle start day — options field `month_start_day` (1–28, default 1) lets users anchor their budget month to their payday instead of the calendar 1st
- `async_get_monthly_summary` uses `get_month_range()` for cycle-aware date filtering; response includes `cycle_start` / `cycle_end` ISO dates
- `_compute_household` propagates global `month_start_day` to each `HouseholdMember` (salary_day + month_cycle fields)
- Translated options label in strings.json, en.json and es.json

## 0.15.1
- Parse the real Enable Banking /transactions response — flat transaction list with per-entry status (BOOK/PEND) instead of the GoCardless {booked, pending} shape the code assumed ('list' object has no attribute 'get' crash, transactions never loaded)
- Apply credit_debit_indicator to amounts — Enable Banking sends unsigned amounts, so debits are now negative as downstream consumers expect
- Join list-typed remittance_information into a single string
- Follow continuation_key pagination on /transactions (capped at 20 pages) so long date windows return all transactions
- Test: +6 unit tests pinning the Enable Banking response parsing (203 total)

## 0.15.0
- Derive all branding assets from the Personal Bankin logo (brand/logo-source.png) — transparent light/dark icon and logo variants, companion add-on icons, frontend copy
- Panel onboarding screen shows the Personal Bankin logo instead of the bank emoji
- Static view serves correct content types for png/svg/json (previously everything as JavaScript)
- Generate_branding_assets.py derives assets from the source image instead of rendering the smiley-coin from scratch

## 0.14.1
- Register a coroutine listener for the initial cache load — recent HA cores reject creating tasks from a lambda off the event loop, which aborted the load and left the panel empty after every restart

## 0.14.0
- Persist user-added categorization keywords in .storage/finance_dashboard_custom_rules, loaded on startup and merged on top of the built-in rules
- New add_categorization_rule / remove_categorization_rule services (category + keyword, response returns current custom rules) — adding or removing rebuilds the categorizer and re-categorizes the cache immediately
- The drag&drop categorize card persists assignments via add_categorization_rule (previously session-only)
- Test: +8 unit tests for custom rules persistence (197 total)

## 0.13.4
- Spanish default keyword rules (Mercadona, alquiler, Iberdrola, nómina...) replacing the German set, keeping international merchants; accented keywords listed in both forms
- Refund keywords moved to Spanish banking terms (devolución, reembolso, retrocesión) plus refund/reversal/chargeback
- Demo mode generates Spanish accounts (Caja Rural de Zamora, BBVA) and merchants
- Test: categorizer and transfer-detector suites reparametrized with Spanish examples

## 0.13.3
- Full Spanish locale for the panel (locales/es.json) and the HA config flow (translations/es.json); supported languages now en/es
- All hardcoded German strings in panel components routed through the tSync() locale system (stat cards, donut chart, person cards, category section, status chip, categorize and budget cards); category labels resolve via cat.* locale keys
- German locale files removed (English base, Spanish UI)
- Panel header title renamed to Personal Bankin

## 0.13.2
- Declare DOMAIN in fd-setup-wizard module scope — components load as ES modules with isolated scopes, so the wizard crashed with a swallowed ReferenceError before ever calling the API (bank list permanently stuck on loading)
- Wizard catch handlers surface real error messages (e.error/e.message + console.error) instead of unrelated i18n loading strings; loading reset moved into finally
- Component script URLs carry ?v= cache busting (static view serves them with 1h Cache-Control)
- Setup help shows the real HA URL via helpers.network.get_url instead of None when network settings are Automatic
- Hardcoded German backend strings translated to English (setup notification, wizard errors, rate-limit messages, OAuth callback page)
- ASPSP country resolved from the HA core country setting instead of hardcoded DE

## 0.13.1
- Global :focus-visible outline rings + prefers-reduced-motion override in SHARED_CSS
- Aria-expanded on transactions-log show-more toggle
- New design tokens in SHARED_CSS (--r-sm/md, --sh-sm/md/lg, --fs-sm/md/lg/xl, --lh-tight/normal, --sp-xs/sm/md/lg/xl) for upcoming token-migration polish
- RateLimitExceeded on /setup/complete surfaces as error_type=rate_limited in HTTP 200 body (matches setup-wizard contract; was previously masked as generic failure)
- Categorizer None-guard with WARNING log — refresh races ahead of init fall back to category="other" instead of crashing
- Cleanup of old CSV exports swallows OSError/ValueError/OverflowError and logs cause (no more silent bare-except)
- Remove unused TRANSACTION_REFRESH_STALENESS constant + timedelta import
- Test: +20 unit tests for events.py (11) + export.py (9 incl. OSError/OverflowError monkeypatch paths) — total 165 → 185, all green
- Chore(lint): ruff sweep across tests/ — 44 fixes (import order, unused imports, datetime.UTC migration)
- Chore(payload): re-sync addon mirror (incl. pre-existing UTC drift from v0.13.0)

## 0.13.0
- MultiFernet credential storage with key rotation + v1→v2 migration (S2)
- Timing-safe OAuth state validation with one-time-use, 10min TTL, 32-entry cap, cross-store fallback (S4, F1, F3, F5)
- Unified setup-wizard rate-limit gate via async_make_setup_call + persistent fresh-setup gate (S3, F2, F4)
- IBAN/account-id/EUR-amount log sanitizer; raw API bodies no longer hit ERROR-level logs (S1)
- Pre-commit secret-scan hook (.pre-commit-config.yaml + scripts/check_no_banking_data.py) (R11)
- PyJWT[crypto] migration with iss=application_id, aud=api.tilisy.com, per-request jti (A4)
- Shared aiohttp ClientSession via async_get_clientsession (A5)
- Retry-After header honored on 429 + PSU headers for online-mode (D5, D6)
- /refresh_status exposes rate_limit_per_day + cache_is_stale + cache_age_seconds (D7, D9)
- /refresh and toggle_demo now require admin (R9, R14)
- Partial-refresh per-account cache prevents data loss on partial bank failure (R5, F10)
- Corrupt .storage recovery via try/except + repair-issue (R8)
- Static file serving non-blocking via async_add_executor_job + LRU cache (R12)
- Repair-issue payloads scrubbed of exception strings (R10)
- _reconstruct_pem PKCS1/PKCS8 detection corrected (C9)
- Split api.py (1258 LOC) into api/ package (setup, refresh, data, static, demo, _helpers) (A1)
- Split manager.py (1151 LOC) into mixin modules (RefreshMixin, PersistenceMixin) (A2)
- Persistent component tree replaces full-rebuild on every data update (A3)
- SHARED_CSS adoption + CAT_COLORS/LABELS consolidation in fd-shared-styles (F2, F3)
- All hardcoded color literals replaced with CSS tokens (F4)
- Unified disconnectedCallback for memory cleanup (F5)
- Shared escHtml helper (F8)
- Setup-wizard modal with role/aria-modal/focus-trap/ESC (U1)
- Institution list with full keyboard navigation (role/listbox/option) (U2)
- Donut chart aria-label + visually-hidden table fallback (U3)
- Toast aria-live based on severity (assertive for warn/error) (U4)
- Cost-distribution role/group + per-segment aria-label (U5)
- I18n with locale JSON files + hass.language detection + tSync helper (U6, G1-G4)
- Skeleton/loading states across all card components (U8)
- + Bank entry-point opens wizard from header (U10)
- Countdown for setup-wizard auth-polling step (D8)
- Persistent notification after config_flow completion (U11)
- Responsive breakpoint at 980px for category section (U9)
- Month label as static span (U7)
- Chore: remove deprecated GoCardless client (F1)
- Manager.async_set_accounts encapsulation (F6)
- Perf(security): reuse audit-log Store instance (F7)
- Chore(manifest): iot_class cloud_polling → cloud_push (D2)
- Docs: align repairs.py role + sync services.yaml (D3, D4)
- Docs: precise update_interval docstring on coordinator (D10)
- Mark auth+storage repairs as is_persistent (D11)
- Fix: dt_util.now() instead of datetime.now() throughout (D12)
- Test: scaffold tests/ + pyproject.toml + requirements_test.txt (T1, T6)
- Test: cache-vs-live-boundary contract test as guardian (T2)
- Test: JWT/Fernet edge-case coverage (T3, 21 tests)
- Test: parametrized categorizer rule coverage (T4, 79 tests)
- Test: transfer-detector cascade + override + confidence (T5, 27 tests)
- Chore(ci): pytest with coverage in validate workflow (T7)
- Docs: sync CLAUDE.md phases with actual code state (D1)
- Docs: audit-synthesis concept page (Phase 2 artifact)
- Result: 165/165 tests pass; ruff 0 errors; coverage 31% (categorizer 96%, transfer_detector 91%, const 100%); payload synced

## 0.12.1
- Preserve partial balances when Enable Banking rate-limit hits mid-fetch — accounts that succeeded before the 429 no longer lose their fresh value, merged into the existing cache instead of being discarded
- Reconstruct `_previous_balances` baseline from cached balances on `async_initialize` so the first refresh after every HA restart no longer fires spurious `fd_balance_changed` events for every account
- Balance-refresh end path now merges into existing cache instead of replacing — accounts that errored this round keep their last known value
- Deferred reload after setup-wizard completion now triggers a real live refresh via `manager.async_refresh_transactions()` instead of a cache-only `coordinator.async_refresh()` — entities populate with actual bank data immediately, no more "unavailable" state until the user clicks "Aktualisieren"
- `async_load_cached` failure path publishes an empty snapshot so entities stay `unknown` (recoverable) instead of `unavailable` (stuck) when cache read errors
- `refresh_accounts` service call now pushes the updated state through the coordinator so dashboards reflect the new account metadata immediately, matching `refresh_transactions` behavior
- Always load the cached snapshot into the coordinator regardless of `configured`/`demo_mode` state so half-configured entries don't leave entities permanently unavailable
- `BudgetLimitNumber` now inherits from `RestoreEntity` — user-set budget limits survive HA restarts instead of silently resetting to 0
- `SplitModelSelect` and `RemainderModeSelect` listen for config-entry updates and re-sync their current option when the options flow changes the stored key — no more stale display after external option changes
- `/demo/toggle` returns HTTP 503 when no manager is configured instead of toggling a dead `hass.data` flag that nothing reads
- Drop unused `ENABLEBANKING_RATE_LIMIT_DAILY` import, move `RateLimitExceeded` below all imports for a clean module layout
- Docs(__init__): replace stale "GoCardless/Nordigen" docstring with Enable Banking PSD2 reference, document the 4/day/ASPSP rate-limit gate
- Docs(addon): replace stale "GoCardless Open Banking API" description in `finance_dashboard_companion/config.yaml` with Enable Banking PSD2

## 0.12.0
- New `fd-transactions-log` card shows imported (cached) transactions after at least one bank is linked and a refresh ran — date, counterparty, description, category badge, account, coloured amount, "vorgemerkt" flag for pending items; collapses to 25 rows with "Alle N anzeigen" toggle (cap 100 from the API)
- `fd-data-provider` caches `/api/finance_dashboard/transactions` in-memory, refetches on user-triggered refresh and on first rebuild with linked accounts — entity-only state changes no longer trigger redundant fetches, and the endpoint is cache-read only (unbounded-safe, no Enable Banking call)
- Register `fd-transactions-log.js` in `LOVELACE_COMPONENTS`, append component after `fd-recurring-list` in the shell's component tree

## 0.11.1
- Btn-demo now renders neutral/ghost by default — orange fill only when demo mode is active (btn-demo-active), preventing false "already in demo" appearance
- Refresh race eliminated — after POST /refresh, poll for entity state change (≤5s, 500ms ticks) before calling _rebuild(), avoiding stale hass.states read that returned accountCount=0 and flashed onboarding screen
- _onHassChanged no longer advances _prevStateHash when _loading=true; instead sets _pendingRebuild=true so _rebuild retries immediately after the in-flight rebuild finishes, closing the concurrent-rebuild deadlock

## 0.11.0
- Separate cache-reads from live API fetches — `manager.async_get_balance()` now returns cached balances only (was hitting Enable Banking on every HTTP `/balances` call, burning the 4/day/ASPSP rate limit)
- Serialise user-triggered refreshes with `asyncio.Lock` to prevent double-click concurrent fetches
- Persist `rate_limited_until` and `last_refresh_stats` across HA restart so the 4/day counter is not lost on reboot
- Track structured refresh stats (outcome, accounts, transactions, new, duration_ms, errors) exposed via `manager.get_refresh_status()`
- New `POST /api/finance_dashboard/refresh` endpoint — the single user-triggered live-fetch entry point, returns stats synchronously
- New `GET /api/finance_dashboard/refresh_status` — cache-only polling endpoint, unbounded reads allowed
- `refresh_transactions` service now uses `SupportsResponse.OPTIONAL` and returns stats so automations can react to the outcome
- Refresh_transactions refreshes balances in the same user-triggered round — one click, one cache update
- Refresh button now shows a result toast ("5 Konten, 243 Transaktionen, 2 neu in 3.1s" / rate-limit / partial / error)
- Header timestamp shows live cache age ("Zuletzt 14:23 · vor 2 Std") and updates every minute
- Rate-limit and loading states surfaced clearly next to the refresh button instead of silent "Aktualisieren" reverts
- "Noch keine Daten" state now has explicit styling + hint to click Aktualisieren
- Remove staleness-based auto-refresh — coordinator is now a pure cache projection, live fetches only via dedicated endpoint
- Docs(claude-md): replace stale GoCardless references with Enable Banking, document cache vs. live-fetch contract

## 0.10.1
- Propagate OAuth callback errors through /setup/status so the wizard surfaces them within 2s instead of timing out after 5min
- Hard-fail /setup/authorize when callback URL is HTTP (Enable Banking requires pre-registered HTTPS redirect)
- Trigger one coordinator refresh after deferred entry reload so entities populate immediately after bank link
- Raise Repairs issue on missing or invalid Enable Banking credentials, auto-clear on recovery
- Wizard polling stops on setup_error and shows the message instead of waiting for timeout
- Data provider subscribes to entity_registry_updated events so newly created sensors appear without race-prone 4s timer

## 0.10.0
- Add inline bank connection wizard as modal overlay (4-step flow: institution search, bank authorization with polling, account assignment, success)
- Replace fragile entity_id prefix matching with HA Entity Registry lookup — entities are now found by platform + unique_id regardless of HA-generated entity_ids
- Add "+ Konto" button in header to open wizard from anywhere
- Replace onboarding "Einstellungen" link with inline "Bankkonto verbinden" button
- Add 4s delay before refreshRegistry() after setup complete to wait for HA config entry reload
- Add https scheme validation on auth URLs to prevent XSS via javascript: scheme
- Update institution filter to only re-render list container (prevents cursor jump)

## 0.9.2
- Remove automatic banking API calls on HA startup — coordinator now loads from cache only, no external calls until user clicks "Aktualisieren"
- Remove _first_update force-refresh flag from coordinator — staleness check is sufficient
- Remove automatic API fallback in _rebuild() — /summary endpoint only called on explicit user refresh, not on every entity change
- Add onboarding welcome screen with "Demo starten" CTA when no bank accounts connected
- Show "Noch keine Daten" timestamp fallback when no refresh has occurred
- Make Demo button more prominent with visible background fill
- Handle loading state in _onData to prevent clearing content during demo toggle

## 0.9.1
- Add missing issue-level description to strings.json — Repairs card had no body text, rendering it invisible in some HA versions
- Add is_persistent=True to ir.async_create_issue — prevents HA from discarding the issue during internal operations
- Wrap synchronous file I/O (exists/read_text/unlink) in async_add_executor_job — HA 2024+ blocks or warns on sync I/O in event loop
- Return None for unknown issue_ids instead of generic RepairsFlow()
- Chore: sync translations (en.json, de.json) with new issue description
- Chore: sync addon payload

## 0.9.0
- Full demo mode with realistic German banking data (3 accounts, ~35 transactions, household split, recurring patterns)
- Toggle via UI button (admin-only), service call, or options flow — persists across HA restarts
- Manual-only API refresh — coordinator update_interval=None, data only updates on explicit user action
- Initial coordinator refresh now works on config entry reloads (not just first HA start)
- Shutdown no longer overwrites real transaction cache when demo mode is active
- AttributeError in DemoToggleView coordinator lookup — null-safe access pattern
- GoCardless reference replaced with Enable Banking in services.yaml
- Removed dead COORDINATOR_UPDATE_INTERVAL constant and corrected all docstrings
- Demo toggle button with DEMO badge, aria-pressed accessibility, mobile breakpoint
- Rapid-click guard and loading state for demo API calls
- DemoMode flag propagated in all data events for consistent UI state

## 0.8.1
- Dashboard no longer stuck on "Lade Finanzdaten..." when no finance entities exist
- Restart notification no longer lost due to race condition in entry setup
- Prevent infinite loading spinner when no fd_ entities exist — data provider now always triggers initial rebuild
- Chore: add .playwright-mcp/ to .gitignore

## 0.8.0
- Decompose monolithic panel into 10 web components (fd-data-provider, fd-header, fd-stats-row, fd-stat-card, fd-household-section, fd-person-card, fd-category-section, fd-donut-chart, fd-cost-distribution, fd-recurring-list)
- Entity-first data strategy — fd-data-provider reads HA sensor/number/select entities, falls back to API for household+recurring
- Panel shell reduced from 507 lines to ~120 lines
- Coordinator force-refreshes transactions on first cycle — prevents stale cache showing 0,00 EUR
- Account settings API now persists `person` field for household assignment
- Monthly summary sensor exposes fixed_costs, variable_costs, household, recurring attributes
- Docs: ARCHITECTURE-FRONTEND.md added with component hierarchy, data flow, entity table, event system

## 0.7.8
- Graceful degradation for household model — exception no longer crashes coordinator
- Graceful degradation for recurring detection — failure yields empty list
- Graceful degradation for budget limit checks — log and skip on error
- Graceful degradation for event firing (balance + transaction) — never blocks data flow

## 0.7.7
- Integrate HouseholdModel into manager — auto-builds members from account assignments, computes per-person Spielgeld splits
- Activate recurring payment detection on each transaction refresh
- Fire fd_transaction_new, fd_balance_changed, fd_budget_exceeded events
- Budget limit checking against Number entities per category
- Fixed vs variable cost computation in summary API
- Dashboard shows real bank balance from API (not income minus expenses)
- Person cards with Spielgeld, income ratio, shared costs share
- Shared Fixkosten bar with per-person distribution
- Recurring payments section with detected patterns
- German category labels (Wohnen, Mobilität, etc.)
- Responsive layout for mobile viewports
- XSS protection for user-provided names

## 0.7.6
- Add DataUpdateCoordinator — entities no longer call banking API directly
- Sensor update interval 10 min via coordinator (was ~30 s per entity → rate-limit exhaustion)
- Panel refresh on connectedCallback + 10-min auto-timer instead of every hass setter
- Lovelace card throttles API calls to max once per 10 min (was every hass setter)
- Coordinator refreshes transactions only when cache is stale (>6 h), balances every 10 min
- Manual refresh_transactions service triggers coordinator push to entities


## 0.7.5
- Expose config entry to API views (entry key was never set)
- Auto-refresh transactions on HA startup (summary panel showed zeros)

## 0.7.4
- **Branch:** claude/upbeat-davinci
- **Changes:** feat(frontend): status chip replaces refresh button
- New `<finance-status-chip>` Lovelace component with 4 visual states (idle/loading/success/error)
- Panel header uses status chip instead of refresh button + dot indicator
- Register status chip JS as Lovelace extra module

## 0.7.3
- Fix setup wizard race condition — guard flag prevents wizard re-trigger during entry reload
- Fix account defaults in step 3 — merge existing settings into pending accounts

## 0.7.2
- Fix setup/complete merges new accounts with existing ones instead of replacing entry.data
- Fix dashboard refresh uses independent error handling per endpoint
- Fix manage accounts dialog retries 3x with 2s delay before showing error

## 0.7.1
- Fix settings overlay flash on load
- Fix balance data display in account cards

## 0.7.0
- Cascading transfer chain detection

## 0.6.15
- Gesamtsaldo uses actual bank balances from /balances API
- Settings gear icon in dashboard header for account management
- Manage-accounts overlay with rename, type change, person assignment
- New update_accounts endpoint and account details in setup/status

## 0.6.14
- Shimmer skeleton loaders replacing plain loading text
- Async refresh indicator (pulsing dot + timestamp)
- Responsive breakpoints for tablet and mobile
- Improved empty state with SVG icon and descriptive text

## 0.6.12
- HA user multi-select chips in step 3 instead of free-text person field
- Custom display name field per account
- New setup/users endpoint for HA user list

## 0.6.9
- Fix RepairsFlow calls homeassistant.restart service when user confirms
- Fix repair notification title says "Restart Required"
- Updated EN and DE translations for restart repair flow

## 0.6.5
- Fix retry logic and error handling for bank list API calls
- Fix graceful error handling when fetching supported banks fails
- Fix frontend error state with actionable feedback

## 0.6.4
- Fix credential return type breaking bank list loading (dict instead of tuple)

## 0.6.3
- Fix backend returns typed errors for differentiated frontend handling
- Fix frontend shows specific German error messages per error type
- Fix credential errors link to integration settings
- Fix 5-minute polling timeout in Step 2

## 0.6.2
- Fix restart marker poll outside is_configured, check on startup

## 0.6.1
- Fix 30s timeout for Enable Banking API, error state with retry button
- Rename "Finance Dashboard" to "Finance" everywhere

## 0.6.0
- Move bank setup from config flow to dashboard panel setup wizard
- Config flow reduced to credentials-only (1 step, config VERSION 3)
- 4-step setup wizard overlay in Finance sidebar panel
- 4 new setup API endpoints
- Config entry migration v2 to v3

## 0.5.5
- Fix granular Enable Banking API debug logging

## 0.5.2
- Fix config flow error handling for PEM key format errors vs API auth failures

## 0.5.1
- Fix PEM private key field renders as multiline textarea
- Remove deprecated arch values from companion add-on config
- Step-by-step Enable Banking setup instructions

## 0.5.0
- Migrate from GoCardless to Enable Banking API
- New EnableBankingClient with JWT RS256 signing
- Config flow v2 with migration handler

## 0.4.3
- Remove unused nordigen-python dependency (fixes 500 error on config flow)

## 0.4.2
- Fix sidebar panel not appearing (use correct panel_custom API)
- Fix repository.yaml format (remove non-standard channel field)

## 0.4.1
- Fix add-on not showing updates (add exec sleep infinity)
- Fix config.yaml missing fields (stage, options, schema, homeassistant_api)
- Add dark mode icon variants
- Switch to bashio structured logging
- Replace SVG brand assets with PNGs

## 0.4.0
- Benchmark auto-crawl with German national averages
- Drag & drop transaction categorizer
- CSV export service

## 0.3.0
- N-person household budget model
- Recurring transaction detection
- Income recognition with salary tolerance
- Bonus detection
- Budget Config Lovelace card

## 0.2.0
- GoCardless OAuth flow
- Account balance sensors
- Monthly summary sensor
- Privacy-first API

## 0.1.0
- Initial release
