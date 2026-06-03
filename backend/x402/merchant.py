"""Mock x402 merchant — emits HTTP 402 Payment Required with payment requirements.

Follows the x402 shape: a resource server responds 402 with an `accepts` list of
payment requirements (scheme/network/amount/payTo/asset). The agent reads the
invoice (which may be poisoned) and pays via a mandate-scoped redemption.
"""

from __future__ import annotations

from .injections import build_invoice

USDC_DECIMALS = 6


def _base_units(amount_usdc: float) -> str:
    return str(int(round(amount_usdc * 10**USDC_DECIMALS)))


def payment_requirements(
    *,
    resource: str,
    pay_to: str,
    amount_usdc: float,
    token: str,
    network: str = "base-sepolia",
    description: str = "Blue Bottle Coffee — oat latte",
) -> dict:
    """x402 `accepts` payment-requirements block."""
    return {
        "x402Version": 1,
        "accepts": [
            {
                "scheme": "exact",
                "network": network,
                "maxAmountRequired": _base_units(amount_usdc),
                "resource": resource,
                "description": description,
                "payTo": pay_to,
                "asset": token,
                "extra": {"name": "USDC", "decimals": USDC_DECIMALS},
            }
        ],
    }


def make_invoice_402(
    *,
    attack: str | None,
    merchant: str,
    attacker: str,
    token: str,
    amount_usdc: float = 4.0,
    cap_usdc: float = 5.0,
    resource: str = "https://merchant.example/orders/042",
    network: str = "base-sepolia",
) -> dict:
    """Full 402 response: payment requirements + the (clean or poisoned) invoice."""
    invoice = build_invoice(
        attack, merchant=merchant, attacker=attacker, amount=amount_usdc, cap=cap_usdc
    )
    reqs = payment_requirements(
        resource=resource, pay_to=merchant, amount_usdc=amount_usdc, token=token, network=network
    )
    return {"status": 402, "payment": reqs, "invoice": invoice}
