"""Pays gérés par SATS-PI.

Source : documentation FedaPay (payouts), relue le 17 nov. 2026. Elle ne confirme les payouts
mobile money que pour : MTN Bénin, Moov Bénin, MTN Côte d'Ivoire, Moov Togo, Togocel.
Les autres pays où FedaPay encaisse (Burkina, Mali, Niger, Sénégal, Guinée) sont listés mais
désactivés (payout=False) tant que FedaPay ne confirme pas le payout par écrit.
Les règles de numéros ci-dessous sont à vérifier en sandbox FedaPay.
"""
import re
from dataclasses import dataclass

from fastapi import HTTPException


@dataclass(frozen=True)
class Country:
    code: str  # ISO 3166-1 alpha-2
    name: str
    dial: str  # indicatif sans +
    currency: str
    national_len: int  # longueur du numéro national attendu
    operators: tuple[str, ...]
    payout: bool  # payout confirmé par la doc FedaPay


COUNTRIES: dict[str, Country] = {
    c.code: c
    for c in (
        Country("BJ", "Bénin", "229", "XOF", 10, ("MTN", "Moov"), True),
        Country("CI", "Côte d'Ivoire", "225", "XOF", 10, ("MTN",), True),
        Country("TG", "Togo", "228", "XOF", 8, ("Moov", "Togocel"), True),
        Country("BF", "Burkina Faso", "226", "XOF", 8, (), False),
        Country("ML", "Mali", "223", "XOF", 8, (), False),
        Country("NE", "Niger", "227", "XOF", 8, (), False),
        Country("SN", "Sénégal", "221", "XOF", 9, (), False),
        Country("GN", "Guinée", "224", "GNF", 9, (), False),  # GNF : autre devise, hors périmètre
    )
}


def get_country(code: str) -> Country:
    c = COUNTRIES.get((code or "").upper())
    if not c:
        raise HTTPException(400, "Pays inconnu.")
    if not c.payout:
        raise HTTPException(400, f"Réception pas encore disponible en {c.name}.")
    return c


def normalize_phone(country: Country, raw: str) -> tuple[str, str]:
    """Retourne (E.164, numéro local envoyé à FedaPay)."""
    d = re.sub(r"\D", "", raw)
    if d.startswith(country.dial) and len(d) > country.national_len:
        d = d[len(country.dial):]
    if country.code == "BJ" and len(d) == 8:
        d = "01" + d  # ancien format à 8 chiffres -> préfixe 01 (2024)
    if len(d) != country.national_len or (country.code == "BJ" and not d.startswith("01")):
        raise HTTPException(400, f"Numéro invalide pour {country.name}.")
    local = d[2:] if country.code == "BJ" else d  # exemple de la doc FedaPay : 8 chiffres au Bénin
    return f"+{country.dial}{d}", local


def mask_phone(e164: str, country: Country) -> str:
    n = e164[len(country.dial) + 1:]
    if len(n) >= 8:
        return f"+{country.dial} {n[:2]} {n[2:4]} ** ** {n[-2:]}"
    return f"+{country.dial} ** {n[-2:]}"
