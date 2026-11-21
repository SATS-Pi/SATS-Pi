import asyncio
import json

import httpx

from app.providers.fedapay import FedaPayPayout
from app.providers.pispi import Recipient

R = Recipient("Afi", "Dossou", "BJ", "+2290197123456", "97123456", "MTN")


def provider(handler):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler), base_url="https://sandbox-api.fedapay.com/v1",
        headers={"Authorization": "Bearer sk_test"},
    )
    return FedaPayPayout(client)


def test_create_start_and_sent():
    calls = []

    def handler(req: httpx.Request) -> httpx.Response:
        calls.append((req.method, req.url.path, json.loads(req.content) if req.content else None))
        if req.method == "POST":
            return httpx.Response(201, json={"v1/payout": {"id": 42, "status": "pending"}})
        if req.url.path.endswith("/start"):
            return httpx.Response(200, json=[{"id": 42, "status": "started"}])
        return httpx.Response(200, json={"v1/payout": {"id": 42, "status": "sent"}})

    res = asyncio.run(provider(handler).send(idempotency_key="abc", recipient=R, amount_xof=20000, reason="t"))
    assert res.ok and res.reference == "42"
    (m1, p1, b1), (m2, p2, b2) = calls[0], calls[1]
    assert (m1, p1) == ("POST", "/v1/payouts")
    assert b1["amount"] == 20000 and b1["currency"] == {"iso": "XOF"} and b1["merchant_reference"] == "abc"
    assert b1["customer"]["phone_number"] == {"number": "97123456", "country": "bj"}
    assert (m2, p2, b2) == ("PUT", "/v1/payouts/start", [{"id": 42}])


def test_failed_status_and_client_error():
    def failed(req):
        if req.method == "POST":
            return httpx.Response(201, json={"id": 7, "status": "pending"})
        if req.url.path.endswith("/start"):
            return httpx.Response(200, json=[{"id": 7}])
        return httpx.Response(200, json={"id": 7, "status": "failed", "last_error_code": "INSUFFICIENT_FUNDS"})

    res = asyncio.run(provider(failed).send(idempotency_key="k", recipient=R, amount_xof=1000, reason="t"))
    assert not res.ok and not res.pending and "INSUFFICIENT_FUNDS" in res.error

    def refused(req):
        return httpx.Response(422, json={"message": "mode invalide"})

    res = asyncio.run(provider(refused).send(idempotency_key="k", recipient=R, amount_xof=1000, reason="t"))
    assert not res.ok and "mode invalide" in res.error


def test_server_error_raises_for_manual_retry():
    def down(req):
        return httpx.Response(503)

    try:
        asyncio.run(provider(down).send(idempotency_key="k", recipient=R, amount_xof=1000, reason="t"))
        raise AssertionError("une erreur 5xx doit remonter")
    except RuntimeError:
        pass
