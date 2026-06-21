"""Tests for the opt-in once-a-day scheduled refresh.

The scheduler in ``__init__._async_setup_auto_refresh`` is the only automatic
live-fetch path. These tests pin down its contract:

- it registers a daily ``async_track_time_change`` only when enabled;
- it fires at the user-chosen hour;
- the callback respects the same rate-limit and demo-mode gates as a manual
  refresh, so Enable Banking's 4/day quota is never exceeded by the scheduler.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from custom_components.finance_dashboard import _async_setup_auto_refresh
from custom_components.finance_dashboard.const import (
    CONF_AUTO_REFRESH_ENABLED,
    CONF_AUTO_REFRESH_HOUR,
)


def _build_entry(options: dict) -> MagicMock:
    entry = MagicMock()
    entry.options = options
    entry.async_on_unload = MagicMock()
    return entry


def _build_manager(*, demo_mode: bool = False, rate_limited=None) -> MagicMock:
    manager = MagicMock()
    manager.demo_mode = demo_mode
    manager.rate_limited_until = rate_limited
    manager.async_refresh_transactions = AsyncMock()
    return manager


def _arm(entry, manager, coordinator):
    """Run setup with a patched tracker; return (registered, callback)."""
    hass = MagicMock()
    with patch(
        "custom_components.finance_dashboard.async_track_time_change",
        return_value=MagicMock(),
    ) as tracker:
        _async_setup_auto_refresh(hass, entry, manager, coordinator)
    if not tracker.called:
        return tracker, None
    # async_track_time_change(hass, action, hour=, minute=, second=)
    callback = tracker.call_args.args[1]
    return tracker, callback


def test_disabled_registers_nothing() -> None:
    entry = _build_entry({CONF_AUTO_REFRESH_ENABLED: False, CONF_AUTO_REFRESH_HOUR: 6})
    tracker, callback = _arm(entry, _build_manager(), MagicMock())
    assert not tracker.called
    assert callback is None
    entry.async_on_unload.assert_not_called()


def test_enabled_registers_at_configured_hour() -> None:
    entry = _build_entry({CONF_AUTO_REFRESH_ENABLED: True, CONF_AUTO_REFRESH_HOUR: 9})
    tracker, _callback = _arm(entry, _build_manager(), MagicMock())
    assert tracker.called
    assert tracker.call_args.kwargs == {"hour": 9, "minute": 0, "second": 0}
    # The unsub must be registered for automatic cleanup on unload/reload.
    entry.async_on_unload.assert_called_once()


async def test_callback_refreshes_when_clear() -> None:
    entry = _build_entry({CONF_AUTO_REFRESH_ENABLED: True, CONF_AUTO_REFRESH_HOUR: 6})
    manager = _build_manager()
    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    _tracker, callback = _arm(entry, manager, coordinator)

    await callback(datetime.now())

    manager.async_refresh_transactions.assert_awaited_once()
    coordinator.async_refresh.assert_awaited_once()


async def test_callback_skips_when_rate_limited() -> None:
    entry = _build_entry({CONF_AUTO_REFRESH_ENABLED: True, CONF_AUTO_REFRESH_HOUR: 6})
    manager = _build_manager(rate_limited=datetime.now() + timedelta(hours=2))
    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    _tracker, callback = _arm(entry, manager, coordinator)

    await callback(datetime.now())

    manager.async_refresh_transactions.assert_not_awaited()
    coordinator.async_refresh.assert_not_awaited()


async def test_callback_skips_in_demo_mode() -> None:
    entry = _build_entry({CONF_AUTO_REFRESH_ENABLED: True, CONF_AUTO_REFRESH_HOUR: 6})
    manager = _build_manager(demo_mode=True)
    coordinator = MagicMock()
    coordinator.async_refresh = AsyncMock()
    _tracker, callback = _arm(entry, manager, coordinator)

    await callback(datetime.now())

    manager.async_refresh_transactions.assert_not_awaited()
    coordinator.async_refresh.assert_not_awaited()
