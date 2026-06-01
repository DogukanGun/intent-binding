"""Real EIP-712 typed-data hashing + secp256k1 signing for IntentMandate.

This replaces the prototype's HMAC stand-in with production cryptography:
  * the mandate is encoded as EIP-712 typed structured data (the same shape a
    wallet like MetaMask signs), so the digest covers EVERY field — relaxing any
    caveat changes the digest and invalidates the signature (constraint-stripping
    defense), and
  * signatures are secp256k1 (`eth-account`), recoverable to the signer's address.

The on-chain ERC-7710 caveat enforcers (AllowedTargets / ValueLte / Timestamp /
Nonce / ERC20) enforce the same bounds in the EVM; this module is the off-chain
pre-flight that mirrors them.
"""

from __future__ import annotations

import dataclasses
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_typed_data, _hash_eip191_message
from eth_utils import keccak, to_checksum_address

from .types import IntentMandate, SignedMandate

ZERO_ADDRESS = "0x0000000000000000000000000000000000000000"
ZERO_BYTES32 = "0x" + "00" * 32

# EIP-712 type definitions for the IntentMandate. Mirrors the on-chain caveat
# dimensions: addresses are `address`, amounts/timestamps `uint256`, the nonce and
# optional calldata commitment `bytes32`.
MANDATE_TYPES = {
    "ScopeCaveat": [
        {"name": "allowedTargets", "type": "address[]"},
        {"name": "maxValue", "type": "uint256"},
        {"name": "token", "type": "address"},
        {"name": "notBefore", "type": "uint256"},
        {"name": "notAfter", "type": "uint256"},
        {"name": "exactCalldataHash", "type": "bytes32"},
    ],
    "IntentMandate": [
        {"name": "instruction", "type": "string"},
        {"name": "caveat", "type": "ScopeCaveat"},
        {"name": "nonce", "type": "bytes32"},
        {"name": "cnfJwk", "type": "bytes32"},
        {"name": "chainId", "type": "uint256"},
    ],
}


def _to_bytes32(value: str) -> str:
    """Normalize an arbitrary string/hex into a 0x bytes32.

    A 0x-hex value of <=32 bytes is left-as-is (right-padded); anything else is
    keccak-hashed so the mapping is deterministic and collision-resistant.
    """
    if value.startswith("0x"):
        raw = bytes.fromhex(value[2:])
        if len(raw) <= 32:
            return "0x" + raw.rjust(32, b"\x00").hex()
    return "0x" + keccak(text=value).hex()


def _cnf_to_bytes32(cnf_jwk: str) -> str:
    """cnf.jwk thumbprint -> bytes32 (keccak) so it fits the typed field."""
    if cnf_jwk.startswith("0x") and len(bytes.fromhex(cnf_jwk[2:])) == 32:
        return cnf_jwk
    return "0x" + keccak(text=cnf_jwk).hex()


def build_typed_data(
    mandate: IntentMandate, verifying_contract: str = ZERO_ADDRESS
) -> dict:
    """Build the full EIP-712 typed-data document for a mandate."""
    c = mandate.caveat
    domain = {
        "name": "IntentGuard",
        "version": "1",
        "chainId": mandate.chain_id,
        "verifyingContract": to_checksum_address(verifying_contract),
    }
    message = {
        "instruction": mandate.instruction,
        "caveat": {
            "allowedTargets": [to_checksum_address(t) for t in c.allowed_targets],
            "maxValue": c.max_value,
            "token": to_checksum_address(c.token),
            "notBefore": c.not_before,
            "notAfter": c.not_after,
            "exactCalldataHash": c.exact_calldata_hash or ZERO_BYTES32,
        },
        "nonce": _to_bytes32(mandate.nonce),
        "cnfJwk": _cnf_to_bytes32(mandate.cnf_jwk),
        "chainId": mandate.chain_id,
    }
    return {
        "domain": domain,
        "types": MANDATE_TYPES,
        "primaryType": "IntentMandate",
        "message": message,
    }


def mandate_digest(
    mandate: IntentMandate, verifying_contract: str = ZERO_ADDRESS
) -> str:
    """The EIP-712 digest that gets signed — covers every mandate field."""
    typed = build_typed_data(mandate, verifying_contract)
    signable = encode_typed_data(full_message=typed)
    return "0x" + _hash_eip191_message(signable).hex()


def sign_mandate(
    mandate: IntentMandate,
    private_key: str | bytes,
    verifying_contract: str = ZERO_ADDRESS,
) -> str:
    """Sign a mandate with a secp256k1 key; returns the 0x signature."""
    typed = build_typed_data(mandate, verifying_contract)
    signable = encode_typed_data(full_message=typed)
    signed = Account.sign_message(signable, private_key)
    return signed.signature.hex() if signed.signature.hex().startswith("0x") else "0x" + signed.signature.hex()


def recover_signer(
    mandate: IntentMandate,
    signature: str,
    verifying_contract: str = ZERO_ADDRESS,
) -> Optional[str]:
    """Recover the checksummed signer address from a mandate signature."""
    typed = build_typed_data(mandate, verifying_contract)
    signable = encode_typed_data(full_message=typed)
    try:
        return Account.recover_message(signable, signature=signature)
    except Exception:
        return None
