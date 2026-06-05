"""1Shot relayer client tests (JSON-RPC mocked, no network)."""

import json

import httpx

from relayer.oneshot import OneShotRelayer, encode_usdc_transfer

USDC = "0x036CbD53842c5426634e7929541eC2318f3dCF7e"
MERCHANT = "0x1111111111111111111111111111111111111111"


def test_encode_usdc_transfer():
    data = encode_usdc_transfer(MERCHANT, 4_000_000)
    assert data.startswith("0xa9059cbb")  # transfer(address,uint256) selector
    assert len(data) == 2 + 8 + 64 + 64  # 0x + selector + 2 words


def test_relay_flow_mocked():
    seen_methods = []

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        seen_methods.append(body["method"])
        method = body["method"]
        if method == "relayer_getFeeData":
            result = {"minFee": "1000", "context": "ctx-fee", "expiry": 9999999999}
        elif method == "relayer_estimate7710Transaction":
            result = {"success": True, "requiredPaymentAmount": "1200", "context": "ctx-locked"}
        elif method == "relayer_send7710Transaction":
            result = {"TaskId": "task-abc"}
        elif method == "relayer_getStatus":
            result = {"task_id": "task-abc", "status": "Confirmed", "transactionHash": "0xdead"}
        else:
            result = {}
        return httpx.Response(200, json={"jsonrpc": "2.0", "id": body["id"], "result": result})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    relayer = OneShotRelayer(chain_id=84532, client=client)

    status = relayer.relay_usdc_payment(
        delegation_context="0xsigneddelegation", token=USDC, to=MERCHANT,
        amount=4_000_000, poll_interval=0, poll_timeout=5,
    )
    assert status["status"] == "Confirmed"
    assert "relayer_getFeeData" in seen_methods
    assert "relayer_estimate7710Transaction" in seen_methods
    assert "relayer_send7710Transaction" in seen_methods
    assert "relayer_getStatus" in seen_methods
