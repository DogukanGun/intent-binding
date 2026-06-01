"""intent_guard — freeze user intent into a signed mandate and enforce it as a
deterministic commitment that a prompt-injected agent cannot relax.

This is a research prototype distilling the winning regime from the
x402-intent-binding-injection experiment (intent-bound ASR = 0.0 vs unbounded
ASR ~= 0.50). It combines:

  * pre-signature mandate freezing  (intent captured at the human-approval moment)
  * caveat enforcement              (ERC-7710-style enforcers: targets/value/time/nonce)
  * provenance separation           (CaMeL: quarantined-LLM data cannot originate pay)
  * replay / confusion protections  (nonce uniqueness, ES256-only, full-field coverage)

Public API:
    Guard.freeze_intent(instruction, caveat, cnf_jwk) -> SignedMandate
    Guard.verify_payment(proposal, signed_mandate)    -> Decision
    Guard.settle(signed_mandate, proposal)            -> Receipt
"""

from .types import (
    Decision,
    IntentMandate,
    PaymentProposal,
    Provenance,
    Receipt,
    ScopeCaveat,
    SignedMandate,
)
from .core import Guard, SUPPORTED_ALGS

__all__ = [
    "Guard",
    "SUPPORTED_ALGS",
    "Decision",
    "IntentMandate",
    "PaymentProposal",
    "Provenance",
    "Receipt",
    "ScopeCaveat",
    "SignedMandate",
]

__version__ = "0.1.0"
