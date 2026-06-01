"""EIP-712 signing / recovery tests for the productionized guard."""

import dataclasses

from eth_account import Account

from intent_guard import Guard, PaymentProposal, Provenance, ScopeCaveat
from intent_guard import eip712

USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
MERCHANT = "0x1111111111111111111111111111111111111111"

CAVEAT = ScopeCaveat(
    allowed_targets=(MERCHANT,),
    max_value=5_000_000,
    token=USDC,
    not_before=0,
    not_after=10_000,
)


def _legit(nonce):
    return PaymentProposal(
        target=MERCHANT, value=4_000_000, token=USDC, nonce=nonce,
        cnf_jwk="cnf-A", provenance=Provenance.USER, timestamp=100,
    )


def test_digest_is_deterministic():
    g = Guard(signing_key="0x" + "11" * 32)
    m = g.build_mandate("pay <=5 USDC", CAVEAT, "cnf-A", nonce="0x" + "ab" * 32)
    d1 = eip712.mandate_digest(m)
    d2 = eip712.mandate_digest(m)
    assert d1 == d2 and d1.startswith("0x") and len(d1) == 66


def test_sign_recovers_to_signer():
    key = "0x" + "11" * 32
    acct = Account.from_key(key)
    g = Guard(signing_key=key)
    signed = g.freeze_intent("pay <=5 USDC", CAVEAT, "cnf-A")
    recovered = eip712.recover_signer(signed.mandate, signed.signature)
    assert recovered.lower() == acct.address.lower()
    # full verify chain accepts it
    assert g.verify_payment(_legit(signed.mandate.nonce), signed).allowed


def test_wrong_expected_signer_rejected():
    # Mandate signed by key A, but the guard expects address B -> bad_signature.
    key_a = "0x" + "11" * 32
    other = Account.from_key("0x" + "22" * 32).address
    signer_guard = Guard(signing_key=key_a)
    signed = signer_guard.freeze_intent("pay <=5 USDC", CAVEAT, "cnf-A")

    verifier = Guard(expected_signer=other)
    d = verifier.verify_payment(_legit(signed.mandate.nonce), signed)
    assert not d.allowed and "bad_signature" in d.reasons


def test_external_wallet_flow():
    # Wallet signs externally; backend attaches the signature and verifies.
    wallet_key = "0x" + "33" * 32
    wallet_addr = Account.from_key(wallet_key).address
    backend = Guard(expected_signer=wallet_addr)

    mandate = backend.build_mandate("pay <=5 USDC", CAVEAT, "cnf-A")
    sig = eip712.sign_mandate(mandate, wallet_key)
    signed = backend.attach_signature(mandate, sig)

    assert backend.verify_payment(_legit(mandate.nonce), signed).allowed


def test_tamper_after_sign_detected():
    # Relax the cap after signing; digest no longer matches -> tampered.
    g = Guard(signing_key="0x" + "11" * 32)
    signed = g.freeze_intent("pay <=5 USDC", CAVEAT, "cnf-A")
    relaxed = dataclasses.replace(signed.mandate.caveat, max_value=10**18)
    forged = dataclasses.replace(
        signed, mandate=dataclasses.replace(signed.mandate, caveat=relaxed)
    )
    big = dataclasses.replace(_legit(signed.mandate.nonce), value=10**12)
    d = g.verify_payment(big, forged)
    assert not d.allowed and "mandate_tampered:hash_mismatch" in d.reasons


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_") and callable(fn):
            fn()
            print(f"ok  {name}")
    print("all eip712 tests passed")
