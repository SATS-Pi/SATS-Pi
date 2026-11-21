import os
import tempfile
import time

# Les réglages doivent être posés AVANT l'import de l'application.
os.environ.update(
    LIGHTNING_MODE="mock",
    PAYOUT_MODE="mock",
    FX_MODE="fixed",
    FIXED_BTC_XOF="60000000",
    POLL_INTERVAL_S="0.1",
    MOCK_PAYOUT_DELAY_S="0.05",
    ADMIN_TOKEN="test-token",
    DB_PATH=os.path.join(tempfile.mkdtemp(), "test.db"),
)

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402
from app.providers.pispi import MockPiSpi, PayoutResult, Recipient  # noqa: E402
from app.store import PENDING, Store  # noqa: E402


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def wait_for(client, link_id, wanted, timeout=4.0):
    end = time.time() + timeout
    status = None
    while time.time() < end:
        status = client.get(f"/api/links/{link_id}").json()["status"]
        if status in wanted:
            return status
        time.sleep(0.1)
    return status


def create(client, amount=20000, phone="97 12 34 56", country="BJ", operator=None):
    r = client.post(
        "/api/links",
        json={"phone": phone, "amount_xof": amount, "firstname": "Afi", "lastname": "Dossou",
              "country": country, "operator": operator},
    )
    assert r.status_code == 201, r.text
    return r.json()


def pay(client, link_id):
    assert client.post(f"/api/dev/simulate-payment/{link_id}").status_code == 200


def test_full_flow(client):
    app.state.payout = MockPiSpi()
    link = create(client)
    assert link["status"] == "PENDING_PAYMENT"
    assert link["phone_masked"] == "+229 01 97 ** ** 56"
    # 20 000 + 200 (service 1 %) + 160 (payout 0,8 %, provisoire) = 20 360 F -> 33 934 sats à 60 M F/BTC
    assert link["total_xof"] == 20360
    assert link["sats"] == 33934

    assert client.get(f"/api/links/{link['id']}/qr.svg").headers["content-type"] == "image/svg+xml"

    pay(client, link["id"])
    assert wait_for(client, link["id"], {"COMPLETED"}) == "COMPLETED"

    final = client.get(f"/api/links/{link['id']}").json()
    assert final["payout_ref"].startswith("MOCK-")
    sent = app.state.payout.sent
    assert len(sent) == 1
    assert sent[link["id"]]["amount_xof"] == 20000
    assert sent[link["id"]]["phone"] == "+2290197123456"


def test_no_double_payout(client):
    app.state.payout = MockPiSpi()
    link = create(client, amount=5000)
    pay(client, link["id"])
    assert wait_for(client, link["id"], {"COMPLETED"}) == "COMPLETED"
    time.sleep(0.5)  # plusieurs tours du poller
    assert len(app.state.payout.sent) == 1


def test_claim_is_atomic(tmp_path):
    store = Store(str(tmp_path / "s.db"))
    store.insert(
        dict(id="x", phone="+2290197123456", note="", amount_xof=1000, total_xof=1018,
             sats=1700, rate=6e7, rate_source="fixed", invoice="lnbc", payment_hash="h",
             status=PENDING, created_at=0.0, expires_at=9e12)
    )
    assert store.claim_for_payout("x") is True
    assert store.claim_for_payout("x") is False


@pytest.mark.parametrize(
    "phone,amount",
    [("12345", 5000), ("97 12 34 56", 100), ("97 12 34 56", 10_000_000)],
)
def test_validation(client, phone, amount):
    r = client.post(
        "/api/links",
        json={"phone": phone, "amount_xof": amount, "firstname": "Afi", "lastname": "D"},
    )
    assert r.status_code == 400


def test_phone_formats(client):
    for raw in ["+229 01 97 12 34 56", "0197123456", "97123456", "229 97 12 34 56"]:
        assert create(client, phone=raw)["phone_masked"] == "+229 01 97 ** ** 56"


def test_payout_failure_then_retry(client):
    class Failing:
        async def send(self, **kw):
            return PayoutResult(False, None, "sandbox indisponible")

        async def status(self, reference):
            return PayoutResult(False, reference, "sandbox indisponible")

    app.state.payout = Failing()
    link = create(client, amount=3000)
    pay(client, link["id"])
    assert wait_for(client, link["id"], {"PAYOUT_FAILED"}) == "PAYOUT_FAILED"
    assert "error" not in client.get(f"/api/links/{link['id']}").json()  # pas de fuite interne

    app.state.payout = MockPiSpi()
    url = f"/api/admin/links/{link['id']}/retry"
    assert client.post(url).status_code == 403
    assert client.post(url, headers={"X-Admin-Token": "mauvais"}).status_code == 403
    r = client.post(url, headers={"X-Admin-Token": "test-token"})
    assert r.status_code == 200 and r.json()["status"] == "COMPLETED"
    assert client.post(url, headers={"X-Admin-Token": "test-token"}).status_code == 409
    assert len(app.state.payout.sent) == 1


def test_countries_and_phones(client):
    by = {c["code"]: c for c in client.get("/api/countries").json()}
    assert by["BJ"]["available"] and by["CI"]["available"] and by["TG"]["available"]
    assert not by["SN"]["available"]  # payout non confirmé par FedaPay
    assert create(client, phone="07 08 09 10 11", country="CI", operator="MTN")["phone_masked"] \
        == "+225 07 08 ** ** 11"
    assert create(client, phone="90 12 34 56", country="TG", operator="Togocel")["phone_masked"] \
        == "+228 90 12 ** ** 56"


def test_unavailable_country_and_bad_operator(client):
    body = {"phone": "771234567", "amount_xof": 5000, "firstname": "A", "lastname": "B", "country": "SN"}
    assert client.post("/api/links", json=body).status_code == 400
    body.update(country="TG", phone="90123456", operator="Orange")
    assert client.post("/api/links", json=body).status_code == 400
    assert client.post("/api/links", json={**body, "firstname": ""}).status_code == 422
