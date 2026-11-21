import asyncio
import secrets
from dataclasses import dataclass
from typing import Protocol

from ..config import settings


@dataclass
class PayoutResult:
    ok: bool
    reference: str | None = None
    error: str | None = None
    pending: bool = False  # envoyé au prestataire, statut final pas encore connu


@dataclass(frozen=True)
class Recipient:
    firstname: str
    lastname: str
    country: str  # ISO2, ex. "BJ"
    phone: str  # E.164, ex. +2290197123456
    local_number: str  # numéro sans indicatif, tel qu'attendu par FedaPay
    operator: str | None = None


class PayoutProvider(Protocol):
    async def send(
        self, *, idempotency_key: str, recipient: Recipient, amount_xof: int, reason: str
    ) -> PayoutResult:
        """Envoie `amount_xof` vers le bénéficiaire. `idempotency_key` doit être unique
        par tentative : le prestataire refuse de réutiliser une référence."""

    async def status(self, reference: str) -> PayoutResult:
        """Statut d'un envoi déjà lancé (ok / en cours / échec)."""


class MockPiSpi:
    """Simule un payout. À afficher clairement comme SANDBOX en démo."""

    def __init__(self) -> None:
        self.sent: dict[str, dict] = {}

    async def status(self, reference: str) -> PayoutResult:
        return PayoutResult(True, reference)

    async def send(
        self, *, idempotency_key: str, recipient: Recipient, amount_xof: int, reason: str
    ) -> PayoutResult:
        if idempotency_key in self.sent:
            return PayoutResult(True, self.sent[idempotency_key]["reference"])
        await asyncio.sleep(settings.mock_payout_delay_s)
        ref = "MOCK-" + secrets.token_hex(4).upper()
        self.sent[idempotency_key] = {
            "reference": ref,
            "phone": recipient.phone,
            "country": recipient.country,
            "amount_xof": amount_xof,
            "reason": reason,
        }
        return PayoutResult(True, ref)
