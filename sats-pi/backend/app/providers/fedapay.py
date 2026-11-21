"""Payout mobile money via l'API FedaPay.

Confirmé par la doc (docs.fedapay.com, relue le 17 nov. 2026) :
  - Bases : https://sandbox-api.fedapay.com/v1  et  https://api.fedapay.com/v1
  - Auth : Authorization: Bearer <clé secrète>
  - POST /payouts : amount (entier), currency {iso}, mode, customer {firstname, lastname,
    phone_number {number, country}}, merchant_reference (unique, jamais réutilisée)
  - PUT  /payouts/start : corps = tableau [{id, scheduled_at?}]
  - GET  /payouts/{id} : statuts pending / started / processing / sent / failed
  - Payouts : fonction activée sur demande (support@fedapay.com), financée par le solde FedaPay.
NON confirmé (à vérifier en sandbox avant la démo) : valeurs de "mode" par opérateur, format exact
du numéro local, enveloppe des réponses (gérée dans _unwrap), événements webhook de payout
(aucun documenté : on interroge donc le statut).
"""
import asyncio
import logging

import httpx

from ..config import settings
from .pispi import PayoutResult, Recipient

log = logging.getLogger("satspi.fedapay")
BASES = {"sandbox": "https://sandbox-api.fedapay.com/v1", "live": "https://api.fedapay.com/v1"}


def _unwrap(data, kind: str = "payout") -> dict:
    """Accepte {"v1/payout": {...}}, {"v1/payouts": [...]}, une liste ou l'objet seul."""
    if isinstance(data, dict):
        for key in (f"v1/{kind}", f"v1/{kind}s"):
            if key in data:
                data = data[key]
                break
    if isinstance(data, list):
        data = data[0] if data else {}
    return data if isinstance(data, dict) else {}


class FedaPayError(Exception):
    """Erreur renvoyée par FedaPay (4xx) : l'envoi n'a pas eu lieu."""


class FedaPayPayout:
    def __init__(self, client: httpx.AsyncClient | None = None) -> None:
        self.http = client or httpx.AsyncClient(
            base_url=BASES.get(settings.fedapay_env, BASES["sandbox"]),
            headers={"Authorization": f"Bearer {settings.fedapay_secret_key}"},
            timeout=20,
        )

    async def aclose(self) -> None:
        await self.http.aclose()

    async def _call(self, method: str, path: str, json=None) -> dict:
        r = await self.http.request(method, path, json=json)
        if r.status_code >= 500:
            raise RuntimeError(f"FedaPay indisponible ({r.status_code})")  # -> reprise manuelle
        if r.status_code >= 400:
            try:
                msg = r.json().get("message") or r.text
            except ValueError:
                msg = r.text
            raise FedaPayError(f"{r.status_code}: {str(msg)[:200]}")
        return _unwrap(r.json())

    @staticmethod
    def _result(p: dict) -> PayoutResult:
        status = (p.get("status") or "").lower()
        ref = str(p.get("id")) if p.get("id") is not None else None
        if status == "sent":
            return PayoutResult(True, ref)
        if status == "failed":
            return PayoutResult(False, ref, p.get("last_error_code") or "envoi échoué")
        return PayoutResult(False, ref, pending=True)

    async def status(self, reference: str) -> PayoutResult:
        return self._result(await self._call("GET", f"/payouts/{reference}"))

    async def send(
        self, *, idempotency_key: str, recipient: Recipient, amount_xof: int, reason: str
    ) -> PayoutResult:
        body = {
            "amount": int(amount_xof),
            "currency": {"iso": "XOF"},
            "mode": settings.fedapay_mode(recipient.country, recipient.operator),
            "description": reason,
            "merchant_reference": idempotency_key,
            "customer": {
                "firstname": recipient.firstname,
                "lastname": recipient.lastname,
                "phone_number": {
                    "number": recipient.local_number,
                    "country": recipient.country.lower(),
                },
            },
        }
        try:
            created = await self._call("POST", "/payouts", json=body)
            pid = created.get("id")
            if pid is None:
                return PayoutResult(False, None, "réponse FedaPay sans identifiant")
            await self._call("PUT", "/payouts/start", json=[{"id": pid}])
        except FedaPayError as e:
            return PayoutResult(False, None, str(e))

        deadline = asyncio.get_event_loop().time() + settings.fedapay_poll_s
        while True:
            res = await self.status(str(pid))
            if not res.pending:
                return res
            if asyncio.get_event_loop().time() >= deadline:
                return PayoutResult(False, str(pid), pending=True)  # le poller prend le relais
            await asyncio.sleep(2)
