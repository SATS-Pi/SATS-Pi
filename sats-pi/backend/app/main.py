import asyncio
import contextlib
import io
import logging
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import qrcode
import qrcode.image.svg
from fastapi import FastAPI, Header, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import store as st
from .config import settings
from .fx import get_btc_xof
from .providers.lightning import BlinkLightning, MockLightning
from .countries import COUNTRIES, get_country, mask_phone, normalize_phone
from .providers.fedapay import FedaPayPayout
from .providers.pispi import MockPiSpi, Recipient
from .quote import build_quote

log = logging.getLogger("satspi")
STATIC = Path(__file__).resolve().parent.parent / "static"


# ---------------------------------------------------------------- helpers
def check_amount(amount_xof: int) -> None:
    if not (settings.min_xof <= amount_xof <= settings.max_xof):
        raise HTTPException(
            400, f"Montant entre {settings.min_xof} et {settings.max_xof} FCFA."
        )


def public(link: dict) -> dict:
    """Vue publique d'un lien (le numéro est masqué, l'erreur interne n'est pas exposée)."""
    return {
        "id": link["id"],
        "status": link["status"],
        "country": link["country"],
        "phone_masked": mask_phone(link["phone"], COUNTRIES[link["country"]]),
        "note": link["note"],
        "amount_xof": link["amount_xof"],
        "total_xof": link["total_xof"],
        "sats": link["sats"],
        "rate": link["rate"],
        "rate_source": link["rate_source"],
        "invoice": link["invoice"],
        "expires_at": link["expires_at"],
        "payout_ref": link.get("payout_ref"),
        "payout_failed": link["status"] == st.FAILED,
    }


# ------------------------------------------------- règlement (poller)
async def do_payout(app: FastAPI, link: dict) -> None:
    store: st.Store = app.state.store
    recipient = Recipient(
        firstname=link["firstname"], lastname=link["lastname"], country=link["country"],
        phone=link["phone"], local_number=link["local_number"], operator=link["operator"],
    )
    # Le prestataire refuse de réutiliser une référence : une reprise utilise un suffixe.
    key = link["id"] if not link["attempts"] else f"{link['id']}-r{link['attempts']}"
    try:
        res = await app.state.payout.send(
            idempotency_key=key,
            recipient=recipient,
            amount_xof=link["amount_xof"],
            reason=(link["note"] or "SATS-PI")[:60],
        )
    except Exception as e:  # noqa: BLE001
        log.exception("Erreur d'envoi pour %s", link["id"])
        store.mark_failed(link["id"], f"{type(e).__name__}: {e}")
        return
    if res.pending:
        store.set_payout_id(link["id"], res.reference)  # statut final suivi par settle_once
    elif res.ok:
        store.mark_completed(link["id"], res.reference)
    else:
        store.mark_failed(link["id"], res.error or "envoi refusé")


async def follow_payouts(app: FastAPI) -> None:
    store: st.Store = app.state.store
    for link in store.paying_out_pending():
        try:
            res = await app.state.payout.status(link["payout_id"])
        except Exception:  # noqa: BLE001
            log.exception("Statut du payout impossible pour %s", link["id"])
            continue
        if res.pending:
            continue
        if res.ok:
            store.mark_completed(link["id"], res.reference)
        else:
            store.mark_failed(link["id"], res.error or "envoi échoué")


async def settle_once(app: FastAPI) -> None:
    store: st.Store = app.state.store
    for link in store.pending():
        try:
            paid = await app.state.ln.is_paid(link["invoice"], link["payment_hash"])
        except Exception:  # noqa: BLE001
            log.exception("Vérification Lightning impossible pour %s", link["id"])
            continue
        if paid:
            # Payée, même après expiration du taux : on honore le montant en FCFA.
            if store.claim_for_payout(link["id"]):
                await do_payout(app, link)
        elif link["expires_at"] < time.time():
            store.mark_expired(link["id"])
    await follow_payouts(app)


async def settle_loop(app: FastAPI) -> None:
    while True:
        try:
            await settle_once(app)
        except Exception:  # noqa: BLE001
            log.exception("settle_once a échoué")
        await asyncio.sleep(settings.poll_interval_s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.store = st.Store(settings.db_path)
    app.state.ln = BlinkLightning() if settings.lightning_mode == "blink" else MockLightning()
    app.state.payout = FedaPayPayout() if settings.payout_mode == "fedapay" else MockPiSpi()
    task = asyncio.create_task(settle_loop(app))
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        for p in (app.state.ln, app.state.payout):
            if hasattr(p, "aclose"):
                await p.aclose()


app = FastAPI(title="SATS-PI", lifespan=lifespan)


# -------------------------------------------------------------- API
class LinkIn(BaseModel):
    phone: str
    amount_xof: int
    firstname: str = Field(min_length=1, max_length=40)  # exigé par FedaPay
    lastname: str = Field(min_length=1, max_length=40)
    country: str = "BJ"
    operator: str | None = None
    note: str = ""


@app.get("/api/health")
async def health():
    return {
        "ok": True,
        "lightning_mode": settings.lightning_mode,
        "payout_mode": settings.payout_mode,
    }


@app.get("/api/countries")
async def countries():
    return [
        {"code": c.code, "name": c.name, "dial": c.dial, "currency": c.currency,
         "operators": list(c.operators), "available": c.payout}
        for c in COUNTRIES.values()
    ]


@app.get("/api/quote")
async def quote(amount_xof: int):
    check_amount(amount_xof)
    rate, source = await get_btc_xof()
    return build_quote(amount_xof, rate, source).dict()


@app.post("/api/links", status_code=201)
async def create_link(body: LinkIn):
    country = get_country(body.country)
    phone, local = normalize_phone(country, body.phone)
    if body.operator and body.operator not in country.operators:
        raise HTTPException(400, f"Opérateur non pris en charge en {country.name}.")
    check_amount(body.amount_xof)
    note = body.note.strip()[:80]
    rate, source = await get_btc_xof()
    q = build_quote(body.amount_xof, rate, source)
    link_id = uuid.uuid4().hex[:10]
    bolt11, payment_hash = await app.state.ln.create_invoice(q.sats, f"SATS-PI {link_id}")
    now = time.time()
    link = {
        "id": link_id,
        "phone": phone,
        "country": country.code,
        "operator": body.operator,
        "firstname": body.firstname.strip(),
        "lastname": body.lastname.strip(),
        "local_number": local,
        "note": note,
        "amount_xof": q.amount_xof,
        "total_xof": q.total_xof,
        "sats": q.sats,
        "rate": q.rate,
        "rate_source": q.rate_source,
        "invoice": bolt11,
        "payment_hash": payment_hash,
        "status": st.PENDING,
        "created_at": now,
        "expires_at": now + settings.invoice_ttl_s,
    }
    app.state.store.insert(link)
    return public(link)


def _get_or_404(link_id: str) -> dict:
    link = app.state.store.get(link_id)
    if not link:
        raise HTTPException(404, "Lien introuvable.")
    return link


@app.get("/api/links/{link_id}")
async def get_link(link_id: str):
    return public(_get_or_404(link_id))


@app.get("/api/links/{link_id}/qr.svg")
async def link_qr(link_id: str):
    link = _get_or_404(link_id)
    # Majuscules : le QR est plus petit et reste lu par les wallets Lightning.
    img = qrcode.make(
        "LIGHTNING:" + link["invoice"].upper(),
        image_factory=qrcode.image.svg.SvgPathImage,
        border=2,
    )
    buf = io.BytesIO()
    img.save(buf)
    return Response(buf.getvalue(), media_type="image/svg+xml")


@app.post("/api/dev/simulate-payment/{link_id}")
async def simulate_payment(link_id: str):
    if settings.lightning_mode != "mock":
        raise HTTPException(404, "Disponible uniquement en mode mock.")
    link = _get_or_404(link_id)
    app.state.ln.simulate_payment(link["payment_hash"])
    return {"ok": True}


@app.post("/api/admin/links/{link_id}/retry")
async def retry_payout(link_id: str, x_admin_token: str = Header(default="")):
    """Relance un payout en échec (sats déjà reçus). Sûr grâce à la clé d'idempotence."""
    if not settings.admin_token or not secrets.compare_digest(x_admin_token, settings.admin_token):
        raise HTTPException(403, "Interdit.")
    _get_or_404(link_id)
    if not app.state.store.claim_retry(link_id):
        raise HTTPException(409, "Ce lien n'est pas en échec d'envoi.")
    await do_payout(app, app.state.store.get(link_id))
    return public(app.state.store.get(link_id))


# ------------------------------------------------------------ frontend
# Le front vit dans apps/web. Ce mini-front de secours n'est servi que si backend/static existe.
if STATIC.exists():

    @app.get("/")
    async def index():
        return FileResponse(STATIC / "index.html")

    app.mount("/static", StaticFiles(directory=STATIC), name="static")
