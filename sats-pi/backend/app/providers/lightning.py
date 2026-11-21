import secrets
from typing import Protocol

import httpx

from ..config import settings


class LightningProvider(Protocol):
    async def create_invoice(self, sats: int, memo: str) -> tuple[str, str]:
        """Retourne (facture bolt11, payment_hash)."""

    async def is_paid(self, bolt11: str, payment_hash: str) -> bool: ...


class MockLightning:
    """Facture factice. Le paiement est déclenché par /api/dev/simulate-payment/{id}."""

    def __init__(self) -> None:
        self.paid: set[str] = set()

    async def create_invoice(self, sats: int, memo: str) -> tuple[str, str]:
        payment_hash = secrets.token_hex(32)
        return f"lnbc{sats}n1mock{payment_hash[:48]}", payment_hash

    async def is_paid(self, bolt11: str, payment_hash: str) -> bool:
        return payment_hash in self.paid

    def simulate_payment(self, payment_hash: str) -> None:
        self.paid.add(payment_hash)


# ATTENTION : requêtes écrites de mémoire. À valider dans l'API explorer de Blink
# (dashboard.blink.sv) : noms des champs, type du montant, et nom de la requête de
# statut (il existe aussi des variantes par hash).
_CREATE = """
mutation LnInvoiceCreate($input: LnInvoiceCreateInput!) {
  lnInvoiceCreate(input: $input) {
    errors { message }
    invoice { paymentRequest paymentHash }
  }
}
"""

_STATUS = """
query LnInvoicePaymentStatus($input: LnInvoicePaymentStatusInput!) {
  lnInvoicePaymentStatus(input: $input) {
    status
    errors { message }
  }
}
"""


class BlinkLightning:
    def __init__(self) -> None:
        self.client = httpx.AsyncClient(
            timeout=10, headers={"X-API-KEY": settings.blink_api_key}
        )

    async def _gql(self, query: str, variables: dict) -> dict:
        r = await self.client.post(
            settings.blink_endpoint, json={"query": query, "variables": variables}
        )
        r.raise_for_status()
        body = r.json()
        if body.get("errors"):
            raise RuntimeError(f"Blink GraphQL : {body['errors']}")
        return body["data"]

    async def create_invoice(self, sats: int, memo: str) -> tuple[str, str]:
        data = await self._gql(
            _CREATE,
            {"input": {"walletId": settings.blink_wallet_id, "amount": sats, "memo": memo}},
        )
        res = data["lnInvoiceCreate"]
        if res["errors"]:
            raise RuntimeError(f"Blink : {res['errors']}")
        inv = res["invoice"]
        return inv["paymentRequest"], inv["paymentHash"]

    async def is_paid(self, bolt11: str, payment_hash: str) -> bool:
        data = await self._gql(_STATUS, {"input": {"paymentRequest": bolt11}})
        return data["lnInvoicePaymentStatus"]["status"] == "PAID"

    async def aclose(self) -> None:
        await self.client.aclose()
