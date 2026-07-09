"""Finance Manager — core business logic orchestrator.

Coordinates between:
- Enable Banking API client (banking data via PSD2)
- Credential Manager (secure storage)
- Transaction Categorizer (auto-classification)
- Transaction Cache (encrypted .storage/)

SECURITY: All transaction data is cached in HA's .storage/ directory
(encrypted at rest). No financial data is ever written to logs or git.

CACHE vs LIVE FETCH CONTRACT:
- ``get_cached_*`` / ``async_get_balance`` return in-memory cache only —
  zero API calls, unbounded calls allowed. Use from HTTP read endpoints.
- ``async_refresh_*`` hits the Enable Banking API and updates the cache —
  ONLY called from explicit user-triggered paths (service call, refresh
  button, setup-complete bootstrap). Enable Banking enforces a 4/day
  ASPSP rate limit, so automatic background fetches are forbidden.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store
from homeassistant.util import dt as dt_util

from ..const import (
    DOMAIN,
    ENABLEBANKING_RATE_LIMIT_DAILY,
    STORAGE_KEY_CUSTOM_RULES,
    STORAGE_KEY_TRANSFER_OVERRIDES,
)
from ..household import HouseholdMember, HouseholdModel
from ..month_cycle import get_month_range
from ..transfer_detector import (
    apply_overrides,
    get_effective_transactions,
)
from ._persistence import PersistenceMixin
from ._refresh import RefreshMixin

_LOGGER = logging.getLogger(__name__)

TRANSACTION_CACHE_KEY = f"{DOMAIN}_transactions"
TRANSACTION_CACHE_VERSION = 1

# OAuth state token TTL in seconds (10 minutes) — kept here for test imports
_OAUTH_STATE_TTL = 600


class FinanceDashboardManager(RefreshMixin, PersistenceMixin):
    """Central orchestrator for the Finance integration.

    Inherits from:
    - RefreshMixin   (_refresh.py) — all live-fetch + OAuth methods
    - PersistenceMixin (_persistence.py) — storage read/write
    """

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        """Initialize the manager."""
        self._hass = hass
        self._entry = entry
        self._credential_manager = None
        self._banking_client = None
        self._categorizer = None
        self._transaction_store = Store(hass, TRANSACTION_CACHE_VERSION, TRANSACTION_CACHE_KEY)
        self._accounts: list[dict[str, Any]] = entry.data.get("accounts", [])
        # Per-account transaction cache: account_id → list[tx].
        # Partial refresh failures only affect the failed account's slice —
        # other accounts keep their last-known data (R5 fix).
        self._tx_by_account: dict[str, list[dict[str, Any]]] = {}
        # Flat view (legacy + internal use) — kept in sync with _tx_by_account.
        self._transactions: list[dict[str, Any]] = []
        self._balances: dict[str, Any] = {}
        self._last_refresh: datetime | None = None
        # Per-account timestamp of the last *successful* transaction fetch
        # (account_id → ISO string). A live fetch that raises (stale session,
        # 422, rate-limit) never updates this, so an account whose bank is
        # failing silently keeps an old timestamp — surfaced in the account
        # editor so the user notices instead of assuming everything refreshed.
        self._last_success_by_account: dict[str, str] = {}
        # Per-account error from the last refresh attempt (account_id → dict:
        # {"type": slug, "message": str, "at": ISO}). Set when an account's
        # live fetch fails, cleared when it next succeeds. Lets the account
        # editor show an explicit reason ("session expired — re-authorize")
        # immediately, instead of waiting for the timestamp to go stale.
        self._last_error_by_account: dict[str, dict[str, Any]] = {}
        self._rate_limited_until: datetime | None = None
        self._transfer_override_store = Store(hass, 1, STORAGE_KEY_TRANSFER_OVERRIDES)
        self._transfer_overrides: dict[str, bool] = {}
        # User-added categorization keywords: category → [keywords].
        # Persisted in .storage/ and merged on top of the built-in rules.
        self._custom_rules_store = Store(hass, 1, STORAGE_KEY_CUSTOM_RULES)
        self._custom_rules: dict[str, list[str]] = {}
        self._recurring_patterns: list[dict[str, Any]] = []
        self._previous_balances: dict[str, float] = {}
        self._demo_mode: bool = False
        # Last user-triggered refresh statistics — surfaced to the UI so
        # the user sees exactly what happened on the last "Aktualisieren"
        # click (accounts hit, transactions loaded, duration, outcome).
        # Structure: {"outcome": str, "accounts": int, "transactions": int,
        #   "new": int, "duration_ms": int, "started_at": ISO,
        #   "finished_at": ISO, "errors": list[str]}
        self._last_refresh_stats: dict[str, Any] = {}
        # Serialises concurrent refresh requests (double-click guard,
        # parallel service calls). In-flight state is also surfaced via
        # ``is_refreshing`` so the frontend can poll for completion.
        self._refresh_lock = asyncio.Lock()
        self._refresh_in_flight: bool = False
        # OAuth state tokens: {state_str: created_iso} — one-time-use, 10min TTL
        self._oauth_states: dict[str, str] = {}
        # Backfill flag — False until the first 365-day fetch succeeds.
        # Persisted in the transaction store so it survives HA restarts.
        self._initial_sync_complete: bool = False

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def rate_limited_until(self) -> datetime | None:
        """Return the datetime until which the API is rate-limited, or None."""
        if self._rate_limited_until and dt_util.now() < self._rate_limited_until:
            return self._rate_limited_until
        return None

    @property
    def is_refreshing(self) -> bool:
        """True while a user-triggered refresh is in flight."""
        return self._refresh_in_flight

    @property
    def last_refresh(self) -> datetime | None:
        """Timestamp of the last successful transaction refresh, if any."""
        return self._last_refresh

    @property
    def last_refresh_stats(self) -> dict[str, Any]:
        """Structured stats from the most recent refresh attempt."""
        return dict(self._last_refresh_stats)

    @property
    def demo_mode(self) -> bool:
        """Return whether demo mode is active."""
        return self._demo_mode

    # ------------------------------------------------------------------
    # Demo mode
    # ------------------------------------------------------------------

    def set_demo_mode(self, enabled: bool) -> None:
        """Toggle demo mode on or off.

        When enabled, loads synthetic demo data into the manager's state.
        When disabled, clears demo data and reverts to real cached data.
        """
        self._demo_mode = enabled
        if enabled:
            from ..demo import generate_demo_data

            data = generate_demo_data()
            self._accounts = data["_demo_accounts"]
            self._transactions = data["_demo_transactions"]
            self._balances = data["_demo_balances"]
            self._last_refresh = dt_util.now()
            self._recurring_patterns = data.get("recurring", [])
            self._last_refresh_stats = self._build_stats(
                outcome="demo",
                started=self._last_refresh,
                duration_ms=0,
                accounts=len(self._accounts),
                transactions=len(self._transactions),
                new=0,
                errors=[],
            )
            _LOGGER.info("Demo mode enabled — loaded synthetic data")
        else:
            # Clear demo data — real data reloads on next manual refresh
            self._accounts = self._entry.data.get("accounts", [])
            self._transactions = []
            self._balances = {}
            self._last_refresh = None
            self._recurring_patterns = []
            _LOGGER.info("Demo mode disabled — cleared synthetic data")

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def async_initialize(self) -> None:  # noqa: PLR0915
        """Initialize all sub-components."""
        from ..categorizer import TransactionCategorizer
        from ..credential_manager import CredentialManager

        self._credential_manager = CredentialManager(self._hass)
        await self._credential_manager.async_initialize()

        # Load user-added categorization keywords — a corrupt or missing
        # file must never block startup; fall back to built-in rules only.
        try:
            stored_rules = await self._custom_rules_store.async_load()
            if isinstance(stored_rules, dict):
                self._custom_rules = {
                    str(cat): [str(kw) for kw in kws]
                    for cat, kws in stored_rules.items()
                    if isinstance(kws, list)
                }
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            _LOGGER.error(
                "Custom rules store corrupt (%s: %s) — using built-in rules only",
                type(exc).__name__,
                exc,
            )

        self._categorizer = TransactionCategorizer(custom_rules=self._custom_rules or None)

        # Load cached transactions from .storage/
        # R8: wrap in try/except — a corrupt .storage/ file must not crash
        # HA startup.  On decode error the file is renamed to .corrupt-<ts>
        # and a Repair issue is raised so the user is notified.
        cached = None
        try:
            cached = await self._transaction_store.async_load()
        except (json.JSONDecodeError, ValueError, OSError) as exc:
            _LOGGER.error(
                "Transaction cache corrupt (%s: %s) — starting with empty state",
                type(exc).__name__,
                exc,
            )
            self._raise_storage_corrupt_issue(TRANSACTION_CACHE_KEY, type(exc).__name__)
        if cached and ("transactions" in cached or "tx_by_account" in cached):
            # R5: prefer per-account dict; fall back to flat list (migration).
            raw_tx_by_account = cached.get("tx_by_account")
            if isinstance(raw_tx_by_account, dict):
                self._tx_by_account = raw_tx_by_account
                # Deduplicate by transactionId — the same physical account may be
                # linked under multiple session IDs, causing identical transactions
                # in separate buckets.
                seen_ids: set[str] = set()
                deduped: list[dict] = []
                for txs in self._tx_by_account.values():
                    for tx in txs:
                        tid = tx.get("transactionId")
                        if tid:
                            if tid in seen_ids:
                                continue
                            seen_ids.add(tid)
                        deduped.append(tx)
                raw_total = sum(len(v) for v in self._tx_by_account.values())
                if raw_total != len(deduped):
                    _LOGGER.warning(
                        "Deduplicated %d duplicate transactions on load "
                        "(total=%d, unique=%d). Same bank account may be "
                        "linked under multiple Enable Banking sessions.",
                        raw_total - len(deduped), raw_total, len(deduped),
                    )
                self._transactions = deduped
                # Deterministic sort after flatten
                self._transactions.sort(key=lambda t: t.get("bookingDate", ""), reverse=True)
            else:
                # Migrate: old flat list → per-account dict
                flat: list[dict[str, Any]] = cached.get("transactions", [])
                self._transactions = flat
                for tx in flat:
                    acc_id = tx.get("_account_id", "__unknown__")
                    self._tx_by_account.setdefault(acc_id, []).append(tx)
            last_refresh = cached.get("last_refresh")
            if last_refresh:
                try:
                    self._last_refresh = datetime.fromisoformat(last_refresh)
                except ValueError:
                    self._last_refresh = None
            # Cached balances survive restart so the UI shows something
            # immediately — they're only reset by an explicit live refresh.
            self._balances = cached.get("balances", {}) or {}
            # Rebuild the balance-change baseline from the cache, otherwise
            # the first refresh after every HA restart fires a
            # fd_balance_changed event for every account (stale baseline =
            # 0.00 vs. cached value) and spams user automations.
            for acc_id, data in self._balances.items():
                raw = data.get("balances") if isinstance(data, dict) else None
                if not raw:
                    continue
                try:
                    self._previous_balances[acc_id] = float(
                        raw[0].get("balanceAmount", {}).get("amount", 0)
                    )
                except (TypeError, ValueError, IndexError, AttributeError):
                    continue
            # Rate-limit state must survive restart — otherwise a user
            # who hit HTTP 429 at 23:59 would "reset" by bouncing HA.
            rl = cached.get("rate_limited_until")
            if rl:
                try:
                    rl_dt = datetime.fromisoformat(rl)
                    # Ensure UTC-aware for comparison (F3)
                    if rl_dt.tzinfo is None:
                        rl_dt = rl_dt.replace(tzinfo=UTC)
                    if rl_dt > dt_util.now():
                        self._rate_limited_until = rl_dt
                        # Mirror to hass.data so the fresh-setup client gate
                        # can enforce the quota even before manager is reached (F2).
                        self._hass.data.setdefault(DOMAIN, {})["_global_rate_limit_until"] = (
                            rl_dt.isoformat()
                        )
                except ValueError:
                    pass
            stats = cached.get("last_refresh_stats")
            if isinstance(stats, dict):
                self._last_refresh_stats = stats
            last_success = cached.get("last_success_by_account")
            if isinstance(last_success, dict):
                self._last_success_by_account = {
                    str(k): str(v) for k, v in last_success.items() if v
                }
            last_errors = cached.get("last_error_by_account")
            if isinstance(last_errors, dict):
                self._last_error_by_account = {
                    str(k): v for k, v in last_errors.items() if isinstance(v, dict)
                }
            # Migration: caches written before this feature existed have no
            # per-account success map. Seed it from the global last_refresh so
            # existing installs show the last known refresh instead of a
            # misleading "never" (see _backfill_last_success_from_global).
            self._backfill_last_success_from_global()
            self._initial_sync_complete = bool(cached.get("initial_sync_complete", False))
            _LOGGER.info(
                "Loaded %d cached transactions (last refresh: %s, balances: %d)",
                len(self._transactions),
                self._last_refresh,
                len(self._balances),
            )

        _LOGGER.info("Finance Manager initialized")

    async def async_shutdown(self) -> None:
        """Clean shutdown — persist cache, clear sensitive data from memory."""
        # Only persist real transactions — never overwrite cache with demo data
        if not self._demo_mode:
            await self._persist_transactions()
        self._banking_client = None
        self._balances.clear()
        _LOGGER.info("Finance Manager shut down")

    # ------------------------------------------------------------------
    # Account management
    # ------------------------------------------------------------------

    def async_set_accounts(self, accounts: list[dict[str, Any]]) -> None:
        """Update the in-memory account list (encapsulated write path).

        Validates that *accounts* is a list; persists immediately to the
        config-entry data so the new assignments survive an HA restart.
        """
        if not isinstance(accounts, list):
            raise TypeError(f"async_set_accounts: expected list, got {type(accounts).__name__}")
        self._accounts = accounts
        # Mirror to config-entry data so accounts survive HA restart
        try:
            new_data = {**self._entry.data, "accounts": accounts}
            self._hass.config_entries.async_update_entry(self._entry, data=new_data)
        except Exception:
            _LOGGER.warning(
                "async_set_accounts: failed to persist to config entry",
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Account refresh
    # ------------------------------------------------------------------

    async def async_refresh_accounts(self) -> list[dict[str, Any]]:
        """Refresh account list from Enable Banking."""
        if self._demo_mode:
            return self._accounts
        client = await self._async_get_client()
        if not client:
            return []

        refreshed = []
        for account in self._accounts:
            acc_id = account.get("id")
            if not acc_id:
                continue
            try:
                details = await client.async_get_account_details(acc_id)
                acc_data = details.get("account", {})
                acc_data["id"] = acc_id
                # Preserve assignment info from config
                acc_data["type"] = account.get("type", "personal")
                acc_data["person"] = account.get("person", "")
                acc_data["ha_users"] = account.get("ha_users", [])
                acc_data["custom_name"] = account.get("custom_name", "")
                acc_data["institution"] = account.get("institution", "")
                acc_data["logo"] = account.get("logo", "")
                refreshed.append(acc_data)
            except Exception:
                _LOGGER.warning("Failed to refresh account %s", acc_id)
                refreshed.append(account)

        self._accounts = refreshed
        await self._credential_manager._audit_log("accounts_refreshed")
        return self._accounts

    # ------------------------------------------------------------------
    # Cache read endpoints (no API calls)
    # ------------------------------------------------------------------

    async def async_get_balance(self) -> dict[str, Any]:
        """Return cached balances — NEVER hits the banking API.

        This is the read path used by the HTTP balance endpoint and the
        coordinator's state queries. Safe for unbounded reads. Live
        updates happen inside ``async_refresh_transactions`` which is
        only invoked from user-triggered refresh paths.
        """
        return dict(self._balances)

    def get_cached_balances(self) -> dict[str, Any]:
        """Synchronous alias for ``async_get_balance`` — cache only."""
        return dict(self._balances)

    async def async_get_monthly_summary(
        self, month: int | None = None, year: int | None = None
    ) -> dict[str, Any]:
        """Get monthly spending summary with category breakdown."""
        now = datetime.now()
        target_month = month or now.month
        target_year = year or now.year

        # Determine cycle range based on configured month_start_day
        month_start_day = self._entry.options.get("month_start_day", 1)
        cycle_mode = "salary" if month_start_day > 1 else "calendar"
        cycle_start, cycle_end = get_month_range(
            target_month, target_year, cycle_mode, month_start_day
        )

        # Use effective transactions (intermediate chain legs excluded)
        effective = get_effective_transactions(self._transactions)

        # Filter for target cycle period
        monthly_txns = [
            txn
            for txn in effective
            if self._is_in_range(txn, cycle_start, cycle_end) and txn.get("_status") == "booked"
        ]

        # Count excluded transfers for transparency
        all_monthly = [
            txn
            for txn in self._transactions
            if self._is_in_range(txn, cycle_start, cycle_end) and txn.get("_status") == "booked"
        ]
        excluded_chain_txns = [
            txn
            for txn in all_monthly
            if txn.get("_transfer_role") in ("intermediate", "destination")
            and txn.get("_transfer_confirmed") is not False
        ]
        excluded_amount = sum(
            abs(float(t.get("transactionAmount", {}).get("amount", 0))) for t in excluded_chain_txns
        )

        # Group by category
        category_totals: dict[str, float] = {}
        total_income = 0.0
        total_expenses = 0.0

        for txn in monthly_txns:
            amount = float(txn.get("transactionAmount", {}).get("amount", 0))
            category = txn.get("category", "other")

            # excluded transactions are intentionally non-computable (internal
            # transfers, ignored items) — skip entirely from income/expenses/categories
            if category == "excluded":
                continue

            if amount > 0:
                total_income += amount
            else:
                total_expenses += abs(amount)

            category_totals[category] = category_totals.get(category, 0) + amount

        # Build household split data from per-person accounts
        # Graceful degradation: household features must never crash the coordinator
        household = None
        try:
            household = self._compute_household(monthly_txns, total_expenses)
        except Exception:
            _LOGGER.exception("Household computation failed — skipping")

        # Recurring patterns (already detected during refresh)
        recurring_top = self._recurring_patterns[:10]

        # Fixed vs variable costs
        fixed_cats = {"housing", "loans", "utilities", "insurance"}
        fixed_total = sum(abs(category_totals.get(c, 0)) for c in fixed_cats)
        variable_total = total_expenses - fixed_total

        # Budget exceeded check — must not crash the coordinator
        try:
            self._check_budget_limits(category_totals)
        except Exception:
            _LOGGER.exception("Budget limit check failed — skipping")

        return {
            "month": target_month,
            "year": target_year,
            "cycle_start": cycle_start.isoformat(),
            "cycle_end": cycle_end.isoformat(),
            "total_income": round(total_income, 2),
            "total_expenses": round(total_expenses, 2),
            "balance": round(total_income - total_expenses, 2),
            "categories": {k: round(v, 2) for k, v in category_totals.items()},
            "transaction_count": len(monthly_txns),
            "excluded_transfers": {
                "chain_count": len(
                    {
                        t.get("_transfer_chain_id")
                        for t in excluded_chain_txns
                        if t.get("_transfer_chain_id")
                    }
                ),
                "excluded_amount": round(excluded_amount, 2),
                "excluded_txn_count": len(excluded_chain_txns),
            },
            "household": household,
            "recurring": [
                {
                    "creditor": p.get("creditor", ""),
                    "average_amount": p.get("average_amount", 0),
                    "frequency": p.get("frequency", "monthly"),
                    "category": p.get("category", "other"),
                    "occurrences": p.get("occurrences", 0),
                    "expected_day": p.get("expected_day", 1),
                }
                for p in recurring_top
            ],
            "fixed_costs": round(fixed_total, 2),
            "variable_costs": round(variable_total, 2),
            "last_refresh": (self._last_refresh.isoformat() if self._last_refresh else None),
            "rate_limited_until": (
                self._rate_limited_until.isoformat() if self.rate_limited_until else None
            ),
            "last_refresh_stats": dict(self._last_refresh_stats),
            "is_refreshing": self._refresh_in_flight,
        }

    async def async_categorize_transactions(self) -> None:
        """Re-run auto-categorization on all cached transactions."""
        if self._demo_mode or not self._categorizer:
            return
        for txn in self._transactions:
            txn["category"] = self._categorizer.categorize(txn)
        await self._persist_transactions()
        _LOGGER.info("Re-categorized %d transactions", len(self._transactions))

    def get_custom_rules(self) -> dict[str, list[str]]:
        """Return a copy of the user-added categorization keywords."""
        return {cat: list(kws) for cat, kws in self._custom_rules.items()}

    async def async_add_categorization_rule(self, category: str, keyword: str) -> dict[str, Any]:
        """Persist a user-added categorization keyword and re-categorize the cache.

        Keywords are stored lowercase (matching is a lowercased substring
        check). Returns the updated custom-rules dict so service callers
        can surface it as a response.
        """
        category = category.strip().lower()
        keyword = keyword.strip().lower()
        if not category or not keyword:
            raise ValueError("category and keyword must be non-empty")

        keywords = self._custom_rules.setdefault(category, [])
        if keyword not in keywords:
            keywords.append(keyword)
            await self._custom_rules_store.async_save(self._custom_rules)
            self._rebuild_categorizer()
            await self.async_categorize_transactions()
            _LOGGER.info("Custom rule added: %s → %s", keyword, category)
        return {"custom_rules": self.get_custom_rules()}

    async def async_remove_categorization_rule(self, category: str, keyword: str) -> dict[str, Any]:
        """Remove a user-added keyword (built-in rules are not affected)."""
        category = category.strip().lower()
        keyword = keyword.strip().lower()

        keywords = self._custom_rules.get(category, [])
        if keyword in keywords:
            keywords.remove(keyword)
            if not keywords:
                self._custom_rules.pop(category, None)
            await self._custom_rules_store.async_save(self._custom_rules)
            self._rebuild_categorizer()
            await self.async_categorize_transactions()
            _LOGGER.info("Custom rule removed: %s → %s", keyword, category)
        return {"custom_rules": self.get_custom_rules()}

    def _rebuild_categorizer(self) -> None:
        """Recreate the categorizer from built-in + current custom rules.

        Needed because TransactionCategorizer.update_rules() can only add
        keywords — removal requires a fresh instance.
        """
        from ..categorizer import TransactionCategorizer

        self._categorizer = TransactionCategorizer(custom_rules=self._custom_rules or None)

    async def async_set_budget_limit(self, category: str, limit: float) -> None:
        """Set a budget limit for a category via the Number entity."""
        entity_id = f"number.fd_budget_{category}"
        state = self._hass.states.get(entity_id)
        if state is not None:
            await self._hass.services.async_call(
                "number",
                "set_value",
                {"entity_id": entity_id, "value": limit},
            )
            _LOGGER.info("Budget limit for %s set to %.2f", category, limit)
        else:
            _LOGGER.warning("Budget entity %s not found", entity_id)

    async def async_export_csv(
        self,
        date_from: str | None = None,
        date_to: str | None = None,
        categories: list[str] | None = None,
    ) -> str:
        """Export transactions as CSV file."""
        from ..export import async_export_csv

        return await async_export_csv(
            self._hass,
            self._transactions,
            date_from=date_from,
            date_to=date_to,
            categories=categories,
        )

    def get_oldest_transaction_dates(self) -> dict[str, str | None]:
        """Return the oldest booked transaction date per account_id (YYYY-MM-DD), or None."""
        result: dict[str, str | None] = {}
        for acc_id, txns in self._tx_by_account.items():
            if acc_id == "__unknown__":
                continue
            dates = [
                t["bookingDate"]
                for t in txns
                if t.get("_status") == "booked" and t.get("bookingDate")
            ]
            result[acc_id] = min(dates) if dates else None
        return result

    def _backfill_last_success_from_global(self) -> None:
        """Seed the per-account success map from the global last_refresh.

        One-time migration for caches written before per-account success
        tracking existed: with no map, every account would render "never" even
        though the last global refresh did touch them. Seeds each account that
        currently holds cached transactions with ``_last_refresh`` so existing
        installs show the last known refresh. Real per-account values take over
        on the next refresh — an account whose bank then fails silently stops
        advancing while the others move on. No-op once the map is populated.
        """
        if self._last_success_by_account or not self._last_refresh:
            return
        iso = self._last_refresh.isoformat()
        for acc_id, txs in self._tx_by_account.items():
            if acc_id != "__unknown__" and txs:
                self._last_success_by_account[acc_id] = iso

    def get_last_success_dates(self) -> dict[str, str | None]:
        """Return the last successful transaction fetch per account_id (ISO), or None.

        Pure cache read. Populated by ``async_refresh_transactions`` each time an
        account's live fetch completes without raising, so a lagging value points
        at an account whose bank is failing silently.
        """
        return {
            acc_id: self._last_success_by_account.get(acc_id)
            for acc_id in (acc.get("id") for acc in self._accounts)
            if acc_id
        }

    def get_account_errors(self) -> dict[str, dict[str, Any]]:
        """Return the last refresh error per linked account_id, or empty dict.

        Pure cache read. Each value is ``{"type", "message", "at"}`` — set when
        the account's last live fetch failed and cleared when it next succeeds.
        Scoped to currently-linked accounts so residue from removed accounts
        never leaks.
        """
        return {
            acc_id: self._last_error_by_account[acc_id]
            for acc_id in (acc.get("id") for acc in self._accounts)
            if acc_id and acc_id in self._last_error_by_account
        }

    def get_cached_transactions(self, limit: int | None = None) -> list[dict[str, Any]]:
        """Get cached transactions (no API call).

        Returns sanitized transactions for API responses. Full details only —
        caller must check admin status. With ``limit=None`` (the default) the
        whole cache is returned: it is already bounded by
        ``HISTORY_RETENTION_MONTHS``, so the frontend can filter the full
        history client-side instead of only the most recent N rows.
        """
        if limit is None:
            return list(self._transactions)
        return self._transactions[:limit]

    # Cache staleness threshold — matches the coordinator constant.
    # Cache is considered stale when older than this value.
    _CACHE_STALE_THRESHOLD_SECONDS: int = 6 * 3600  # 6 hours

    def get_refresh_status(self) -> dict[str, Any]:
        """Return a compact status snapshot for the UI status endpoint.

        Pure cache read — NEVER touches the banking API. Safe for
        unbounded polling while a refresh is in flight.
        """
        now = dt_util.now()
        cache_age_seconds: int | None = None
        cache_is_stale: bool = False
        if self._last_refresh:
            cache_age_seconds = int((now - self._last_refresh).total_seconds())
            cache_is_stale = cache_age_seconds > self._CACHE_STALE_THRESHOLD_SECONDS
        return {
            "is_refreshing": self._refresh_in_flight,
            "last_refresh": (self._last_refresh.isoformat() if self._last_refresh else None),
            "cache_age_seconds": cache_age_seconds,
            "cache_is_stale": cache_is_stale,
            "rate_limited_until": (
                self._rate_limited_until.isoformat() if self.rate_limited_until else None
            ),
            "stats": dict(self._last_refresh_stats),
            "account_count": len(self._accounts),
            "transaction_count": len(self._transactions),
            "has_cache": bool(self._transactions) or bool(self._balances),
            "demo_mode": self._demo_mode,
            # Expose the daily rate-limit cap so the frontend can render
            # the "4/day" label dynamically instead of hardcoding it.
            "rate_limit_per_day": ENABLEBANKING_RATE_LIMIT_DAILY,
        }

    # ------------------------------------------------------------------
    # Transfer chain management
    # ------------------------------------------------------------------

    async def async_confirm_transfer_chain(self, chain_id: str, confirmed: bool) -> None:
        """Confirm or reject a detected transfer chain.

        Args:
            chain_id: The chain UUID to confirm/reject
            confirmed: True = user agrees it's a chain, False = reject
        """
        self._transfer_overrides[chain_id] = confirmed
        await self._transfer_override_store.async_save(self._transfer_overrides)
        # Apply to in-memory transactions immediately
        apply_overrides(self._transactions, self._transfer_overrides)
        _LOGGER.info(
            "Transfer chain %s %s",
            chain_id,
            "confirmed" if confirmed else "rejected",
        )

    def get_transfer_chains(self) -> list[dict[str, Any]]:
        """Return detected transfer chains for API/frontend display."""
        chains: dict[str, dict[str, Any]] = {}
        for txn in self._transactions:
            chain_id = txn.get("_transfer_chain_id")
            if not chain_id:
                continue

            if chain_id not in chains:
                chains[chain_id] = {
                    "chain_id": chain_id,
                    "confidence": txn.get("_transfer_confidence", 0),
                    "confirmed": txn.get("_transfer_confirmed"),
                    "transactions": [],
                }

            amount = float(txn.get("transactionAmount", {}).get("amount", 0))
            chains[chain_id]["transactions"].append(
                {
                    "transactionId": txn.get("transactionId", ""),
                    "role": txn.get("_transfer_role", ""),
                    "account_name": txn.get("_account_name", ""),
                    "amount": amount,
                    "date": txn.get("bookingDate", ""),
                    "creditor": txn.get("creditorName", ""),
                    "description": txn.get("remittanceInformationUnstructured", ""),
                }
            )

        return list(chains.values())

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _compute_household(
        self,
        monthly_txns: list[dict[str, Any]],
        total_expenses: float,
    ) -> dict[str, Any] | None:
        """Build household split data from account assignments and transactions.

        Groups transactions by person (from account assignments), computes
        income and individual costs per person, then runs the household
        split model to calculate each person's share of shared costs
        and their remaining Spielgeld.
        """
        # Build person map from account config
        persons: dict[str, dict[str, Any]] = {}
        for acc in self._accounts:
            person = acc.get("person", "")
            if not person:
                continue
            if person not in persons:
                persons[person] = {
                    "income": 0.0,
                    "individual_costs": 0.0,
                    "account_ids": [],
                    "acc_type": acc.get("type", "personal"),
                }
            persons[person]["account_ids"].append(acc.get("id", ""))

        if not persons:
            return None

        # Sum income and costs per person from their transactions
        shared_costs = 0.0
        shared_cost_items: list[dict[str, Any]] = []

        for txn in monthly_txns:
            amount = float(txn.get("transactionAmount", {}).get("amount", 0))
            acc_type = txn.get("_account_type", "personal")
            person = txn.get("_account_person", "")
            category = txn.get("category", "other")

            if category == "excluded":
                continue

            if acc_type == "shared":
                # Shared account — costs are split among all members
                if amount < 0:
                    shared_costs += abs(amount)
                    shared_cost_items.append(
                        {
                            "category": category,
                            "amount": amount,
                        }
                    )
            elif person and person in persons:
                if amount > 0:
                    persons[person]["income"] += amount
                else:
                    persons[person]["individual_costs"] += abs(amount)

        # Build HouseholdMembers — inherit global salary cycle config
        month_start_day = self._entry.options.get("month_start_day", 1)
        cycle_mode = "salary" if month_start_day > 1 else "calendar"
        members = []
        for name, data in persons.items():
            members.append(
                HouseholdMember(
                    name=name,
                    net_income=data["income"],
                    gross_income=data["income"],
                    individual_costs=data["individual_costs"],
                    account_ids=data["account_ids"],
                    month_cycle=cycle_mode,
                    salary_day=month_start_day,
                )
            )

        split_mode = self._entry.options.get("split_model", "proportional")
        remainder_mode = self._entry.options.get("remainder_mode", "none")

        model = HouseholdModel(
            members=members,
            split_mode=split_mode,
            remainder_mode=remainder_mode,
        )

        results = model.calculate_split(shared_costs, shared_cost_items or None)

        return {
            "members": [
                {
                    "person": r.person,
                    "gross_income": round(r.gross_income, 2),
                    "net_income": round(r.net_income, 2),
                    "income_ratio": round(r.income_ratio * 100, 1),
                    "shared_costs_share": round(r.shared_costs_share, 2),
                    "individual_costs": round(r.individual_costs, 2),
                    "spielgeld": round(r.spielgeld, 2),
                    "bonus_amount": round(r.bonus_amount, 2),
                }
                for r in results
            ],
            "split_model": split_mode,
            "remainder_mode": remainder_mode,
            "total_shared_costs": round(shared_costs, 2),
        }

    def _check_budget_limits(self, category_totals: dict[str, float]) -> None:
        """Check if any category exceeds its budget limit and fire events."""
        from ..events import fire_budget_exceeded

        for category, amount in category_totals.items():
            if amount >= 0:
                continue  # Only check expense categories
            actual = abs(amount)
            entity_id = f"number.fd_budget_{category}"
            state = self._hass.states.get(entity_id)
            if state is None:
                continue
            try:
                limit = float(state.state)
            except (ValueError, TypeError):
                continue
            if limit > 0 and actual > limit:
                fire_budget_exceeded(
                    self._hass,
                    category=category,
                    limit=limit,
                    actual=actual,
                )

    @staticmethod
    def _is_in_range(txn: dict[str, Any], start: Any, end: Any) -> bool:
        """Check if a transaction falls within a date range (inclusive)."""
        booking_date = txn.get("bookingDate", "")
        if not booking_date:
            return False
        try:
            dt = datetime.strptime(booking_date, "%Y-%m-%d").date()
            return start <= dt <= end
        except ValueError:
            return False
