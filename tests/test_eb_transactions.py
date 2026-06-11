"""Enable Banking /transactions response parsing.

The real API returns {"transactions": [flat list], "continuation_key": ...}
where each transaction carries a status (BOOK/PEND) and an unsigned amount
plus credit_debit_indicator — unlike the GoCardless {booked, pending}
shape the rest of the integration consumes. These tests pin the
normalization: status split, sign handling, remittance list join and
continuation_key pagination.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from custom_components.finance_dashboard.enablebanking_client import EnableBankingClient

# Minimal valid RSA key is not needed — we bypass __init__'s key loading
# by constructing the object without calling __init__.


def _client() -> EnableBankingClient:
    client = EnableBankingClient.__new__(EnableBankingClient)
    client._session = None
    return client


def _eb_txn(
    amount: str = "12.34",
    indicator: str = "DBIT",
    status: str = "BOOK",
    remittance: list[str] | str | None = None,
) -> dict:
    return {
        "entry_reference": "ref-1",
        "booking_date": "2026-06-10",
        "transaction_amount": {"amount": amount, "currency": "EUR"},
        "credit_debit_indicator": indicator,
        "status": status,
        "creditor": {"name": "MERCADONA SA"},
        "remittance_information": remittance if remittance is not None else ["COMPRA 1234"],
    }


# ---------------------------------------------------------------------------
# Flat-list parsing (real Enable Banking shape)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_flat_list_with_status_split():
    client = _client()
    client._async_request = AsyncMock(
        return_value={
            "transactions": [
                _eb_txn(status="BOOK"),
                _eb_txn(status="PEND"),
                _eb_txn(status="BOOK"),
            ],
            "continuation_key": None,
        }
    )

    result = await client.async_get_transactions("acc-1", "2026-03-01", "2026-06-11")

    assert len(result["booked"]) == 2
    assert len(result["pending"]) == 1


@pytest.mark.asyncio
async def test_debit_amounts_are_signed_negative():
    client = _client()
    client._async_request = AsyncMock(
        return_value={
            "transactions": [
                _eb_txn(amount="50.00", indicator="DBIT"),
                _eb_txn(amount="1200.00", indicator="CRDT"),
            ]
        }
    )

    result = await client.async_get_transactions("acc-1")

    amounts = [t["transactionAmount"]["amount"] for t in result["booked"]]
    assert amounts == ["-50.00", "1200.00"]


@pytest.mark.asyncio
async def test_remittance_list_joined_to_string():
    client = _client()
    client._async_request = AsyncMock(
        return_value={"transactions": [_eb_txn(remittance=["RECIBO", "IBERDROLA", ""])]}
    )

    result = await client.async_get_transactions("acc-1")

    assert result["booked"][0]["remittanceInformationUnstructured"] == "RECIBO IBERDROLA"


@pytest.mark.asyncio
async def test_continuation_key_pagination():
    client = _client()
    client._async_request = AsyncMock(
        side_effect=[
            {"transactions": [_eb_txn()], "continuation_key": "page2"},
            {"transactions": [_eb_txn()], "continuation_key": None},
        ]
    )

    result = await client.async_get_transactions("acc-1", "2026-03-01", "2026-06-11")

    assert len(result["booked"]) == 2
    assert client._async_request.await_count == 2
    second_call_endpoint = client._async_request.await_args_list[1].args[1]
    assert "continuation_key=page2" in second_call_endpoint


@pytest.mark.asyncio
async def test_pagination_cap_stops_runaway_loop():
    client = _client()
    client._async_request = AsyncMock(
        return_value={"transactions": [_eb_txn()], "continuation_key": "again"}
    )

    result = await client.async_get_transactions("acc-1")

    assert client._async_request.await_count == EnableBankingClient._MAX_TX_PAGES
    assert len(result["booked"]) == EnableBankingClient._MAX_TX_PAGES


# ---------------------------------------------------------------------------
# Legacy GoCardless-style dict still accepted
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_gocardless_dict_shape_still_supported():
    client = _client()
    client._async_request = AsyncMock(
        return_value={
            "booked": [_eb_txn()],
            "pending": [_eb_txn(status="PEND")],
        }
    )

    result = await client.async_get_transactions("acc-1")

    assert len(result["booked"]) == 1
    assert len(result["pending"]) == 1
