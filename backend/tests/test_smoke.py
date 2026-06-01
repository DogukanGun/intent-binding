"""Smoke test for the intent-binding guard.

Asserts the core security property: legitimate in-scope payments are allowed,
while every scope-lifting injection vector is deterministically rejected.
Run:  python -m pytest tests/test_smoke.py   (or: python tests/test_smoke.py)
"""

import dataclasses

from intent_guard import Guard, PaymentProposal, Provenance, ScopeCaveat

USDC = "0xUSDC"
MERCHANT = "0xMerchant"
ATTACKER = "0xAttacker"


def _setup():
    guard = Guard(signing_key=b"k" * 32)
    caveat = ScopeCaveat(
        allowed_targets=(MERCHANT,),
        max_value=5_000_000,
        token=USDC,
        not_before=0,
        not_after=10_000,
    )
    mandate = guard.freeze_intent("pay <=5 USDC to merchant", caveat, "cnf-A")
    nonce = mandate.mandate.nonce
    legit = PaymentProposal(
        target=MERCHANT, value=4_000_000, token=USDC, nonce=nonce,
        cnf_jwk="cnf-A", provenance=Provenance.USER, timestamp=100,
    )
    return guard, caveat, mandate, legit, nonce


def test_legit_allowed_and_settles():
    guard, _, mandate, legit, _ = _setup()
    assert guard.verify_payment(legit, mandate).allowed
    receipt = guard.settle(mandate, legit)
    assert receipt.settled and receipt.amount == 4_000_000


def test_scope_lift_rejected():
    guard, _, mandate, _, nonce = _setup()
    evil = PaymentProposal(
        target=ATTACKER, value=100_000_000, token=USDC, nonce=nonce,
        cnf_jwk="cnf-A", provenance=Provenance.USER, timestamp=100,
    )
    d = guard.verify_payment(evil, mandate)
    assert not d.allowed
    assert "target_not_allowed" in d.reasons and "value_exceeds_cap" in d.reasons


def test_tool_provenance_rejected():
    guard, _, mandate, legit, _ = _setup()
    tainted = dataclasses.replace(legit, provenance=Provenance.TOOL)
    d = guard.verify_payment(tainted, mandate)
    assert not d.allowed and any(r.startswith("untrusted_provenance") for r in d.reasons)


def test_constraint_stripping_rejected():
    guard, caveat, mandate, _, nonce = _setup()
    relaxed = dataclasses.replace(caveat, max_value=10**12)
    forged = dataclasses.replace(
        mandate, mandate=dataclasses.replace(mandate.mandate, caveat=relaxed)
    )
    big = PaymentProposal(
        target=MERCHANT, value=10**9, token=USDC, nonce=nonce,
        cnf_jwk="cnf-A", provenance=Provenance.USER, timestamp=100,
    )
    d = guard.verify_payment(big, forged)
    assert not d.allowed and "mandate_tampered:hash_mismatch" in d.reasons


def test_alg_confusion_rejected():
    guard, _, mandate, legit, _ = _setup()
    confused = dataclasses.replace(mandate, alg="HS256")
    d = guard.verify_payment(legit, confused)
    assert not d.allowed and any(r.startswith("alg_confusion") for r in d.reasons)


def test_replay_blocked():
    guard, _, mandate, legit, _ = _setup()
    guard.settle(mandate, legit)
    try:
        guard.settle(mandate, legit)
        assert False, "replay should have been blocked"
    except PermissionError as exc:
        assert "nonce_replayed" in str(exc)


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all smoke tests passed")
