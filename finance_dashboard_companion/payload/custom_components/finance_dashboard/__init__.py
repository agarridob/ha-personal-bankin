"""Finance Dashboard — Home Assistant Integration.

Provides a secure finance overview with live banking data via the Enable
Banking PSD2 Open Banking API (JWT-signed RS256). Tracks accounts,
transactions, and household budgets.

SECURITY: No financial data is ever stored in git or logs.
All credentials and tokens are stored in HA's encrypted .storage/ directory.
Live banking calls are gated behind explicit user-triggered paths
(refresh button, service call, setup bootstrap, and an opt-in once-a-day
scheduled refresh) to respect Enable Banking's 4/day/ASPSP rate limit.
The optional daily scheduler fires at most one live fetch per day at a
user-chosen hour — it is NOT background interval polling.
"""

from __future__ import annotations

import logging

from ha_customapps.restart import RestartNotifier
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, SupportsResponse
from homeassistant.helpers.event import async_track_time_change

from .const import (
    CONF_AUTO_REFRESH_ENABLED,
    CONF_AUTO_REFRESH_HOUR,
    DEFAULT_AUTO_REFRESH_HOUR,
    DOMAIN,
    SERVICE_FETCH_FULL_HISTORY,
    SERVICE_TOGGLE_DEMO,
)

PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.NUMBER,
    Platform.SELECT,
]

_LOGGER = logging.getLogger(__name__)

type FinanceDashboardConfigEntry = ConfigEntry


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up the Finance Dashboard integration."""
    hass.data.setdefault(DOMAIN, {})
    return True


async def async_setup_entry(hass: HomeAssistant, entry: FinanceDashboardConfigEntry) -> bool:
    """Set up Finance Dashboard from a config entry."""
    # Restart notification via ha-customapps (marker polling + Repairs issue)
    notifier = RestartNotifier(hass, DOMAIN)
    await notifier.async_setup(entry)

    # Initialize the manager (core business logic)
    from .manager import FinanceDashboardManager

    manager = FinanceDashboardManager(hass, entry)
    await manager.async_initialize()

    # Notify the user (via HA Repairs) that a 12-month backfill is pending.
    # The issue is cleared automatically once the first 365-day refresh succeeds.
    if not manager.initial_sync_complete:
        from homeassistant.helpers import issue_registry as ir

        ir.async_create_issue(
            hass,
            DOMAIN,
            "initial_sync_pending",
            is_fixable=True,
            is_persistent=False,
            severity=ir.IssueSeverity.WARNING,
            translation_key="initial_sync_pending",
        )

    # Create the coordinator — single source of truth for all entities.
    # Entities read from coordinator.data instead of calling the API directly.
    from .coordinator import FinanceDashboardCoordinator

    coordinator = FinanceDashboardCoordinator(hass, manager)

    # Initialize demo mode from options
    if entry.options.get("demo_mode", False):
        manager.set_demo_mode(True)

    hass.data[DOMAIN][entry.entry_id] = manager
    hass.data[DOMAIN][f"{entry.entry_id}_coordinator"] = coordinator
    hass.data[DOMAIN]["entry"] = entry

    # Register services (pass coordinator so refresh service can push updates)
    await _async_register_services(hass, manager, coordinator)

    # Register sidebar panel
    from .panel import async_register_panel

    await async_register_panel(hass)

    # Register HTTP endpoints
    from .api import async_register_api

    await async_register_api(hass)

    # Forward platform setup — sensors/numbers/selects will register themselves
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Load cached data into coordinator — NO external API calls.
    # Entities are populated immediately from the transaction cache
    # that was loaded in manager.async_initialize(). The user must
    # click "Aktualisieren" to trigger real banking API calls.
    # Run for ALL entry states (configured / pending / demo) so sensors
    # always have a valid coordinator snapshot — without this,
    # half-configured setups leave entities permanently "unavailable"
    # until a full HA restart.
    async def _initial_load() -> None:
        try:
            await coordinator.async_load_cached()
            _LOGGER.info("Initial cached data loaded (no API calls)")
        except Exception:
            _LOGGER.exception("Initial cached data load failed")

    async def _on_started(_event) -> None:
        # Coroutine listener — the event bus awaits it on the event loop,
        # so no manual task creation is needed. Creating tasks from a
        # lambda here crashed on recent HA cores that enforce
        # async_create_task being called from the event loop thread,
        # which aborted the initial cache load and left the panel empty.
        await _initial_load()

    if hass.is_running:
        hass.async_create_task(_initial_load())
    else:
        hass.bus.async_listen_once("homeassistant_started", _on_started)

    # Opt-in once-a-day scheduled refresh (see module docstring). Disabled by
    # default; respects the 4/day rate limit and demo mode.
    _async_setup_auto_refresh(hass, entry, manager, coordinator)

    # Reload the entry when options change so the scheduler is re-armed with
    # the new hour / enabled flag. The unsub registered via async_on_unload
    # is cleaned up automatically on each reload.
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    _LOGGER.info("Finance Dashboard v%s loaded", entry.version)
    return True


async def _async_options_updated(hass: HomeAssistant, entry: FinanceDashboardConfigEntry) -> None:
    """Reload the config entry when options change (re-arms the scheduler)."""
    await hass.config_entries.async_reload(entry.entry_id)


def _async_setup_auto_refresh(
    hass: HomeAssistant,
    entry: FinanceDashboardConfigEntry,
    manager,
    coordinator,
) -> None:
    """Arm a single daily live refresh at a user-chosen hour (opt-in).

    This is the ONLY automatic live-fetch path. It fires at most once per day
    and is gated by the same rate-limit / demo checks as a manual refresh, so
    Enable Banking's 4/day per-ASPSP quota is never exceeded by the scheduler
    alone. When disabled (default) nothing is registered and behaviour is
    identical to before — refreshes happen only on explicit user action.
    """
    if not entry.options.get(CONF_AUTO_REFRESH_ENABLED, False):
        return

    hour = entry.options.get(CONF_AUTO_REFRESH_HOUR, DEFAULT_AUTO_REFRESH_HOUR)

    async def _scheduled_refresh(now) -> None:
        # Never touch the bank in demo mode — cached/sample data only.
        if manager.demo_mode:
            _LOGGER.debug("Scheduled refresh skipped: demo mode active")
            return
        # rate_limited_until returns None once the window has elapsed, so a
        # truthy value means the daily quota is currently exhausted.
        rate_limited = manager.rate_limited_until
        if rate_limited:
            _LOGGER.info(
                "Scheduled refresh skipped: rate-limited until %s",
                rate_limited.isoformat(),
            )
            return
        try:
            await manager.async_refresh_transactions()
            await coordinator.async_refresh()
            _LOGGER.info("Scheduled daily refresh completed")
        except Exception:
            _LOGGER.exception("Scheduled daily refresh failed")

    unsub = async_track_time_change(hass, _scheduled_refresh, hour=hour, minute=0, second=0)
    entry.async_on_unload(unsub)
    _LOGGER.info("Auto-refresh scheduled daily at %02d:00", hour)


async def async_unload_entry(hass: HomeAssistant, entry: FinanceDashboardConfigEntry) -> bool:
    """Unload a config entry."""
    from .panel import async_unregister_panel

    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        manager = hass.data[DOMAIN].pop(entry.entry_id, None)
        hass.data[DOMAIN].pop(f"{entry.entry_id}_coordinator", None)
        if manager:
            await manager.async_shutdown()
        # Clean up entry reference if it matches
        if hass.data.get(DOMAIN, {}).get("entry") is entry:
            hass.data[DOMAIN].pop("entry", None)
        await async_unregister_panel(hass)
    return unload_ok


async def _async_register_services(hass: HomeAssistant, manager, coordinator) -> None:
    """Register integration services."""
    from .const import (
        SERVICE_ADD_RULE,
        SERVICE_CATEGORIZE,
        SERVICE_EXPORT_CSV,
        SERVICE_GET_BALANCE,
        SERVICE_GET_SUMMARY,
        SERVICE_REFRESH_ACCOUNTS,
        SERVICE_REFRESH_TRANSACTIONS,
        SERVICE_REMOVE_RULE,
        SERVICE_SET_BUDGET_LIMIT,
    )

    async def handle_refresh_accounts(call) -> dict:
        await manager.async_refresh_accounts()
        # Keep entity state in lockstep with the account metadata we
        # just refreshed — otherwise the next dashboard render reads
        # stale account data from the coordinator and the user sees
        # no change despite a successful service call.
        try:
            await coordinator.async_refresh()
        except Exception:
            _LOGGER.exception("Coordinator refresh after refresh_accounts failed")
        return manager.get_refresh_status()

    async def handle_refresh_transactions(call) -> dict:
        """User-triggered refresh — returns stats so automations and
        the frontend can surface "5 Konten, 243 Tx, 2 neu" instead
        of a silent OK."""
        await manager.async_refresh_transactions()
        # Push fresh data to all entities via coordinator
        await coordinator.async_refresh()
        return manager.get_refresh_status()

    async def handle_get_balance(call) -> dict:
        return await manager.async_get_balance()

    async def handle_get_summary(call) -> dict:
        return await manager.async_get_monthly_summary()

    async def handle_categorize(call) -> None:
        await manager.async_categorize_transactions()

    async def handle_add_rule(call) -> dict:
        from homeassistant.exceptions import HomeAssistantError

        category = (call.data.get("category") or "").strip()
        keyword = (call.data.get("keyword") or "").strip()
        if not category or not keyword:
            raise HomeAssistantError("category and keyword are required")
        result = await manager.async_add_categorization_rule(category, keyword)
        await coordinator.async_refresh()
        return result

    async def handle_remove_rule(call) -> dict:
        from homeassistant.exceptions import HomeAssistantError

        category = (call.data.get("category") or "").strip()
        keyword = (call.data.get("keyword") or "").strip()
        if not category or not keyword:
            raise HomeAssistantError("category and keyword are required")
        result = await manager.async_remove_categorization_rule(category, keyword)
        await coordinator.async_refresh()
        return result

    async def handle_set_budget_limit(call) -> None:
        category = call.data.get("category")
        limit = call.data.get("limit")
        if category and limit is not None:
            await manager.async_set_budget_limit(category, float(limit))

    async def handle_export_csv(call) -> dict:
        path = await manager.async_export_csv(
            date_from=call.data.get("date_from"),
            date_to=call.data.get("date_to"),
            categories=call.data.get("categories"),
        )
        return {"path": path}

    async def handle_toggle_demo(call) -> None:
        # R14: admin-only gate — toggling demo mode modifies global state
        # and replaces cached transaction data.
        from homeassistant.exceptions import HomeAssistantError

        if not call.context or not call.context.user_id:
            raise HomeAssistantError("admin_required")
        user = await hass.auth.async_get_user(call.context.user_id)
        if user is None or not user.is_admin:
            raise HomeAssistantError("admin_required")

        enabled = not manager.demo_mode
        if enabled:
            # Back up real data before overwriting with demo
            manager._demo_backup_transactions = list(manager._transactions)
            manager._demo_backup_tx_by_account = dict(manager._tx_by_account)
            manager._demo_backup_balances = dict(manager._balances)
            manager._demo_backup_last_refresh = manager._last_refresh
        # Restore real data when disabling demo
        elif hasattr(manager, "_demo_backup_transactions"):
            manager._transactions = manager._demo_backup_transactions
            manager._tx_by_account = manager._demo_backup_tx_by_account
            manager._balances = manager._demo_backup_balances
            manager._last_refresh = manager._demo_backup_last_refresh
        manager.set_demo_mode(enabled)
        await coordinator.async_refresh()

    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_ACCOUNTS,
        handle_refresh_accounts,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REFRESH_TRANSACTIONS,
        handle_refresh_transactions,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(DOMAIN, SERVICE_GET_BALANCE, handle_get_balance)
    hass.services.async_register(DOMAIN, SERVICE_GET_SUMMARY, handle_get_summary)
    hass.services.async_register(DOMAIN, SERVICE_CATEGORIZE, handle_categorize)
    hass.services.async_register(
        DOMAIN,
        SERVICE_ADD_RULE,
        handle_add_rule,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN,
        SERVICE_REMOVE_RULE,
        handle_remove_rule,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(DOMAIN, SERVICE_SET_BUDGET_LIMIT, handle_set_budget_limit)
    hass.services.async_register(DOMAIN, SERVICE_EXPORT_CSV, handle_export_csv)
    hass.services.async_register(DOMAIN, SERVICE_TOGGLE_DEMO, handle_toggle_demo)

    async def handle_fetch_full_history(call) -> dict:
        """Admin-only: reset the backfill flag and re-fetch 365 days of history.

        Calls without a user_id (e.g. from the Repairs fix flow) are trusted
        internal calls and bypass the admin gate.
        """
        from homeassistant.exceptions import HomeAssistantError

        if call.context and call.context.user_id:
            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None or not user.is_admin:
                raise HomeAssistantError("admin_required")

        await manager._clear_initial_sync_complete()
        await manager.async_refresh_transactions()
        await coordinator.async_refresh()
        return manager.get_refresh_status()

    hass.services.async_register(
        DOMAIN,
        SERVICE_FETCH_FULL_HISTORY,
        handle_fetch_full_history,
        supports_response=SupportsResponse.OPTIONAL,
    )
