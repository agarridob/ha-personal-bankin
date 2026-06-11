"""Demo data generator for Finance Dashboard.

Generates realistic Spanish banking data for demo/testing purposes.
All data is synthetic — no real financial information.

Each call to generate_demo_data() produces a complete, randomized dataset
that matches the exact shape the frontend expects (unified data object).
"""

from __future__ import annotations

import random
from datetime import datetime
from typing import Any

# ---------------------------------------------------------------------------
# Demo bank accounts
# ---------------------------------------------------------------------------

DEMO_ACCOUNTS_CONFIG: list[dict[str, Any]] = [
    {
        "id": "demo-cajarural-ana",
        "iban": "ES9121000418450200051332",
        "name": "Cuenta corriente",
        "custom_name": "Ana Caja Rural",
        "institution": "Caja Rural de Zamora",
        "institution_id": "CAJARURAL_ZAMORA_ES",
        "logo": "",
        "currency": "EUR",
        "type": "personal",
        "person": "Ana",
        "ha_users": [],
    },
    {
        "id": "demo-bbva-mario",
        "iban": "ES7620770024003102575766",
        "name": "Cuenta corriente",
        "custom_name": "Mario BBVA",
        "institution": "BBVA",
        "institution_id": "BBVA_ES",
        "logo": "",
        "currency": "EUR",
        "type": "personal",
        "person": "Mario",
        "ha_users": [],
    },
    {
        "id": "demo-ing-shared",
        "iban": "ES6621000418401234567891",
        "name": "Cuenta conjunta",
        "custom_name": "Cuenta del hogar",
        "institution": "ING",
        "institution_id": "ING_ES",
        "logo": "",
        "currency": "EUR",
        "type": "shared",
        "person": "",
        "ha_users": [],
    },
]

# Base balances per account (randomized ±15%)
_BASE_BALANCES = {
    "demo-cajarural-ana": 3250.00,
    "demo-bbva-mario": 2180.00,
    "demo-ing-shared": 1520.00,
}

# ---------------------------------------------------------------------------
# Transaction templates — amounts are jittered at generation time
# ---------------------------------------------------------------------------

_TRANSACTION_TEMPLATES: list[dict[str, Any]] = [
    # --- Shared account (ING) ---
    {
        "creditor": "Inmobiliaria Duero SL",
        "desc": "Alquiler {month_name} {year}",
        "base": -1150.0,
        "cat": "housing",
        "day": 1,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Iberdrola Clientes",
        "desc": "Recibo luz",
        "base": -85.0,
        "cat": "utilities",
        "day": 3,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Movistar",
        "desc": "Fibra + fijo",
        "base": -44.95,
        "cat": "utilities",
        "day": 5,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Mapfre",
        "desc": "Seguro hogar",
        "base": -12.50,
        "cat": "insurance",
        "day": 1,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Aqualia",
        "desc": "Recibo agua",
        "base": -18.36,
        "cat": "utilities",
        "day": 1,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Mercadona",
        "desc": "Mercadona compra grande",
        "base": -89.45,
        "cat": "food",
        "day": 4,
        "acc": "demo-ing-shared",
    },
    {
        "creditor": "Carrefour",
        "desc": "Carrefour hipermercado",
        "base": -49.99,
        "cat": "food",
        "day": 8,
        "acc": "demo-ing-shared",
    },
    # --- Anna (Sparkasse) ---
    {
        "creditor": "Empresa Ejemplo SL",
        "desc": "Nomina {month_name}",
        "base": 3250.0,
        "cat": "income",
        "day": 25,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Mercadona",
        "desc": "Mercadona compra 4823",
        "base": -47.83,
        "cat": "food",
        "day": 2,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Eroski",
        "desc": "Eroski City compra",
        "base": -32.15,
        "cat": "food",
        "day": 5,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Netflix",
        "desc": "Netflix suscripcion",
        "base": -13.99,
        "cat": "subscriptions",
        "day": 8,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Spotify",
        "desc": "Spotify Premium Family",
        "base": -17.99,
        "cat": "subscriptions",
        "day": 1,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Renfe",
        "desc": "Renfe abono mensual",
        "base": -49.00,
        "cat": "transport",
        "day": 1,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "ALDI",
        "desc": "ALDI tienda 2847",
        "base": -28.47,
        "cat": "food",
        "day": 10,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Druni",
        "desc": "Druni perfumeria",
        "base": -15.99,
        "cat": "other",
        "day": 7,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Mercadona",
        "desc": "Mercadona compra 5121",
        "base": -52.30,
        "cat": "food",
        "day": 12,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Glovo",
        "desc": "Glovo pedido cena",
        "base": -24.90,
        "cat": "food",
        "day": 14,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Linea Directa",
        "desc": "Seguro coche",
        "base": -45.80,
        "cat": "insurance",
        "day": 1,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "LIDL",
        "desc": "LIDL compra",
        "base": -19.62,
        "cat": "food",
        "day": 16,
        "acc": "demo-cajarural-ana",
    },
    {
        "creditor": "Primor",
        "desc": "Primor tienda",
        "base": -8.49,
        "cat": "other",
        "day": 18,
        "acc": "demo-cajarural-ana",
    },
    # --- Max (DKB) ---
    {
        "creditor": "Tecnologia SA",
        "desc": "Nomina {month_name}",
        "base": 2850.0,
        "cat": "income",
        "day": 27,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Mercadona",
        "desc": "Mercadona compra",
        "base": -38.92,
        "cat": "food",
        "day": 3,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Lidl",
        "desc": "LIDL compra semanal",
        "base": -22.47,
        "cat": "food",
        "day": 6,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Disney Plus",
        "desc": "Disney+ suscripcion",
        "base": -8.99,
        "cat": "subscriptions",
        "day": 15,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Xbox",
        "desc": "Xbox Game Pass Ultimate",
        "base": -14.99,
        "cat": "subscriptions",
        "day": 10,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Repsol",
        "desc": "Repsol gasolinera A-52",
        "base": -65.40,
        "cat": "transport",
        "day": 8,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Amazon",
        "desc": "Amazon.es pedido",
        "base": -34.99,
        "cat": "other",
        "day": 11,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Alcampo",
        "desc": "Alcampo compra",
        "base": -41.23,
        "cat": "food",
        "day": 9,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Basic-Fit",
        "desc": "Basic-Fit cuota gimnasio",
        "base": -29.90,
        "cat": "other",
        "day": 1,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Cepsa",
        "desc": "Cepsa gasolinera",
        "base": -58.20,
        "cat": "transport",
        "day": 15,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Caja Rural de Zamora",
        "desc": "Prestamo coche cuota 48/60",
        "base": -285.00,
        "cat": "loans",
        "day": 5,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Adeslas",
        "desc": "Seguro dental",
        "base": -28.50,
        "cat": "insurance",
        "day": 1,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Google",
        "desc": "Google One 200 GB",
        "base": -2.99,
        "cat": "subscriptions",
        "day": 12,
        "acc": "demo-bbva-mario",
    },
    {
        "creditor": "Mercadona",
        "desc": "Mercadona compra tarde",
        "base": -31.78,
        "cat": "food",
        "day": 17,
        "acc": "demo-bbva-mario",
    },
]

# Recurring patterns for demo
_RECURRING_TEMPLATES: list[dict[str, Any]] = [
    {
        "creditor": "Inmobiliaria Duero SL",
        "average_amount": -1150.0,
        "frequency": "monthly",
        "category": "housing",
        "occurrences": 12,
        "expected_day": 1,
    },
    {
        "creditor": "Iberdrola Clientes",
        "average_amount": -85.0,
        "frequency": "monthly",
        "category": "utilities",
        "occurrences": 12,
        "expected_day": 3,
    },
    {
        "creditor": "Movistar",
        "average_amount": -44.95,
        "frequency": "monthly",
        "category": "utilities",
        "occurrences": 12,
        "expected_day": 5,
    },
    {
        "creditor": "Netflix",
        "average_amount": -13.99,
        "frequency": "monthly",
        "category": "subscriptions",
        "occurrences": 8,
        "expected_day": 8,
    },
    {
        "creditor": "Spotify",
        "average_amount": -17.99,
        "frequency": "monthly",
        "category": "subscriptions",
        "occurrences": 11,
        "expected_day": 1,
    },
    {
        "creditor": "Renfe",
        "average_amount": -49.00,
        "frequency": "monthly",
        "category": "transport",
        "occurrences": 10,
        "expected_day": 1,
    },
    {
        "creditor": "Caja Rural de Zamora",
        "average_amount": -285.00,
        "frequency": "monthly",
        "category": "loans",
        "occurrences": 12,
        "expected_day": 5,
    },
    {
        "creditor": "Carrefour",
        "average_amount": -49.99,
        "frequency": "monthly",
        "category": "food",
        "occurrences": 6,
        "expected_day": 8,
    },
]

# Month names for Spanish formatting
_MONTH_NAMES = [
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_demo_data() -> dict[str, Any]:
    """Generate a complete demo dataset matching the frontend unified data shape.

    Returns a dict with keys: accounts, totalBalance, accountCount, summary,
    budgets, splitModel, household, recurring, loading, error, lastRefresh,
    rateLimitedUntil, _demo_accounts, _demo_transactions, _demo_balances.

    The _demo_* keys are internal — used by the manager to populate entities.
    """
    rng = random.Random()
    now = datetime.now()
    month = now.month
    year = now.year
    month_name = _MONTH_NAMES[month - 1]

    accounts = _build_accounts()
    transactions = _build_transactions(rng, month, year, month_name)
    balances = _build_balances(rng, accounts)

    # Compute summary from transactions
    category_totals: dict[str, float] = {}
    total_income = 0.0
    total_expenses = 0.0

    for txn in transactions:
        amount = float(txn["transactionAmount"]["amount"])
        cat = txn.get("category", "other")
        if amount > 0:
            total_income += amount
        else:
            total_expenses += abs(amount)
        category_totals[cat] = category_totals.get(cat, 0) + amount

    fixed_cats = {"housing", "loans", "utilities", "insurance"}
    fixed_total = sum(abs(category_totals.get(c, 0)) for c in fixed_cats)
    variable_total = total_expenses - fixed_total

    # Build household data
    household = _build_household(rng, transactions, total_expenses)

    # Build frontend account list
    fe_accounts = []
    total_balance = 0.0
    for acc in accounts:
        acc_id = acc["id"]
        bal_data = balances.get(acc_id, {})
        raw_bals = bal_data.get("balances", [])
        bal_val = 0.0
        if raw_bals:
            bal_val = float(raw_bals[0].get("balanceAmount", {}).get("amount", 0))
        iban = acc.get("iban", "")
        fe_accounts.append(
            {
                "entityId": f"sensor.fd_demo_{acc_id.replace('-', '_')}",
                "name": acc.get("custom_name") or acc.get("name", ""),
                "institution": acc.get("institution", ""),
                "balance": bal_val,
                "ibanMasked": f"****{iban[-4:]}" if len(iban) >= 4 else "****",
                "currency": acc.get("currency", "EUR"),
                "person": acc.get("person", ""),
            }
        )
        total_balance += bal_val

    # Budget limits (demo defaults)
    budgets = {
        "housing": 1200.0,
        "food": 600.0,
        "transport": 200.0,
        "subscriptions": 100.0,
        "insurance": 150.0,
        "utilities": 200.0,
        "loans": 300.0,
        "other": 200.0,
    }

    return {
        # Frontend unified data shape
        "accounts": fe_accounts,
        "totalBalance": round(total_balance, 2),
        "accountCount": len(fe_accounts),
        "summary": {
            "totalIncome": round(total_income, 2),
            "totalExpenses": round(total_expenses, 2),
            "balance": round(total_income - total_expenses, 2),
            "categories": {k: round(v, 2) for k, v in category_totals.items()},
            "transactionCount": len(transactions),
            "fixedCosts": round(fixed_total, 2),
            "variableCosts": round(variable_total, 2),
            "month": month,
            "year": year,
        },
        "budgets": budgets,
        "splitModel": "proportional",
        "household": household,
        "recurring": _RECURRING_TEMPLATES[:8],
        "loading": False,
        "error": None,
        "lastRefresh": now.isoformat(),
        "rateLimitedUntil": None,
        # Internal keys for manager/coordinator
        "_demo_accounts": accounts,
        "_demo_transactions": transactions,
        "_demo_balances": balances,
    }


# ---------------------------------------------------------------------------
# Internal builders
# ---------------------------------------------------------------------------


def _build_accounts() -> list[dict[str, Any]]:
    """Return a deep copy of demo accounts."""
    return [dict(a) for a in DEMO_ACCOUNTS_CONFIG]


def _build_transactions(
    rng: random.Random,
    month: int,
    year: int,
    month_name: str,
) -> list[dict[str, Any]]:
    """Generate demo transactions for the given month."""
    today = datetime.now().day
    transactions: list[dict[str, Any]] = []

    # Build account lookup for tagging
    acc_map = {a["id"]: a for a in DEMO_ACCOUNTS_CONFIG}

    for i, tpl in enumerate(_TRANSACTION_TEMPLATES):
        day = tpl["day"]
        # Skip future dates within the month (including future salaries)
        if day > today:
            continue

        # Jitter amount by ±8% (except fixed amounts like rent, salary)
        base = tpl["base"]
        if abs(base) > 100 and tpl["cat"] not in ("income", "housing", "loans"):
            jitter = rng.uniform(-0.08, 0.08)
            amount = round(base * (1 + jitter), 2)
        elif abs(base) < 100:
            jitter = rng.uniform(-0.12, 0.12)
            amount = round(base * (1 + jitter), 2)
        else:
            amount = base

        booking_date = f"{year}-{month:02d}-{day:02d}"
        desc = tpl["desc"].format(month_name=month_name, year=year)
        acc_id = tpl["acc"]
        acc = acc_map.get(acc_id, {})

        transactions.append(
            {
                "transactionId": f"demo-{i:04d}-{rng.randint(1000, 9999)}",
                "bookingDate": booking_date,
                "transactionAmount": {
                    "amount": str(amount),
                    "currency": "EUR",
                },
                "creditorName": tpl["creditor"],
                "remittanceInformationUnstructured": desc,
                "category": tpl["cat"],
                "_account_id": acc_id,
                "_account_name": acc.get("custom_name") or acc.get("name", ""),
                "_account_type": acc.get("type", "personal"),
                "_account_person": acc.get("person", ""),
                "_account_ha_users": [],
                "_status": "booked",
            }
        )

    # Sort newest first
    transactions.sort(key=lambda t: t["bookingDate"], reverse=True)
    return transactions


def _build_balances(
    rng: random.Random,
    accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Generate demo balance data per account."""
    today = datetime.now().strftime("%Y-%m-%d")
    balances: dict[str, Any] = {}

    for acc in accounts:
        acc_id = acc["id"]
        base = _BASE_BALANCES.get(acc_id, 1000.0)
        amount = round(base * rng.uniform(0.85, 1.15), 2)
        iban = acc.get("iban", "")

        balances[acc_id] = {
            "account_name": acc.get("custom_name") or acc.get("name", ""),
            "iban": iban,
            "iban_masked": f"****{iban[-4:]}" if len(iban) >= 4 else "****",
            "institution": acc.get("institution", ""),
            "logo": acc.get("logo", ""),
            "balances": [
                {
                    "balanceType": "closingBooked",
                    "balanceAmount": {
                        "amount": str(amount),
                        "currency": "EUR",
                    },
                    "referenceDate": today,
                }
            ],
        }

    return balances


def _build_household(
    rng: random.Random,
    transactions: list[dict[str, Any]],
    total_expenses: float,
) -> dict[str, Any]:
    """Build household split data from demo transactions."""
    persons: dict[str, dict[str, float]] = {}
    shared_costs = 0.0

    for txn in transactions:
        amount = float(txn["transactionAmount"]["amount"])
        acc_type = txn.get("_account_type", "personal")
        person = txn.get("_account_person", "")

        if acc_type == "shared":
            if amount < 0:
                shared_costs += abs(amount)
        elif person:
            if person not in persons:
                persons[person] = {"income": 0.0, "individual_costs": 0.0}
            if amount > 0:
                persons[person]["income"] += amount
            else:
                persons[person]["individual_costs"] += abs(amount)

    if not persons:
        return None

    # Calculate proportional split
    total_income = sum(p["income"] for p in persons.values())
    members = []
    for name, data in persons.items():
        ratio = data["income"] / total_income if total_income > 0 else 0.5
        share = shared_costs * ratio
        spielgeld = data["income"] - data["individual_costs"] - share

        members.append(
            {
                "person": name,
                "gross_income": round(data["income"], 2),
                "net_income": round(data["income"], 2),
                "income_ratio": round(ratio * 100, 1),
                "shared_costs_share": round(share, 2),
                "individual_costs": round(data["individual_costs"], 2),
                "spielgeld": round(spielgeld, 2),
                "bonus_amount": 0.0,
            }
        )

    return {
        "members": members,
        "split_model": "proportional",
        "remainder_mode": "none",
        "total_shared_costs": round(shared_costs, 2),
    }
