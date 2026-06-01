"""Core intent-binding engine: freeze -> verify -> settle.

The enforcement chain in `verify_payment` is the heart of the prototype. Each
check corresponds to an ERC-7710 caveat enforcer or a protocol-level guard
proven necessary by the experiment. A proposal is allowed ONLY when every check
passes; otherwise `Decision.reasons` lists each violated caveat.

Cryptography note
-----------------
This prototype uses HMAC-SHA256 as a stand-in for ES256/EIP-712 signing so it
runs on the standard library with zero install. The security *properties* are
faithful: the signature covers a deterministic hash of ALL mandate fields, so
any constraint relaxation invalidates it. In production, swap `_Signer` for
eth-account (EIP-712) / PyJWT-ES256 — the verify chain is unchanged.
"""

from __future__ import annotations

import dataclasses
import hashlib
import hmac
import json
import logging
import os
from typing import Optional

from .types import (
    Decision,
    IntentMandate,
    PaymentProposal,
    Provenance,
    Receipt,
    ScopeCaveat,
    SignedMandate,
)

logger = logging.getLogger("intent_guard")

# ES256 only. Accepting "HS256"/"none" would enable algorithm-confusion attacks.
SUPPORTED_ALGS: frozenset[str] = frozenset({"ES256"})


def _canonical(obj: object) -> bytes:
    """Deterministic JSON encoding for hashing (sorted keys, no whitespace)."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _struct_hash(mandate: IntentMandate) -> str:
    """EIP-712-style struct hash covering EVERY mandate field.

    Stand-in: sha256 here; keccak256 over typed EIP-712 data in production.
    Covering all fields is what makes constraint-stripping detectable.
    """
    payload = dataclasses.asdict(mandate)  # includes caveat + nonce + cnf + chain
    return hashlib.sha256(_canonical(payload)).hexdigest()


class _Signer:
    """Pluggable signer. HMAC stand-in for ES256/EIP-712 (see module docstring)."""

    def __init__(self, key: bytes) -> None:
        self._key = key

    def sign(self, struct_hash: str) -> str:
        return hmac.new(self._key, struct_hash.encode("utf-8"), hashlib.sha256).hexdigest()

    def verify(self, struct_hash: str, signature: str) -> bool:
        expected = self.sign(struct_hash)
        return hmac.compare_digest(expected, signature)


class Guard:
    """Stateful intent-binding guard.

    Holds the signing key and a consumed-nonce set so a redeemed mandate cannot
    be replayed. Construct once per signing authority (the privileged planner).
    """

    def __init__(self, signing_key: Optional[bytes] = None) -> None:
        self._signer = _Signer(signing_key or os.urandom(32))
        self._consumed_nonces: set[str] = set()
        self.metrics: dict[str, int] = {
            "frozen": 0,
            "verified_allow": 0,
            "verified_deny": 0,
            "settled": 0,
            "replay_blocked": 0,
        }

    # ------------------------------------------------------------------ freeze
    def freeze_intent(
        self,
        instruction: str,
        caveat: ScopeCaveat,
        cnf_jwk: str,
        *,
        nonce: Optional[str] = None,
        chain_id: int = 8453,
    ) -> SignedMandate:
        """Capture human-approved intent into a signed, immutable mandate."""
        mandate = IntentMandate(
            instruction=instruction,
            caveat=caveat,
            nonce=nonce or os.urandom(16).hex(),
            cnf_jwk=cnf_jwk,
            chain_id=chain_id,
        )
        struct_hash = _struct_hash(mandate)
        signed = SignedMandate(
            mandate=mandate,
            struct_hash=struct_hash,
            signature=self._signer.sign(struct_hash),
            alg="ES256",
        )
        self.metrics["frozen"] += 1
        logger.info("intent_frozen", extra={"mandate_hash": struct_hash, "nonce": mandate.nonce})
        return signed

    # ------------------------------------------------------------------ verify
    def verify_payment(
        self,
        proposal: PaymentProposal,
        signed: SignedMandate,
        *,
        now: Optional[int] = None,
    ) -> Decision:
        """Run the full caveat-enforcer chain. Allowed iff no reason fires."""
        reasons: list[str] = []
        m = signed.mandate
        c = m.caveat

        # 1. Algorithm pinning — block algorithm-confusion attacks.
        if signed.alg not in SUPPORTED_ALGS:
            reasons.append(f"alg_confusion:{signed.alg}")

        # 2. Signature coverage — recompute hash over ALL fields and verify.
        #    A stripped/relaxed constraint changes the hash -> signature fails.
        recomputed = _struct_hash(m)
        if recomputed != signed.struct_hash:
            reasons.append("mandate_tampered:hash_mismatch")
        elif not self._signer.verify(signed.struct_hash, signed.signature):
            reasons.append("bad_signature")

        # 3. Provenance separation (CaMeL) — untrusted data cannot originate pay.
        if proposal.provenance is not Provenance.USER:
            reasons.append(f"untrusted_provenance:{proposal.provenance.value}")

        # 4. Same-agent binding — cnf.jwk must match (block split-agent attack).
        if proposal.cnf_jwk != m.cnf_jwk:
            reasons.append("cnf_mismatch")

        # 5. Nonce binding + replay guard.
        if proposal.nonce != m.nonce:
            reasons.append("nonce_mismatch")
        elif m.nonce in self._consumed_nonces:
            reasons.append("nonce_replayed")

        # 6. AllowedTargets enforcer.
        if proposal.target not in c.allowed_targets:
            reasons.append("target_not_allowed")

        # 7. Asset + ValueLte enforcer.
        if proposal.token != c.token:
            reasons.append("token_mismatch")
        if proposal.value > c.max_value:
            reasons.append("value_exceeds_cap")

        # 8. Timestamp enforcer (temporal replay window).
        t = proposal.timestamp if now is None else now
        if t < c.not_before or t > c.not_after:
            reasons.append("outside_time_window")

        # 9. ExactCalldata enforcer (optional, strictest binding).
        if c.exact_calldata_hash is not None and proposal.calldata_hash != c.exact_calldata_hash:
            reasons.append("calldata_mismatch")

        allowed = not reasons
        self.metrics["verified_allow" if allowed else "verified_deny"] += 1
        logger.info(
            "payment_verified",
            extra={"allowed": allowed, "reasons": reasons, "mandate_hash": signed.struct_hash},
        )
        return Decision(allowed=allowed, reasons=tuple(reasons), mandate_hash=signed.struct_hash)

    # ------------------------------------------------------------------ settle
    def settle(self, signed: SignedMandate, proposal: PaymentProposal) -> Receipt:
        """Re-verify then redeem, consuming the nonce so it cannot be replayed."""
        decision = self.verify_payment(proposal, signed)
        if not decision.allowed:
            raise PermissionError(f"settlement refused: {', '.join(decision.reasons)}")

        if signed.mandate.nonce in self._consumed_nonces:
            self.metrics["replay_blocked"] += 1
            raise PermissionError("settlement refused: nonce_replayed")
        self._consumed_nonces.add(signed.mandate.nonce)

        tx_hash = "0x" + hashlib.sha256(
            (signed.struct_hash + signed.mandate.nonce + "redeem").encode()
        ).hexdigest()
        self.metrics["settled"] += 1
        logger.info("settled", extra={"tx_hash": tx_hash, "amount": proposal.value})
        return Receipt(
            settled=True,
            tx_hash=tx_hash,
            mandate_hash=signed.struct_hash,
            amount=proposal.value,
            target=proposal.target,
        )

    # ----------------------------------------------------------------- metrics
    def metrics_text(self) -> str:
        """Render counters in Prometheus text-exposition format."""
        lines = []
        for name, value in self.metrics.items():
            lines.append(f"# TYPE intent_guard_{name} counter")
            lines.append(f"intent_guard_{name} {value}")
        return "\n".join(lines) + "\n"
