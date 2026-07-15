"""Transaction auto-categorizer.

Uses rule-based pattern matching to classify banking transactions
into budget categories. Users can customize rules via the UI.

No ML/AI dependencies — pure keyword matching for reliability and
transparency. Categories are deterministic and auditable.

Rules are direction-aware: a keyword may be scoped to credits (money in),
debits (money out), or either. This lets the same text resolve to
different categories depending on the sign — e.g. a person's name that
appears on both an incoming salary (credit → income) and an outgoing
transfer to their own untracked account (debit → excluded).
"""

from __future__ import annotations

import logging
from typing import Any

from .const import (
    CATEGORIZATION_RULES,
    CATEGORY_OTHER,
    CREDIT_ONLY_CATEGORIES,
    RULE_DIRECTION_ANY,
    RULE_DIRECTION_CREDIT,
    RULE_DIRECTION_DEBIT,
    RULE_DIRECTIONS,
)

_LOGGER = logging.getLogger(__name__)


def _normalize_rule(entry: Any) -> tuple[str, str] | None:
    """Normalize a stored rule entry to a (keyword, direction) tuple.

    Backwards-compatible: a plain string is treated as an any-direction
    keyword. A dict must carry a "keyword"; its "direction" defaults to
    "any" and is coerced to a valid value.
    """
    if isinstance(entry, str):
        keyword = entry.strip().lower()
        return (keyword, RULE_DIRECTION_ANY) if keyword else None
    if isinstance(entry, dict):
        keyword = str(entry.get("keyword", "")).strip().lower()
        if not keyword:
            return None
        direction = str(entry.get("direction", RULE_DIRECTION_ANY)).strip().lower()
        if direction not in RULE_DIRECTIONS:
            direction = RULE_DIRECTION_ANY
        return (keyword, direction)
    return None


def _direction_matches(direction: str, amount: float) -> bool:
    """Return True if a rule's direction is compatible with the amount sign."""
    if direction == RULE_DIRECTION_CREDIT:
        return amount > 0
    if direction == RULE_DIRECTION_DEBIT:
        return amount < 0
    return True


class TransactionCategorizer:
    """Categorize banking transactions by keyword matching."""

    def __init__(self, custom_rules: dict[str, list[Any]] | None = None) -> None:
        """Initialize with default + optional custom rules.

        Rules are stored as {category: [(keyword, direction), ...]}. Custom
        entries may be plain strings (any direction) or dicts with an explicit
        direction; both are normalized here.
        """
        self._rules: dict[str, list[tuple[str, str]]] = {
            category: [r for kw in keywords if (r := _normalize_rule(kw))]
            for category, keywords in CATEGORIZATION_RULES.items()
        }
        if custom_rules:
            for category, entries in custom_rules.items():
                normalized = [r for e in entries if (r := _normalize_rule(e))]
                if not normalized:
                    continue
                existing = self._rules.setdefault(category, [])
                for rule in normalized:
                    if rule not in existing:
                        existing.append(rule)

    def categorize(self, transaction: dict[str, Any]) -> str:
        """Categorize a single transaction.

        Checks remittance info, creditor name, and debtor name against
        keyword patterns, honoring each rule's direction scope. A keyword
        resolving to a credit-only category (e.g. income) never tags a debit.

        Args:
            transaction: Transaction object (normalized format)

        Returns:
            Category string (e.g., 'housing', 'dining', 'income')
        """
        # Extract searchable text from transaction
        search_text = self._extract_searchable_text(transaction)
        if not search_text:
            return CATEGORY_OTHER

        search_lower = search_text.lower()

        # Amount direction drives sign-scoped matching and the income fallback
        amount = float(transaction.get("transactionAmount", {}).get("amount", 0))

        # Match against rules
        for category, rules in self._rules.items():
            credit_only = category in CREDIT_ONLY_CATEGORIES
            for keyword, direction in rules:
                if keyword not in search_lower:
                    continue
                if not _direction_matches(direction, amount):
                    continue
                # A credit-only category must never absorb a debit
                if credit_only and amount <= 0:
                    continue
                return category

        # Fallback: positive amounts without category → income
        if amount > 0:
            return "income"

        return CATEGORY_OTHER

    def update_rules(self, category: str, keywords: list[Any]) -> None:
        """Add or update categorization rules for a category."""
        normalized = [r for kw in keywords if (r := _normalize_rule(kw))]
        existing = self._rules.setdefault(category, [])
        for rule in normalized:
            if rule not in existing:
                existing.append(rule)

    def get_rules(self) -> dict[str, list[tuple[str, str]]]:
        """Get current categorization rules (deep copy — mutations are safe)."""
        return {category: list(rules) for category, rules in self._rules.items()}

    @staticmethod
    def _extract_searchable_text(
        transaction: dict[str, Any],
    ) -> str:
        """Extract all searchable text fields from a transaction."""
        parts = []

        # Remittance information (payment reference)
        remittance = transaction.get("remittanceInformationUnstructured", "")
        if remittance:
            parts.append(remittance)

        remittance_array = transaction.get("remittanceInformationUnstructuredArray", [])
        if remittance_array:
            parts.extend(remittance_array)

        # Creditor (who receives money)
        creditor = transaction.get("creditorName", "")
        if creditor:
            parts.append(creditor)

        # Debtor (who sends money)
        debtor = transaction.get("debtorName", "")
        if debtor:
            parts.append(debtor)

        # Additional info
        additional = transaction.get("additionalInformation", "")
        if additional:
            parts.append(additional)

        return " ".join(parts)
