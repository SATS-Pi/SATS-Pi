import json

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Modes ----------------------------------------------------------
    # mock  : tout est simulé, aucune clé nécessaire (développement, démo de secours)
    # blink : vraie facture Lightning via l'API Blink
    lightning_mode: str = "mock"
    # mock    : le payout est simulé
    # fedapay : payout réel via l'API FedaPay (providers/fedapay.py)
    payout_mode: str = "mock"
    # auto  : Yadio -> CoinGecko -> taux fixe
    # fixed : toujours FIXED_BTC_XOF (tests, démo hors-ligne)
    fx_mode: str = "auto"

    # --- Blink ----------------------------------------------------------
    blink_api_key: str = ""
    blink_wallet_id: str = ""  # identifiant du wallet BTC Blink
    blink_endpoint: str = "https://api.blink.sv/graphql"

    # --- FedaPay ----------------------------------------------------------
    fedapay_env: str = "sandbox"  # sandbox | live
    fedapay_secret_key: str = ""  # clé secrète du dashboard FedaPay (jamais côté client)
    # Valeur du champ "mode" par opérateur, au format JSON : {"BJ:MTN": "...", "TG:Togocel": "..."}.
    # La doc FedaPay ne liste pas ces valeurs : à relever en sandbox. Défaut : "mobile_money".
    fedapay_modes: str = "{}"
    fedapay_poll_s: float = 20.0  # attente du statut final après l'envoi

    # --- Économie -------------------------------------------------------
    # Valeur indicative pour la démo, à ajuster. Utilisée si fx_mode=fixed
    # ou si toutes les sources de taux échouent.
    fixed_btc_xof: float = 60_000_000
    service_fee_pct: float = 1.0  # notre marge
    # Frais de payout : valeur provisoire (0,8 %). À remplacer par le tarif réel FedaPay.
    payout_fee_pct: float = 0.8
    min_xof: int = 500
    max_xof: int = 100_000  # plafond prudent pour le MVP
    invoice_ttl_s: int = 900  # durée de validité du taux et du lien (15 min)

    # --- Technique ------------------------------------------------------
    poll_interval_s: float = 2.0
    mock_payout_delay_s: float = 0.8
    db_path: str = "satspi.db"
    admin_token: str = ""  # vide = route de reprise désactivée


    def fedapay_mode(self, country: str, operator: str | None) -> str:
        try:
            table = json.loads(self.fedapay_modes or "{}")
        except ValueError:
            table = {}
        return table.get(f"{country}:{operator}") or table.get(country) or "mobile_money"


settings = Settings()
