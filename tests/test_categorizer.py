"""Parametrized tests for TransactionCategorizer rule coverage (T4).

Tests all 9 rule categories plus income detection and custom-rule injection.
Each category is exercised with multiple real-world merchant / reference
patterns that a German household would encounter.
"""

from __future__ import annotations

import pytest

from custom_components.finance_dashboard.categorizer import (
    TransactionCategorizer,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _txn(
    creditor: str = "",
    remittance: str = "",
    amount: float = -10.00,
    debtor: str = "",
    additional: str = "",
) -> dict:
    """Build a minimal transaction dict."""
    txn: dict = {
        "transactionAmount": {"amount": str(amount), "currency": "EUR"},
    }
    if creditor:
        txn["creditorName"] = creditor
    if remittance:
        txn["remittanceInformationUnstructured"] = remittance
    if debtor:
        txn["debtorName"] = debtor
    if additional:
        txn["additionalInformation"] = additional
    return txn


# ---------------------------------------------------------------------------
# Housing
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("remittance", "Alquiler diciembre 2025 piso calle Mayor"),
        ("remittance", "Recibo hipoteca cuota noviembre"),
        ("creditor", "Comunidad de Propietarios Avda Galicia 12"),
        ("remittance", "CDAD COMUNIDAD PROP CUOTA TRIMESTRE"),
        ("remittance", "ALQUILER GARAJE ENERO"),
        ("creditor", "Rent payment apartment Zamora"),
    ],
)
def test_housing(field, value):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == "housing", f"Expected housing for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Food — split into groceries (supermarkets) and dining (restaurants/delivery)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value,expected",
    [
        ("creditor", "MERCADONA SA", "groceries"),
        ("creditor", "Carrefour Express", "groceries"),
        ("creditor", "ALDI San Roque", "groceries"),
        ("creditor", "Lidl Supermercados SAU", "groceries"),
        ("creditor", "EROSKI City", "groceries"),
        ("remittance", "Compra supermercado semanal", "groceries"),
        ("creditor", "ALCAMPO SA", "groceries"),
        ("creditor", "Glovoapp23 SL", "dining"),
        ("remittance", "Restaurante Casa Pepe mesa 4", "dining"),
        ("remittance", "Uber Eats Madrid", "dining"),
    ],
)
def test_food(field, value, expected):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == expected, f"Expected {expected} for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Transport
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("creditor", "RENFE Viajeros SME SA"),
        ("creditor", "ALSA Grupo SLU"),
        ("remittance", "Cabify viaje 12/03"),
        ("creditor", "REPSOL Estacion de Servicio"),
        ("creditor", "CEPSA Gasolinera A-52"),
        ("creditor", "Uber BV"),
        ("remittance", "Taxi aeropuerto"),
        ("remittance", "Peaje autopista AP-6"),
    ],
)
def test_transport(field, value):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == "transport", f"Expected transport for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Insurance
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("creditor", "MAPFRE España"),
        ("creditor", "Linea Directa Aseguradora"),
        ("creditor", "SegurCaixa Adeslas"),
        ("remittance", "Recibo seguro hogar anual"),
        ("remittance", "SEGURO COCHE SEMESTRE"),
        ("creditor", "Sanitas SA de Seguros"),
        ("creditor", "Allianz Seguros"),
    ],
)
def test_insurance(field, value):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == "insurance", f"Expected insurance for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Subscriptions
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("creditor", "Netflix International BV"),
        ("creditor", "Spotify AB"),
        ("remittance", "Amazon Prime suscripcion"),
        ("creditor", "Disney Plus"),
        ("remittance", "Xbox Game Pass Ultimate"),
        ("remittance", "Google One 200GB"),
        ("remittance", "iCloud almacenamiento"),
        ("remittance", "YouTube Premium mensual"),
        ("creditor", "HBO Max"),
        ("creditor", "DAZN Limited"),
        ("remittance", "APPLE.COM/BILL"),
        ("remittance", "Movistar Plus+ cuota"),
    ],
)
def test_subscriptions(field, value):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == "subscriptions", f"Expected subscriptions for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Loans
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("remittance", "Prestamo personal cuota enero"),
        ("remittance", "AMORTIZACION ANTICIPADA PRESTAMO"),
        ("remittance", "Financiacion vehiculo cuota 14/48"),
        ("remittance", "Loan repayment"),
        ("remittance", "COFIDIS RECIBO MENSUAL"),
    ],
)
def test_loans(field, value):
    cat = TransactionCategorizer()
    result = cat.categorize(_txn(remittance=value))
    assert result == "loans", f"Expected loans for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("creditor", "IBERDROLA CLIENTES SAU"),
        ("creditor", "ENDESA ENERGIA XXI"),
        ("creditor", "NATURGY IBERIA SA"),
        ("creditor", "AQUALIA GESTION AGUA"),
        ("creditor", "Telefonica de España"),
        ("creditor", "Vodafone España SAU"),
        ("creditor", "O2 fibra y movil"),
        ("creditor", "Orange Espagne SAU"),
        ("creditor", "PEPEPHONE"),
        ("remittance", "Recibo Movistar fibra octubre"),
    ],
)
def test_utilities(field, value):
    cat = TransactionCategorizer()
    if field == "creditor":
        result = cat.categorize(_txn(creditor=value))
    else:
        result = cat.categorize(_txn(remittance=value))
    assert result == "utilities", f"Expected utilities for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Income (keyword-based)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("remittance", "NOMINA NOVIEMBRE 2025 EMPRESA SL"),
        ("remittance", "Nómina diciembre"),
        ("remittance", "Salary payment"),
        ("remittance", "Salario octubre"),
        ("remittance", "PENSION SEGURIDAD SOC"),
    ],
)
def test_income_keyword(field, value):
    """Income keywords on a credit (positive amount) → income."""
    cat = TransactionCategorizer()
    result = cat.categorize(_txn(remittance=value, amount=1234.56))
    assert result == "income", f"Expected income for '{value}', got '{result}'"


@pytest.mark.parametrize(
    "field,value",
    [
        ("remittance", "NOMINA NOVIEMBRE 2025 EMPRESA SL"),
        ("remittance", "Salary payment"),
        ("remittance", "PENSION SEGURIDAD SOC"),
    ],
)
def test_income_keyword_never_tags_debit(field, value):
    """Income is credit-only: an income keyword on a debit must NOT be income.

    A negative amount is never income even if it carries a salary/pension
    keyword; it falls through to the debit fallback (other).
    """
    cat = TransactionCategorizer()
    result = cat.categorize(_txn(remittance=value, amount=-0.01))
    assert result == "other", f"Expected other (debit) for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Income (positive amount fallback)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "amount,label",
    [
        (500.00, "standard deposit"),
        (0.01, "micro deposit"),
        (9999.99, "large transfer"),
    ],
)
def test_income_positive_amount_fallback(amount, label):
    """Transactions with no matching keyword but positive amount → income."""
    cat = TransactionCategorizer()
    # Use an unrecognized creditor to avoid keyword matches
    result = cat.categorize(_txn(creditor="Remitente Desconocido XYZ", amount=amount))
    assert result == "income", f"Expected income for {label} (amount={amount}), got '{result}'"


# ---------------------------------------------------------------------------
# Transfers
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field,value",
    [
        ("remittance", "TRANSFERENCIA A CUENTA AHORRO"),
        ("remittance", "Traspaso entre cuentas"),
        ("remittance", "Transfer to savings account"),
        ("remittance", "BIZUM ENVIADO A MARIA"),
    ],
)
def test_transfers(field, value):
    cat = TransactionCategorizer()
    result = cat.categorize(_txn(remittance=value))
    assert result == "transfers", f"Expected transfers for '{value}', got '{result}'"


# ---------------------------------------------------------------------------
# Other (fallback)
# ---------------------------------------------------------------------------


def test_other_fallback_negative_amount():
    """Transactions with no matching keyword and negative amount → other."""
    cat = TransactionCategorizer()
    result = cat.categorize(
        _txn(
            creditor="Completely Unknown Merchant XYZXYZ",
            remittance="REF 12345678",
            amount=-50.00,
        )
    )
    assert result == "other"


def test_other_empty_transaction():
    """An entirely empty transaction dict → other."""
    cat = TransactionCategorizer()
    result = cat.categorize({})
    assert result == "other"


def test_other_no_text_fields():
    """Transaction with only an amount field and no text → other (negative amount)."""
    cat = TransactionCategorizer()
    result = cat.categorize({"transactionAmount": {"amount": "-1.00"}})
    assert result == "other"


# ---------------------------------------------------------------------------
# Custom rules
# ---------------------------------------------------------------------------


def test_custom_rule_adds_keyword():
    """Custom rules injected via constructor must extend category matching."""
    cat = TransactionCategorizer(custom_rules={"food": ["biomarkt", "demeter"]})
    result = cat.categorize(_txn(creditor="Alnatura Biomarkt"))
    assert result == "food"


def test_custom_rule_new_category():
    """Custom rules for a previously-unseen category key must work."""
    cat = TransactionCategorizer(custom_rules={"fitness": ["fitnessstudio", "mcfit", "clever fit"]})
    result = cat.categorize(_txn(creditor="McFit GmbH"))
    assert result == "fitness"


def test_update_rules_adds_keyword():
    """update_rules must extend matching for an existing category."""
    cat = TransactionCategorizer()
    cat.update_rules("food", ["naschmarkt"])
    result = cat.categorize(_txn(creditor="Naschmarkt Wien"))
    assert result == "food"


def test_get_rules_returns_copy():
    """get_rules() must return a copy — mutations must not affect the instance."""
    cat = TransactionCategorizer()
    rules = cat.get_rules()
    rules["groceries"].append("__sentinel__")
    # Internal rules must not be polluted
    assert "__sentinel__" not in cat.get_rules()["groceries"]


# ---------------------------------------------------------------------------
# Direction-aware custom rules (sign-scoped)
# ---------------------------------------------------------------------------


def test_debit_rule_ignores_credit():
    """A debit-scoped rule must not match a positive (credit) amount."""
    cat = TransactionCategorizer(
        custom_rules={"excluded": [{"keyword": "mariana moura", "direction": "debit"}]}
    )
    # Positive amount → the debit rule is skipped → positive fallback → income
    result = cat.categorize(_txn(creditor="MARIANA MOURA", amount=1600.0))
    assert result == "income"


def test_debit_rule_matches_debit():
    """A debit-scoped rule matches a negative (debit) amount."""
    cat = TransactionCategorizer(
        custom_rules={"excluded": [{"keyword": "mariana moura", "direction": "debit"}]}
    )
    result = cat.categorize(_txn(creditor="MARIANA MOURA", amount=-1000.0))
    assert result == "excluded"


def test_credit_rule_ignores_debit():
    """A credit-scoped rule must not match a negative (debit) amount."""
    cat = TransactionCategorizer(
        custom_rules={"income": [{"keyword": "acme corp", "direction": "credit"}]}
    )
    result = cat.categorize(_txn(creditor="ACME CORP", amount=-50.0))
    # Debit + no other match → debit fallback → other
    assert result == "other"


def test_any_direction_string_rule_matches_both_signs():
    """A plain-string custom rule (any direction) matches both signs."""
    cat = TransactionCategorizer(custom_rules={"dining": ["pizzeria roma"]})
    assert cat.categorize(_txn(creditor="Pizzeria Roma", amount=-20.0)) == "dining"
    assert cat.categorize(_txn(creditor="Pizzeria Roma", amount=20.0)) == "dining"


def test_mariana_scenario_splits_by_sign():
    """The end-to-end Mariana case: same name, opposite signs, split cleanly.

    +1600 salary → income (positive fallback); -1000 transfer to her own
    untracked account → excluded via a debit-scoped rule. Neither leaks into
    the other bucket.
    """
    cat = TransactionCategorizer(
        custom_rules={"excluded": [{"keyword": "mariana moura", "direction": "debit"}]}
    )
    assert cat.categorize(_txn(creditor="MARIANA MOURA", amount=1600.0)) == "income"
    assert cat.categorize(_txn(creditor="MARIANA MOURA", amount=-1000.0)) == "excluded"


def test_invalid_direction_falls_back_to_any():
    """An unknown direction value is coerced to 'any' (matches both signs)."""
    cat = TransactionCategorizer(
        custom_rules={"dining": [{"keyword": "bar pepe", "direction": "sideways"}]}
    )
    assert cat.categorize(_txn(creditor="Bar Pepe", amount=-10.0)) == "dining"
    assert cat.categorize(_txn(creditor="Bar Pepe", amount=10.0)) == "dining"


def test_malformed_rule_entries_ignored():
    """Entries without a keyword are dropped, not crash categorization."""
    cat = TransactionCategorizer(
        custom_rules={"dining": [{"direction": "debit"}, "", {"keyword": "  "}, "sushi"]}
    )
    assert cat.categorize(_txn(creditor="Sushi Bar", amount=-10.0)) == "dining"


# ---------------------------------------------------------------------------
# Case-insensitivity
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    [
        "MERCADONA SA",
        "mercadona sa",
        "Mercadona Sa",
        "mErCaDoNa",
    ],
)
def test_case_insensitive_matching(text):
    """Rule matching must be case-insensitive."""
    cat = TransactionCategorizer()
    result = cat.categorize(_txn(creditor=text))
    assert result == "groceries", f"Expected groceries for '{text}', got '{result}'"


# ---------------------------------------------------------------------------
# Multi-field priority
# ---------------------------------------------------------------------------


def test_creditor_name_matched():
    """creditorName field must be searched for keyword matches."""
    cat = TransactionCategorizer()
    result = cat.categorize({"creditorName": "Netflix", "transactionAmount": {"amount": "-9.99"}})
    assert result == "subscriptions"


def test_remittance_array_matched():
    """remittanceInformationUnstructuredArray entries must all be searched."""
    cat = TransactionCategorizer()
    txn = {
        "remittanceInformationUnstructuredArray": ["Ref 001", "Alquiler abril", "WE-042"],
        "transactionAmount": {"amount": "-700.00"},
    }
    result = cat.categorize(txn)
    assert result == "housing"
