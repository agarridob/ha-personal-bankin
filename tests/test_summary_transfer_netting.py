"""End-to-end: internal transfers net to zero in the monthly summary.

Proves that a transfer between two of the user's own connected accounts no
longer inflates total_expenses — both legs are excluded — while a real
expense in the same cycle is still counted.
"""

from __future__ import annotations

from datetime import date
from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.finance_dashboard.categorizer import TransactionCategorizer
from custom_components.finance_dashboard.manager import FinanceDashboardManager
from custom_components.finance_dashboard.transfer_detector import (
    detect_transfer_chains,
    enrich_transactions,
)


def _make_manager(accounts: list[dict]) -> FinanceDashboardManager:
    hass = MagicMock()
    hass.data = {}
    hass.states.get.return_value = None  # no budget Number entities
    entry = MagicMock()
    entry.data = {"accounts": accounts}
    entry.options = {}
    mgr = FinanceDashboardManager(hass, entry)
    mgr._custom_rules_store = AsyncMock()
    mgr._transaction_store = AsyncMock()
    mgr._categorizer = TransactionCategorizer()
    mgr._accounts = accounts
    return mgr


def _txn(
    txn_id: str,
    account_id: str,
    amount: float,
    booking: str,
    category: str,
    creditor: str = "",
    debtor: str = "",
    account_name: str = "",
) -> dict:
    return {
        "transactionId": txn_id,
        "_account_id": account_id,
        "_account_name": account_name,
        "_status": "booked",
        "bookingDate": booking,
        "category": category,
        "creditorName": creditor,
        "debtorName": debtor,
        "transactionAmount": {"amount": str(amount), "currency": "EUR"},
    }


@pytest.mark.asyncio
async def test_internal_transfer_excluded_from_expenses():
    """-1000 from account A / +1000 into account B nets to zero in GASTOS."""
    today = date.today()
    day = today.replace(day=15).isoformat()  # mid-cycle, always in range

    accounts = [
        {"id": "acc-a", "name": "Cuenta Corriente"},
        {"id": "acc-b", "name": "Cuenta Comun"},
    ]
    txns = [
        # Internal transfer A → B (both owned)
        _txn(
            "tr-out",
            "acc-a",
            -1000.00,
            day,
            "transfers",
            creditor="Cuenta Comun",
            account_name="Cuenta Corriente",
        ),
        _txn(
            "tr-in",
            "acc-b",
            1000.00,
            day,
            "transfers",
            debtor="Cuenta Corriente",
            account_name="Cuenta Comun",
        ),
        # A real expense in the same cycle
        _txn("exp-1", "acc-a", -200.00, day, "groceries", creditor="Mercadona"),
    ]
    chains, refunds = detect_transfer_chains(txns, accounts)
    enrich_transactions(txns, chains, refunds)

    mgr = _make_manager(accounts)
    mgr._transactions = txns

    summary = await mgr.async_get_monthly_summary(today.month, today.year)

    # The transfer nets to zero: only the 200 groceries expense counts
    assert summary["total_expenses"] == 200.00
    assert summary["total_income"] == 0.00
    # Transfers category must not appear (both legs excluded)
    assert "transfers" not in summary["categories"]
    assert summary["categories"] == {"groceries": -200.00}
    # Transparency: one excluded chain, value counted once (the outflow)
    assert summary["excluded_transfers"]["chain_count"] == 1
    assert summary["excluded_transfers"]["excluded_amount"] == 1000.00
    assert summary["excluded_transfers"]["excluded_txn_count"] == 2


@pytest.mark.asyncio
async def test_rejected_internal_transfer_counts_again():
    """If the user rejects the detected chain, both legs count as normal."""
    today = date.today()
    day = today.replace(day=15).isoformat()

    accounts = [
        {"id": "acc-a", "name": "Cuenta Corriente"},
        {"id": "acc-b", "name": "Cuenta Comun"},
    ]
    txns = [
        _txn(
            "tr-out",
            "acc-a",
            -1000.00,
            day,
            "transfers",
            creditor="Cuenta Comun",
            account_name="Cuenta Corriente",
        ),
        _txn(
            "tr-in",
            "acc-b",
            1000.00,
            day,
            "transfers",
            debtor="Cuenta Corriente",
            account_name="Cuenta Comun",
        ),
    ]
    chains, refunds = detect_transfer_chains(txns, accounts)
    enrich_transactions(txns, chains, refunds)
    # User rejects the chain → treated as independent transactions
    for t in txns:
        t["_transfer_confirmed"] = False

    mgr = _make_manager(accounts)
    mgr._transactions = txns

    summary = await mgr.async_get_monthly_summary(today.month, today.year)

    # Both legs count again
    assert summary["total_expenses"] == 1000.00
    assert summary["total_income"] == 1000.00
    assert summary["categories"]["transfers"] == 0.00
