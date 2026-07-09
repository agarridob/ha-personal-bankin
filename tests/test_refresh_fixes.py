"""Regression tests for the refresh fixes:

1. Stale-account cache pruning (residue from re-linking a bank).
2. 422 WRONG_TRANSACTIONS_PERIOD fallback to progressively smaller windows.
3. _ingest_account_txns tagging + historical merge.

These exercise the RefreshMixin helpers on a bare manager instance built with
``object.__new__`` (same lightweight style as test_partial_refresh.py).
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from homeassistant.util import dt as dt_util

from custom_components.finance_dashboard.enablebanking_client import (
    TransactionPeriodExceeded,
)
from custom_components.finance_dashboard.manager import FinanceDashboardManager


def _bare_manager() -> FinanceDashboardManager:
    return object.__new__(FinanceDashboardManager)


# ---------------------------------------------------------------------------
# Fix 3 — prune stale account buckets
# ---------------------------------------------------------------------------


def test_prune_drops_unlinked_accounts_keeps_active_and_unknown() -> None:
    mgr = _bare_manager()
    mgr._accounts = [{"id": "active-1"}, {"id": "active-2"}]
    mgr._tx_by_account = {
        "active-1": [{"transactionId": "a"}],
        "stale-old": [{"transactionId": "b"}],
        "__unknown__": [{"transactionId": "c"}],
    }
    mgr._balances = {
        "active-1": {"balances": []},
        "active-2": {"balances": []},
        "stale-old": {"balances": []},
    }

    mgr._prune_stale_account_cache()

    assert set(mgr._tx_by_account) == {"active-1", "__unknown__"}
    assert set(mgr._balances) == {"active-1", "active-2"}


def test_prune_no_op_when_all_active() -> None:
    mgr = _bare_manager()
    mgr._accounts = [{"id": "x"}]
    mgr._tx_by_account = {"x": []}
    mgr._balances = {"x": {}}

    mgr._prune_stale_account_cache()

    assert set(mgr._tx_by_account) == {"x"}
    assert set(mgr._balances) == {"x"}


# ---------------------------------------------------------------------------
# Fix 2 — 422 fallback to smaller windows
# ---------------------------------------------------------------------------


class _FakeClient:
    """Records the date_from of each call and raises 422 for windows that are
    'too wide' (date_from earlier than ``accept_from``)."""

    def __init__(self, accept_from: str | None) -> None:
        self.accept_from = accept_from
        self.calls: list[str] = []

    async def async_get_transactions(self, account_id, date_from, date_to, psu_ip=None):
        self.calls.append(date_from)
        if self.accept_from is not None and date_from < self.accept_from:
            raise TransactionPeriodExceeded("422 rejected")
        return {"booked": [{"transactionId": f"{account_id}-{date_from}"}], "pending": []}


async def test_fallback_uses_smaller_window_when_default_rejected() -> None:
    mgr = _bare_manager()
    # Accept only windows starting within ~30 days. The 90-day window is
    # rejected, the 30-day fallback succeeds.
    accept_from = (dt_util.now() - timedelta(days=31)).strftime("%Y-%m-%d")
    client = _FakeClient(accept_from=accept_from)
    date_to = dt_util.now().strftime("%Y-%m-%d")

    txns, used_from = await mgr._fetch_account_txns_with_fallback(
        client, "acc", days=90, date_to=date_to
    )

    assert len(client.calls) == 2, "should try 90 then fall back to 30"
    assert txns["booked"], "fallback window should return data"
    # used_from corresponds to the 30-day window that succeeded
    assert used_from == client.calls[-1]


async def test_fallback_raises_when_all_windows_rejected() -> None:
    mgr = _bare_manager()
    client = _FakeClient(accept_from="9999-01-01")  # reject everything

    date_to = dt_util.now().strftime("%Y-%m-%d")
    with pytest.raises(TransactionPeriodExceeded):
        await mgr._fetch_account_txns_with_fallback(
            client, "acc", days=90, date_to=date_to
        )
    # 90 + the two TX_FALLBACK_WINDOWS (30, 7) = 3 attempts
    assert len(client.calls) == 3


async def test_no_fallback_attempt_when_first_window_succeeds() -> None:
    mgr = _bare_manager()
    client = _FakeClient(accept_from=None)  # accept anything

    date_to = dt_util.now().strftime("%Y-%m-%d")
    txns, _used_from = await mgr._fetch_account_txns_with_fallback(
        client, "acc", days=90, date_to=date_to
    )
    assert len(client.calls) == 1, "no fallback needed when first window works"
    assert txns["booked"]


# ---------------------------------------------------------------------------
# Fix 2 helper — _ingest_account_txns tagging + historical merge
# ---------------------------------------------------------------------------


def test_ingest_tags_and_keeps_historical_outside_window() -> None:
    mgr = _bare_manager()
    mgr._categorizer = None  # forces "other" fallback, no init needed

    date_from = (dt_util.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    older = (dt_util.now() - timedelta(days=200)).strftime("%Y-%m-%d")
    inside = dt_util.now().strftime("%Y-%m-%d")

    # Seed a historical booked txn older than the window — must be preserved.
    mgr._tx_by_account = {
        "acc": [
            {
                "transactionId": "old-1",
                "_status": "booked",
                "bookingDate": older,
            }
        ]
    }

    txns = {
        "booked": [{"transactionId": "new-1", "bookingDate": inside}],
        "pending": [{"transactionId": "pend-1", "bookingDate": inside}],
    }
    account = {"id": "acc", "custom_name": "My Acct", "type": "personal"}

    mgr._ingest_account_txns(account, "acc", txns, date_from)

    result = mgr._tx_by_account["acc"]
    ids = {t["transactionId"] for t in result}
    assert ids == {"old-1", "new-1", "pend-1"}, "historical txn must be kept"
    new = next(t for t in result if t["transactionId"] == "new-1")
    assert new["_account_name"] == "My Acct"
    assert new["category"] == "other"
    assert new["_status"] == "booked"


# ---------------------------------------------------------------------------
# Per-account last-successful-refresh tracking
# ---------------------------------------------------------------------------


def test_last_success_dates_scoped_to_linked_accounts() -> None:
    """Only linked accounts appear; a never-refreshed account maps to None."""
    mgr = _bare_manager()
    mgr._accounts = [{"id": "acc-ok"}, {"id": "acc-stale"}]
    ts = dt_util.now().isoformat()
    # acc-ok refreshed; acc-stale never did; acc-gone is stale residue and
    # must not leak into the result once it is no longer linked.
    mgr._last_success_by_account = {"acc-ok": ts, "acc-gone": ts}

    result = mgr.get_last_success_dates()

    assert result == {"acc-ok": ts, "acc-stale": None}
    assert "acc-gone" not in result


def test_backfill_seeds_missing_map_from_global_refresh() -> None:
    """Pre-feature caches: seed accounts holding tx from the global last_refresh."""
    mgr = _bare_manager()
    mgr._last_success_by_account = {}
    mgr._last_refresh = dt_util.now()
    mgr._tx_by_account = {
        "acc-a": [{"transactionId": "1"}],
        "acc-empty": [],  # no cached tx → not seeded
        "__unknown__": [{"transactionId": "2"}],  # migration bucket → skipped
    }

    mgr._backfill_last_success_from_global()

    iso = mgr._last_refresh.isoformat()
    assert mgr._last_success_by_account == {"acc-a": iso}


def test_backfill_no_op_when_map_already_populated() -> None:
    """An existing per-account map is authoritative — backfill must not touch it."""
    mgr = _bare_manager()
    existing = {"acc-a": "2026-01-01T00:00:00+00:00"}
    mgr._last_success_by_account = dict(existing)
    mgr._last_refresh = dt_util.now()
    mgr._tx_by_account = {"acc-a": [{"transactionId": "1"}], "acc-b": [{"transactionId": "2"}]}

    mgr._backfill_last_success_from_global()

    assert mgr._last_success_by_account == existing


# ---------------------------------------------------------------------------
# Per-account error classification + surfacing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("message", "expected"),
    [
        ('401 {"error":"EXPIRED_SESSION","message":"Session is expired"}', "session_expired"),
        ("Session is expired", "session_expired"),
        ('401 {"error":"INVALID_SESSION"}', "auth_error"),
        ("500 internal server error", "error"),
    ],
)
def test_classify_account_error(message: str, expected: str) -> None:
    assert FinanceDashboardManager._classify_account_error(Exception(message)) == expected


def test_get_account_errors_scoped_and_typed() -> None:
    """Only linked accounts surface; success on an account clears its error."""
    mgr = _bare_manager()
    mgr._accounts = [{"id": "acc-bad"}, {"id": "acc-ok"}]
    mgr._last_error_by_account = {}
    mgr._record_account_error("acc-bad", "session_expired", "Session is expired")
    # Residue from an unlinked account must not leak into the scoped view.
    mgr._record_account_error("acc-gone", "error", "boom")

    errors = mgr.get_account_errors()

    assert set(errors) == {"acc-bad"}
    assert errors["acc-bad"]["type"] == "session_expired"
    assert "at" in errors["acc-bad"]


# ---------------------------------------------------------------------------
# Re-link history preservation — re-key cached data onto fresh account ids
# ---------------------------------------------------------------------------


async def test_remap_account_ids_moves_history_and_state() -> None:
    """Re-keying migrates tx bucket (re-tagged), balances and per-account state."""
    mgr = _bare_manager()
    mgr._demo_mode = False
    mgr._tx_by_account = {
        "old": [
            {"transactionId": "t1", "_account_id": "old", "bookingDate": "2026-03-01"},
        ],
        "other-bank": [{"transactionId": "z", "_account_id": "other-bank"}],
    }
    mgr._balances = {"old": {"balances": []}}
    mgr._previous_balances = {"old": 12.5}
    mgr._last_success_by_account = {"old": "2026-07-01T00:00:00+00:00"}
    mgr._last_error_by_account = {"old": {"type": "session_expired"}}

    persisted: list[bool] = []

    async def _fake_persist() -> None:
        persisted.append(True)

    mgr._persist_transactions = _fake_persist  # type: ignore[method-assign]

    migrated = await mgr.async_remap_account_ids({"old": "new", "": "x", "same": "same"})

    assert migrated == 1
    assert "old" not in mgr._tx_by_account
    assert mgr._tx_by_account["new"][0]["_account_id"] == "new"
    assert mgr._tx_by_account["new"][0]["transactionId"] == "t1"
    assert mgr._balances == {"new": {"balances": []}}
    assert mgr._previous_balances == {"new": 12.5}
    assert mgr._last_success_by_account == {"new": "2026-07-01T00:00:00+00:00"}
    assert mgr._last_error_by_account == {"new": {"type": "session_expired"}}
    assert mgr._tx_by_account["other-bank"], "untouched banks must be preserved"
    assert persisted == [True]


async def test_remap_account_ids_noop_when_nothing_to_move() -> None:
    """No cached bucket for the old id → no migration, no persist."""
    mgr = _bare_manager()
    mgr._tx_by_account = {}
    mgr._balances = {}
    mgr._previous_balances = {}
    mgr._last_success_by_account = {}
    mgr._last_error_by_account = {}

    async def _fail_persist() -> None:  # pragma: no cover - must not run
        raise AssertionError("persist must not be called when nothing moved")

    mgr._persist_transactions = _fail_persist  # type: ignore[method-assign]

    migrated = await mgr.async_remap_account_ids({"old": "new"})

    assert migrated == 0
