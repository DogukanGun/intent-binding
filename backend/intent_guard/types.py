"""Typed data model for the intent-binding flow.

All dataclasses are frozen (immutable) so a mandate cannot be mutated in place
after it is signed — any change must produce a new struct hash, which is exactly
the property that defeats constraint-stripping injection attacks.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class Provenance(str, Enum):
    """Origin label for a payment proposal (CaMeL-style provenance tracking).

    USER  -> originated by the privileged planner from human-approved intent.
    TOOL  -> derived from quarantined-LLM / tool output (untrusted, tainted).

    Only USER-provenance proposals may originate a payment. This blocks the
    split-agent attack where injected web/tool content tries to spend funds.
    """

    USER = "user"
    TOOL = "tool"


@dataclass(frozen=True)
class ScopeCaveat:
    """Bounds on a payment, mirroring ERC-7710 caveat enforcers.

    Each field maps to an on-chain enforcer in the production contracts:
        allowed_targets      -> AllowedTargets enforcer
        max_value / token    -> ValueLte + ERC20 transfer-amount enforcer
        not_before/not_after -> Timestamp enforcer (replay temporal window)
        exact_calldata_hash  -> ExactCalldata enforcer (optional, strictest)
    """

    allowed_targets: tuple[str, ...]
    max_value: int
    token: str
    not_before: int
    not_after: int
    exact_calldata_hash: Optional[str] = None


@dataclass(frozen=True)
class IntentMandate:
    """The frozen, human-approved intent. Every field is signature-covered."""

    instruction: str          # human-readable intent shown at approval time
    caveat: ScopeCaveat       # machine-enforced bounds
    nonce: str                # unique per mandate (Nonce enforcer / replay guard)
    cnf_jwk: str              # confirmation-key thumbprint binding the planner
    chain_id: int = 8453      # default: Base mainnet


@dataclass(frozen=True)
class SignedMandate:
    """A mandate plus its deterministic commitment and signature."""

    mandate: IntentMandate
    struct_hash: str          # EIP-712 digest over ALL mandate fields
    signature: str
    alg: str = "EIP712"       # EIP712/secp256k1 only — anything else is algorithm confusion


@dataclass(frozen=True)
class PaymentProposal:
    """A payment the agent wants to make; validated against a SignedMandate."""

    target: str               # recipient (x402 payTo)
    value: int                # amount in token base units
    token: str
    nonce: str                # must equal the mandate nonce
    cnf_jwk: str              # must equal the mandate cnf (same-agent proof)
    provenance: Provenance    # where this proposal originated
    timestamp: int            # proposal time (unix seconds)
    calldata_hash: Optional[str] = None


@dataclass(frozen=True)
class Decision:
    """Result of verify_payment. `allowed` is True only if `reasons` is empty."""

    allowed: bool
    reasons: tuple[str, ...] = field(default_factory=tuple)
    mandate_hash: Optional[str] = None


@dataclass(frozen=True)
class Receipt:
    """Settlement record returned once a verified payment is redeemed."""

    settled: bool
    tx_hash: str
    mandate_hash: str
    amount: int
    target: str
