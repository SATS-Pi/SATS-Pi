import time

import httpx

from .config import settings

_cache: dict = {"t": 0.0, "v": None}
_TTL_S = 30


async def get_btc_xof() -> tuple[float, str]:
    """Retourne (XOF pour 1 BTC, source). Yadio -> CoinGecko -> taux fixe."""
    if settings.fx_mode == "fixed":
        return settings.fixed_btc_xof, "fixed"

    if _cache["v"] and time.time() - _cache["t"] < _TTL_S:
        return _cache["v"]

    async with httpx.AsyncClient(timeout=5) as client:
        try:
            r = await client.get("https://api.yadio.io/convert/1/BTC/XOF")
            r.raise_for_status()
            data = r.json()
            rate = float(data.get("result") or data["rate"])
            _cache.update(t=time.time(), v=(rate, "yadio"))
            return _cache["v"]
        except Exception:  # noqa: BLE001 - on tente la source suivante
            pass
        try:
            r = await client.get(
                "https://api.coingecko.com/api/v3/simple/price",
                params={"ids": "bitcoin", "vs_currencies": "xof"},
            )
            r.raise_for_status()
            rate = float(r.json()["bitcoin"]["xof"])
            _cache.update(t=time.time(), v=(rate, "coingecko"))
            return _cache["v"]
        except Exception:  # noqa: BLE001
            pass

    return settings.fixed_btc_xof, "fixed-fallback"
