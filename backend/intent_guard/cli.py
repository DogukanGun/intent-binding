"""Demo CLI: freeze an intent, settle a bounded micropayment, and watch an
injected out-of-scope instruction get deterministically rejected.

Run:
    python -m intent_guard.cli          # full demo scenario
    python -m intent_guard.cli --help
"""

from __future__ import annotations

import argparse
import dataclasses

from .core import Guard
from .types import PaymentProposal, Provenance, ScopeCaveat

MERCHANT = "0xMerchantCoffeeShop"
ATTACKER = "0xAttackerDrainWallet"
USDC = "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"


def _proposal(**overrides) -> PaymentProposal:
    base = dict(
        target=MERCHANT,
        value=4_000_000,            # 4 USDC (6 decimals)
        token=USDC,
        nonce="",                   # filled per-mandate below
        cnf_jwk="planner-key-thumbprint",
        provenance=Provenance.USER,
        timestamp=1_900,
    )
    base.update(overrides)
    return PaymentProposal(**base)


def run_demo() -> None:
    guard = Guard(signing_key=b"demo-planner-signing-key-32bytes!")

    # 1. Human approves: "buy coffee, at most 5 USDC, to the coffee shop".
    caveat = ScopeCaveat(
        allowed_targets=(MERCHANT,),
        max_value=5_000_000,        # 5 USDC cap
        token=USDC,
        not_before=1_000,
        not_after=2_000,
    )
    mandate = guard.freeze_intent(
        instruction="Pay up to 5 USDC to the coffee shop for one order.",
        caveat=caveat,
        cnf_jwk="planner-key-thumbprint",
    )
    print(f"[freeze]  mandate hash = {mandate.struct_hash[:16]}…  nonce = {mandate.mandate.nonce[:8]}…\n")

    nonce = mandate.mandate.nonce

    print("=== Legitimate payment (within frozen scope) ===")
    ok = _proposal(nonce=nonce)
    d = guard.verify_payment(ok, mandate)
    print(f"  verify -> allowed={d.allowed} reasons={d.reasons}\n")

    # Verify injection vectors BEFORE settling, so each shows its own clean
    # rejection reason (settling consumes the nonce and would add replay noise).
    print("=== Injection #1: scope-lift to attacker + 100 USDC ===")
    evil = _proposal(nonce=nonce, target=ATTACKER, value=100_000_000)
    print(f"  verify -> {guard.verify_payment(evil, mandate).reasons}\n")

    print("=== Injection #2: data-originated payment (quarantined LLM) ===")
    tainted = _proposal(nonce=nonce, provenance=Provenance.TOOL)
    print(f"  verify -> {guard.verify_payment(tainted, mandate).reasons}\n")

    print("=== Injection #3: constraint stripping (raise cap to 1000 USDC) ===")
    relaxed_caveat = dataclasses.replace(caveat, max_value=1_000_000_000)
    forged = dataclasses.replace(
        mandate, mandate=dataclasses.replace(mandate.mandate, caveat=relaxed_caveat)
    )
    big = _proposal(nonce=nonce, value=900_000_000)
    print(f"  verify -> {guard.verify_payment(big, forged).reasons}\n")

    print("=== Settle the legitimate payment ===")
    receipt = guard.settle(mandate, ok)
    print(f"  settle -> tx={receipt.tx_hash[:18]}…  amount={receipt.amount}\n")

    print("=== Replay: re-settle the already-redeemed mandate ===")
    try:
        guard.settle(mandate, ok)
    except PermissionError as exc:
        print(f"  settle -> blocked: {exc}\n")

    print("--- Prometheus metrics ---")
    print(guard.metrics_text())


def main() -> None:
    parser = argparse.ArgumentParser(description="intent_guard x402 intent-binding demo")
    parser.add_argument("command", nargs="?", default="demo", choices=["demo"], help="action")
    parser.parse_args()
    run_demo()


if __name__ == "__main__":
    main()
