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
