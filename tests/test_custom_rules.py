"""Custom categorization rules — persistence and live re-categorization.

Covers the manager-level add/remove rule flow: keywords are persisted via
the Store, the categorizer is rebuilt, and cached transactions are
re-categorized immediately.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from custom_components.finance_dashboard.categorizer import TransactionCategorizer
from custom_components.finance_dashboard.manager import FinanceDashboardManager

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_manager() -> FinanceDashboardManager:
    hass = MagicMock()
    hass.data = {}
    entry = MagicMock()
    entry.data = {"accounts": []}
    entry.options = {}
    mgr = FinanceDashboardManager(hass, entry)
    mgr._custom_rules_store = AsyncMock()
    mgr._transaction_store = AsyncMock()
    mgr._categorizer = TransactionCategorizer()
    return mgr


def _txn(creditor: str, amount: str = "-10.00") -> dict:
    return {
        "creditorName": creditor,
        "transactionAmount": {"amount": amount},
    }


# ---------------------------------------------------------------------------
# Categorizer-level: custom rules merge with defaults
# ---------------------------------------------------------------------------


def test_custom_rules_extend_defaults():
    # A user-defined category key ("food") still works as a custom alias.
    cat = TransactionCategorizer(custom_rules={"food": ["la tahona"]})
    assert cat.categorize(_txn("Panaderia La Tahona")) == "food"
    # Built-in rules still apply — supermarkets resolve to the groceries category.
    assert cat.categorize(_txn("MERCADONA SA")) == "groceries"


def test_custom_rules_new_category():
    cat = TransactionCategorizer(custom_rules={"fitness": ["basic-fit"]})
    assert cat.categorize(_txn("Basic-Fit Spain SAU")) == "fitness"


# ---------------------------------------------------------------------------
# Manager-level: add rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_rule_persists_and_recategorizes():
    mgr = _make_manager()
    mgr._transactions = [_txn("Panaderia La Tahona")]

    result = await mgr.async_add_categorization_rule("food", "La Tahona")

    # Keyword stored lowercase
    assert mgr.get_custom_rules() == {"food": ["la tahona"]}
    mgr._custom_rules_store.async_save.assert_awaited_once_with({"food": ["la tahona"]})
    # Cached transaction re-categorized and persisted
    assert mgr._transactions[0]["category"] == "food"
    mgr._transaction_store.async_save.assert_awaited()
    # Service response payload
    assert result == {"custom_rules": {"food": ["la tahona"]}}


@pytest.mark.asyncio
async def test_add_rule_duplicate_is_noop():
    mgr = _make_manager()
    await mgr.async_add_categorization_rule("food", "la tahona")
    mgr._custom_rules_store.async_save.reset_mock()

    await mgr.async_add_categorization_rule("food", "LA TAHONA")

    assert mgr.get_custom_rules() == {"food": ["la tahona"]}
    mgr._custom_rules_store.async_save.assert_not_awaited()


@pytest.mark.asyncio
async def test_add_rule_empty_raises():
    mgr = _make_manager()
    with pytest.raises(ValueError):
        await mgr.async_add_categorization_rule("food", "   ")


# ---------------------------------------------------------------------------
# Manager-level: remove rule
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_rule_restores_default_categorization():
    mgr = _make_manager()
    mgr._transactions = [_txn("Panaderia La Tahona")]
    await mgr.async_add_categorization_rule("subscriptions", "la tahona")
    assert mgr._transactions[0]["category"] == "subscriptions"

    await mgr.async_remove_categorization_rule("subscriptions", "la tahona")

    assert mgr.get_custom_rules() == {}
    # Without the custom keyword the txn falls back to "other"
    assert mgr._transactions[0]["category"] == "other"


@pytest.mark.asyncio
async def test_remove_unknown_rule_is_noop():
    mgr = _make_manager()
    mgr._custom_rules_store.async_save.reset_mock()

    result = await mgr.async_remove_categorization_rule("food", "inexistente")

    mgr._custom_rules_store.async_save.assert_not_awaited()
    assert result == {"custom_rules": {}}


@pytest.mark.asyncio
async def test_remove_does_not_affect_builtin_rules():
    mgr = _make_manager()
    mgr._transactions = [_txn("MERCADONA SA")]

    await mgr.async_remove_categorization_rule("groceries", "mercadona")

    # Built-in keyword still matches — removal only targets custom rules
    mgr._categorizer = TransactionCategorizer(custom_rules=mgr.get_custom_rules() or None)
    assert mgr._categorizer.categorize(mgr._transactions[0]) == "groceries"


# ---------------------------------------------------------------------------
# Manager-level: direction-scoped rules
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_debit_rule_stored_as_dict_and_splits_sign():
    """A debit-scoped rule persists as a dict and only tags debits."""
    mgr = _make_manager()
    mgr._transactions = [
        _txn("MARIANA MOURA", amount="1600.00"),
        _txn("MARIANA MOURA", amount="-1000.00"),
    ]

    result = await mgr.async_add_categorization_rule("excluded", "Mariana Moura", "debit")

    # Direction-scoped rule stored as a structured dict
    assert mgr.get_custom_rules() == {
        "excluded": [{"keyword": "mariana moura", "direction": "debit"}]
    }
    mgr._custom_rules_store.async_save.assert_awaited_once_with(
        {"excluded": [{"keyword": "mariana moura", "direction": "debit"}]}
    )
    # +1600 stays income, -1000 becomes excluded
    assert mgr._transactions[0]["category"] == "income"
    assert mgr._transactions[1]["category"] == "excluded"
    assert result == {
        "custom_rules": {"excluded": [{"keyword": "mariana moura", "direction": "debit"}]}
    }


@pytest.mark.asyncio
async def test_any_direction_still_stored_as_plain_string():
    """Any-direction rules keep the legacy plain-string on-disk shape."""
    mgr = _make_manager()

    await mgr.async_add_categorization_rule("dining", "Bar Pepe")

    assert mgr.get_custom_rules() == {"dining": ["bar pepe"]}


@pytest.mark.asyncio
async def test_credit_and_debit_rules_coexist_for_same_keyword():
    """The same keyword can carry both a credit and a debit rule."""
    mgr = _make_manager()

    await mgr.async_add_categorization_rule("income", "acme", "credit")
    await mgr.async_add_categorization_rule("excluded", "acme", "debit")

    assert mgr.get_custom_rules() == {
        "income": [{"keyword": "acme", "direction": "credit"}],
        "excluded": [{"keyword": "acme", "direction": "debit"}],
    }


@pytest.mark.asyncio
async def test_remove_debit_rule_requires_matching_direction():
    """Removing needs the direction to match; a bare removal misses it."""
    mgr = _make_manager()
    await mgr.async_add_categorization_rule("excluded", "mariana moura", "debit")
    mgr._custom_rules_store.async_save.reset_mock()

    # Wrong direction (default 'any') → no-op
    await mgr.async_remove_categorization_rule("excluded", "mariana moura")
    mgr._custom_rules_store.async_save.assert_not_awaited()
    assert mgr.get_custom_rules() == {
        "excluded": [{"keyword": "mariana moura", "direction": "debit"}]
    }

    # Matching direction → removed
    await mgr.async_remove_categorization_rule("excluded", "mariana moura", "debit")
    assert mgr.get_custom_rules() == {}
