import math
from dataclasses import asdict, dataclass

from .config import settings


@dataclass
class Quote:
    amount_xof: int  # ce que la famille reçoit
    service_fee_xof: int  # notre marge
    payout_fee_xof: int  # frais de payout, estimation prudente
    total_xof: int  # ce que paie l'expéditeur, en équivalent XOF
    rate: float  # XOF pour 1 BTC
    rate_source: str
    sats: int

    def dict(self) -> dict:
        return asdict(self)


def _ceil(x: float) -> int:
    # round() d'abord pour éviter qu'un 160.00000000000003 devienne 161
    return math.ceil(round(x, 6))


def build_quote(amount_xof: int, rate: float, rate_source: str) -> Quote:
    service_fee = _ceil(amount_xof * settings.service_fee_pct / 100)
    payout_fee = _ceil(amount_xof * settings.payout_fee_pct / 100)
    total = amount_xof + service_fee + payout_fee
    sats = _ceil(total / rate * 100_000_000)
    return Quote(amount_xof, service_fee, payout_fee, total, rate, rate_source, sats)
