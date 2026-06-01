"""Core intent-binding engine: freeze -> verify -> settle.

The enforcement chain in `verify_payment` is the heart of the system. Each check
corresponds to an ERC-7710 caveat enforcer or a protocol-level guard proven
necessary by the experiment. A proposal is allowed ONLY when every check passes;
otherwise `Decision.reasons` lists each violated caveat.

Cryptography
------------
Production EIP-712 + secp256k1 via `eth-account` (see `eip712.py`). The mandate is
signed as EIP-712 typed data — the same document a wallet signs — so the digest
covers ALL fields and any constraint relaxation invalidates the signature. The
on-chain ERC-7710 caveats enforce the same bounds in the EVM; this is the
off-chain pre-flight that mirrors them.
"""

from __future__ import annotations

import hashlib
import logging
import os
from typing import Optional

from eth_account import Account

from . import eip712
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

# EIP-712 / secp256k1 only. Accepting another alg would enable algorithm-confusion.
SUPPORTED_ALGS: frozenset[str] = frozenset({"EIP712"})


class Guard:
    """Stateful intent-binding guard.

    Construct with the privileged planner's signing key (the authority that
    freezes user intent). For the production path where the *wallet* signs the
    mandate externally (MetaMask EIP-712), construct with `expected_signer` and
    attach the wallet signature via `attach_signature`.
    """

    def __init__(
        self,
        signing_key: Optional[str | bytes] = None,
        *,
        expected_signer: Optional[str] = None,
        verifying_contract: str = eip712.ZERO_ADDRESS,
    ) -> None:
        if signing_key is None and expected_signer is None:
            # Generate an ephemeral key so the guard is usable out of the box.
            signing_key = "0x" + os.urandom(32).hex()
        self._account = Account.from_key(signing_key) if signing_key is not None else None
        self._expected_signer = (
            expected_signer or (self._account.address if self._account else None)
        )
        self._verifying_contract = verifying_contract
        self._consumed_nonces: set[str] = set()
        self.metrics: dict[str, int] = {
            "frozen": 0,
            "verified_allow": 0,
            "verified_deny": 0,
            "settled": 0,
            "replay_blocked": 0,
        }

    @property
    def signer_address(self) -> Optional[str]:
        return self._expected_signer

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
        """Capture human-approved intent into a signed, immutable mandate.

        Signs locally with the planner key. (In the wallet-signs-externally flow
        use `build_mandate` + `attach_signature` instead.)
        """
        if self._account is None:
            raise RuntimeError(
                "Guard has no signing key; use build_mandate()+attach_signature() "
                "for the wallet-signed flow."
            )
        mandate = self.build_mandate(instruction, caveat, cnf_jwk, nonce=nonce, chain_id=chain_id)
        digest = eip712.mandate_digest(mandate, self._verifying_contract)
        signature = eip712.sign_mandate(mandate, self._account.key, self._verifying_contract)
        signed = SignedMandate(mandate=mandate, struct_hash=digest, signature=signature, alg="EIP712")
        self.metrics["frozen"] += 1
        logger.info("intent_frozen", extra={"mandate_hash": digest, "nonce": mandate.nonce})
        return signed

    def build_mandate(
        self,
        instruction: str,
        caveat: ScopeCaveat,
        cnf_jwk: str,
        *,
        nonce: Optional[str] = None,
        chain_id: int = 8453,
    ) -> IntentMandate:
        """Build the unsigned mandate (for the wallet-signs-externally flow)."""
        return IntentMandate(
            instruction=instruction,
            caveat=caveat,
            nonce=nonce or ("0x" + os.urandom(32).hex()),
            cnf_jwk=cnf_jwk,
            chain_id=chain_id,
        )

    def attach_signature(self, mandate: IntentMandate, signature: str) -> SignedMandate:
        """Wrap a mandate with an externally produced wallet signature."""
        digest = eip712.mandate_digest(mandate, self._verifying_contract)
        self.metrics["frozen"] += 1
        return SignedMandate(mandate=mandate, struct_hash=digest, signature=signature, alg="EIP712")

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

        # 2. Signature coverage — recompute the EIP-712 digest over ALL fields and
        #    recover the signer. A stripped/relaxed constraint changes the digest;
        #    a forged signature recovers to the wrong address.
        recomputed = eip712.mandate_digest(m, self._verifying_contract)
        if recomputed != signed.struct_hash:
            reasons.append("mandate_tampered:hash_mismatch")
        else:
            recovered = eip712.recover_signer(m, signed.signature, self._verifying_contract)
            if recovered is None:
                reasons.append("bad_signature")
            elif self._expected_signer is not None and recovered.lower() != self._expected_signer.lower():
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
        if proposal.target.lower() not in {t.lower() for t in c.allowed_targets}:
            reasons.append("target_not_allowed")

        # 7. Asset + ValueLte enforcer.
        if proposal.token.lower() != c.token.lower():
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
    def settle(
        self, signed: SignedMandate, proposal: PaymentProposal, *, tx_hash: Optional[str] = None
    ) -> Receipt:
        """Re-verify then mark redeemed, consuming the nonce against replay.

        `tx_hash` is supplied by the relayer when the redemption lands on-chain;
        absent that, a deterministic placeholder is used (off-chain dry run).
        """
        decision = self.verify_payment(proposal, signed)
        if not decision.allowed:
            raise PermissionError(f"settlement refused: {', '.join(decision.reasons)}")

        if signed.mandate.nonce in self._consumed_nonces:
            self.metrics["replay_blocked"] += 1
            raise PermissionError("settlement refused: nonce_replayed")
        self._consumed_nonces.add(signed.mandate.nonce)

        if tx_hash is None:
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

    def mark_consumed(self, nonce: str) -> None:
        """Record a nonce as spent (e.g. after the relayer confirms on-chain)."""
        self._consumed_nonces.add(nonce)

    # ----------------------------------------------------------------- metrics
    def metrics_text(self) -> str:
        """Render counters in Prometheus text-exposition format."""
        lines = []
        for name, value in self.metrics.items():
            lines.append(f"# TYPE intent_guard_{name} counter")
            lines.append(f"intent_guard_{name} {value}")
        return "\n".join(lines) + "\n"
