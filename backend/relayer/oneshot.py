"""1Shot permissionless relayer client (EIP-7710 gas abstraction).

The public relayer is keyless JSON-RPC at https://relayer.1shotapi.com/relayers.
Gas is paid in a stablecoin included in the transaction — no pre-funded paymaster,
no signup. Flow:

    relayer_getCapabilities  -> chains, accepted fee tokens, feeCollector, target
    relayer_getFeeData       -> rough fee quote (gasPrice/rate/minFee/context)
    relayer_estimate7710...  -> validate + lock final fee (returns context)
    relayer_send7710...      -> submit signed delegation + calls (returns TaskId)
    relayer_getStatus        -> poll to terminal state (Confirmed/Reverted/Rejected)

`delegationContext` is the signed ERC-7710/7702 delegation produced by the frontend
(MetaMask). `transactions` are the encoded execution calls (e.g. USDC.transfer).
"""

from __future__ import annotations

import time
from typing import Any, Optional

import httpx
from eth_abi import encode as abi_encode
from eth_utils import function_signature_to_4byte_selector, to_checksum_address

RELAYER_URL = "https://relayer.1shotapi.com/relayers"
_TRANSFER_SELECTOR = function_signature_to_4byte_selector("transfer(address,uint256)")


def encode_usdc_transfer(to: str, amount: int) -> str:
    """ABI-encode an ERC-20 transfer(to, amount) call -> 0x calldata."""
    args = abi_encode(["address", "uint256"], [to_checksum_address(to), int(amount)])
    return "0x" + (_TRANSFER_SELECTOR + args).hex()


class OneShotRelayer:
    def __init__(
        self,
        base_url: str = RELAYER_URL,
        chain_id: int = 84532,
        timeout: float = 30.0,
        client: Optional[httpx.Client] = None,
    ):
        self.base_url = base_url
        self.chain_id = chain_id
        self._client = client or httpx.Client(timeout=timeout)
        self._rpc_id = 0

    # ----------------------------------------------------------------- JSON-RPC
    def _rpc(self, method: str, params: Any) -> Any:
        self._rpc_id += 1
        payload = {"jsonrpc": "2.0", "id": self._rpc_id, "method": method, "params": params}
        resp = self._client.post(self.base_url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        if "error" in data and data["error"]:
            raise RuntimeError(f"1shot relayer error: {data['error']}")
        return data.get("result")

    def get_capabilities(self, version: str = "1") -> Any:
        return self._rpc("relayer_getCapabilities", [version])

    def get_fee_data(self, token: str) -> Any:
        return self._rpc("relayer_getFeeData", {"chainId": str(self.chain_id), "token": token})

    def estimate_7710(
        self, *, delegation_context: str, transactions: list, fee_token: str, fee_amount: int
    ) -> Any:
        return self._rpc(
            "relayer_estimate7710Transaction",
            {
                "chainId": str(self.chain_id),
                "delegationContext": delegation_context,
                "transactions": transactions,
                "feeToken": fee_token,
                "feeAmount": str(fee_amount),
            },
        )

    def send_7710(
        self,
        *,
        delegation_context: str,
        transactions: list,
        fee_token: str,
        fee_amount: int,
        context: Any,
        destination_url: Optional[str] = None,
    ) -> str:
        params: dict = {
            "delegationContext": delegation_context,
            "transactions": transactions,
            "feeToken": fee_token,
            "feeAmount": str(fee_amount),
            "context": context,
        }
        if destination_url:
            params["destinationUrl"] = destination_url
        result = self._rpc("relayer_send7710Transaction", params)
        return result["TaskId"] if isinstance(result, dict) else result

    def get_status(self, task_id: str) -> Any:
        return self._rpc("relayer_getStatus", [task_id])

    # ------------------------------------------------------------- high level
    def relay_usdc_payment(
        self,
        *,
        delegation_context: str,
        token: str,
        to: str,
        amount: int,
        fee_token: Optional[str] = None,
        poll: bool = True,
        poll_interval: float = 2.0,
        poll_timeout: float = 60.0,
    ) -> dict:
        """Relay a mandate-scoped USDC transfer gaslessly. Returns status dict."""
        fee_token = fee_token or token  # pay the gas fee in the same stablecoin
        call = {
            "to": to_checksum_address(token),
            "data": encode_usdc_transfer(to, amount),
            "value": "0",
        }
        fee = self.get_fee_data(fee_token)
        fee_amount = int(fee.get("minFee", 0)) if isinstance(fee, dict) else 0
        est = self.estimate_7710(
            delegation_context=delegation_context, transactions=[call],
            fee_token=fee_token, fee_amount=fee_amount,
        )
        context = est.get("context") if isinstance(est, dict) else fee.get("context")
        required = int(est.get("requiredPaymentAmount", fee_amount)) if isinstance(est, dict) else fee_amount
        task_id = self.send_7710(
            delegation_context=delegation_context, transactions=[call],
            fee_token=fee_token, fee_amount=required, context=context,
        )
        if not poll:
            return {"task_id": task_id, "status": "Submitted"}
        deadline = time.time() + poll_timeout
        status = {"task_id": task_id, "status": "Pending"}
        while time.time() < deadline:
            st = self.get_status(task_id)
            status = st if isinstance(st, dict) else {"task_id": task_id, "status": str(st)}
            if str(status.get("status")) in ("Confirmed", "Rejected", "Reverted"):
                break
            time.sleep(poll_interval)
        return status


class MandateRelayer:
    """Adapter exposing the agent's ``relay_redemption(proposal, signed)`` interface.

    Wraps a OneShotRelayer with the frontend-provided signed delegation context so a
    verified payment is redeemed gaslessly on-chain via 1Shot. Used only in the live
    flow (a real signed delegation must be present).
    """

    def __init__(self, oneshot: OneShotRelayer, delegation_context: str, token: str):
        self.oneshot = oneshot
        self.delegation_context = delegation_context
        self.token = token

    def relay_redemption(self, proposal, signed) -> str:
        status = self.oneshot.relay_usdc_payment(
            delegation_context=self.delegation_context,
            token=self.token,
            to=proposal.target,
            amount=proposal.value,
        )
        return status.get("transactionHash") or status.get("task_id") or "0xpending"
