"""x402 injection harness + FastAPI end-to-end tests (offline heuristic LLM)."""

from fastapi.testclient import TestClient

from x402.injections import FAMILIES, build_invoice
from x402.merchant import make_invoice_402
import app as app_module

MERCHANT = "0x1111111111111111111111111111111111111111"
ATTACKER = "0x2222222222222222222222222222222222222222"
USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"


def test_all_families_build():
    assert len(FAMILIES) == 9
    for fam in FAMILIES:
        inv = build_invoice(fam.name, merchant=MERCHANT, attacker=ATTACKER, amount=4, cap=5)
        assert inv["poisoned"] and inv["text"]
    clean = build_invoice("clean", merchant=MERCHANT, attacker=ATTACKER)
    assert not clean["poisoned"] and MERCHANT in clean["text"]


def test_recipient_attacks_embed_attacker():
    for name in ("recipient_redirection", "priority_hijack", "adaptive_strongest"):
        inv = build_invoice(name, merchant=MERCHANT, attacker=ATTACKER, amount=4, cap=5)
        assert ATTACKER in inv["text"]


def test_merchant_402_shape():
    r = make_invoice_402(attack="clean", merchant=MERCHANT, attacker=ATTACKER, token=USDC)
    assert r["status"] == 402
    assert r["payment"]["accepts"][0]["payTo"] == MERCHANT
    assert r["payment"]["accepts"][0]["asset"] == USDC


def test_app_end_to_end():
    client = TestClient(app_module.app)

    # freeze a mandate
    fr = client.post("/session/freeze", json={"cap_usdc": 5, "amount_usdc": 4}).json()
    assert fr["mandate_hash"].startswith("0x")
    assert fr["caveat"]["allowed_targets"] == [app_module.MERCHANT]

    # clean + guarded -> settles to merchant
    clean = client.post("/agent/run", json={"attack": "clean", "guarded": True, "planner": "naive"}).json()
    assert clean["settled"] and not clean["attack_succeeded"]

    # poisoned + unguarded -> attack succeeds (baseline)
    eviln = client.post("/agent/run", json={"attack": "adaptive_strongest", "guarded": False, "planner": "naive"}).json()
    assert eviln["attack_succeeded"]

    # poisoned + guarded -> blocked
    guarded = client.post("/agent/run", json={"attack": "adaptive_strongest", "guarded": True, "planner": "naive"}).json()
    assert not guarded["settled"] and not guarded["attack_succeeded"]
    assert "target_not_allowed" in guarded["reasons"]
