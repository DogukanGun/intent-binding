"""EIP-3009 `transferWithAuthorization` builder.

The agent's *redemption object* is a gasless, nonce-protected stablecoin transfer
(USDC supports EIP-3009). The user/session key signs it as EIP-712 typed data over
the token's domain; a relayer (here, 1Shot) broadcasts it so the user pays no gas.
On-chain, the ERC-7710 caveat enforcers gate this transfer against the frozen
mandate before it can settle.
"""

from __future__ import annotations

import os
from typing import Optional

from eth_account import Account
from eth_account.messages import encode_typed_data
from eth_utils import to_checksum_address

TRANSFER_WITH_AUTHORIZATION_TYPES = {
    "TransferWithAuthorization": [
        {"name": "from", "type": "address"},
        {"name": "to", "type": "address"},
        {"name": "value", "type": "uint256"},
        {"name": "validAfter", "type": "uint256"},
        {"name": "validBefore", "type": "uint256"},
        {"name": "nonce", "type": "bytes32"},
    ],
}


def build_authorization(
    *,
    sender: str,
    to: str,
    value: int,
    valid_after: int,
    valid_before: int,
    token: str,
    chain_id: int,
    nonce: Optional[str] = None,
    token_name: str = "USDC",
    token_version: str = "2",
) -> dict:
    """Build the EIP-712 typed data + a serializable authorization tuple."""
    nonce = nonce or ("0x" + os.urandom(32).hex())
    domain = {
        "name": token_name,
        "version": token_version,
        "chainId": chain_id,
        "verifyingContract": to_checksum_address(token),
    }
    message = {
        "from": to_checksum_address(sender),
        "to": to_checksum_address(to),
        "value": value,
        "validAfter": valid_after,
        "validBefore": valid_before,
        "nonce": nonce,
    }
    typed = {
        "domain": domain,
        "types": TRANSFER_WITH_AUTHORIZATION_TYPES,
        "primaryType": "TransferWithAuthorization",
        "message": message,
    }
    return {"typed_data": typed, "authorization": message}


def sign_authorization(typed_data: dict, private_key: str | bytes) -> str:
    """Sign an EIP-3009 authorization; returns the 0x signature for the relayer."""
    signable = encode_typed_data(full_message=typed_data)
    signed = Account.sign_message(signable, private_key)
    sig = signed.signature.hex()
    return sig if sig.startswith("0x") else "0x" + sig
