"""get_cached_transactions: the /transactions endpoint must be able to serve
the full cached history (bounded by HISTORY_RETENTION_MONTHS), not just the
first 100 rows — otherwise date-filtering in the panel can't reach older
transactions.
"""

from __future__ import annotations

from custom_components.finance_dashboard.manager import FinanceDashboardManager


def _bare_manager(n: int) -> FinanceDashboardManager:
    mgr = object.__new__(FinanceDashboardManager)
    mgr._transactions = [{"transactionId": str(i)} for i in range(n)]
    return mgr


def test_default_returns_all_transactions() -> None:
    mgr = _bare_manager(250)
    result = mgr.get_cached_transactions()
    assert len(result) == 250, "default (limit=None) must return the full cache"


def test_explicit_limit_caps_the_result() -> None:
    mgr = _bare_manager(250)
    result = mgr.get_cached_transactions(limit=100)
    assert len(result) == 100
    assert [t["transactionId"] for t in result] == [str(i) for i in range(100)]


def test_returns_a_copy_not_the_internal_list() -> None:
    mgr = _bare_manager(5)
    result = mgr.get_cached_transactions()
    result.append({"transactionId": "injected"})
    assert len(mgr._transactions) == 5, "caller must not mutate the cache"
