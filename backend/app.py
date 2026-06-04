"""IntentGuard backend API.

Wires the demo: freeze a mandate (ERC-7715 intent), fetch an x402 invoice (clean
or poisoned), and run the Venice agent through the guard. Designed for the Next.js
frontend; CORS-enabled.
"""

from __future__ import annotations

import os
import time
from typing import Optional

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from intent_guard import Guard, ScopeCaveat
from intent_guard import eip712
from agent.agent import PaymentAgent, usdc, from_usdc
from agent.venice import VeniceClient
from x402.merchant import make_invoice_402
from x402.injections import FAMILIES

load_dotenv()

CHAIN_ID = int(os.environ.get("CHAIN_ID", "84532"))
USDC_ADDRESS = os.environ.get("USDC_ADDRESS", "0x036CbD53842c5426634e7929541eC2318f3dCF7e")
# Demo counterparties (override via env for the live on-chain path).
MERCHANT = os.environ.get("DEMO_MERCHANT", "0x1111111111111111111111111111111111111111")
ATTACKER = os.environ.get("DEMO_ATTACKER", "0x2222222222222222222222222222222222222222")
CORS_ORIGINS = os.environ.get("CORS_ORIGINS", "http://localhost:3000").split(",")

app = FastAPI(title="IntentGuard", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

venice = VeniceClient()


class Session:
    """Single in-memory demo session: the frozen mandate + its guard."""

    def __init__(self) -> None:
        self.guard: Optional[Guard] = None
        self.signed = None
        self.cap_usdc: float = 5.0
        self.amount_usdc: float = 4.0


SESSION = Session()


# --------------------------------------------------------------------- models
class FreezeRequest(BaseModel):
    instruction: str = "Pay up to 5 USDC to Blue Bottle Coffee"
    cap_usdc: float = 5.0
    amount_usdc: float = 4.0
    ttl_seconds: int = 3600
    # Wallet-signed flow (Phase 4): if provided, attach instead of backend-signing.
    signer_address: Optional[str] = None
    signature: Optional[str] = None
    nonce: Optional[str] = None


class RunRequest(BaseModel):
    attack: Optional[str] = "clean"
    guarded: bool = True
    planner: str = "naive"
    # Optional raw invoice override so a judge can paste/edit their own injection.
    invoice_text: Optional[str] = None


# -------------------------------------------------------------------- routes
@app.get("/health")
def health():
    return {"ok": True, "llm_backend": venice.backend, "chain_id": CHAIN_ID}


@app.get("/config")
def config():
    return {
        "chain_id": CHAIN_ID,
        "usdc": USDC_ADDRESS,
        "merchant": MERCHANT,
        "attacker": ATTACKER,
        "llm_backend": venice.backend,
        "attacks": [{"name": f.name, "dimension": f.dimension, "desc": f.desc} for f in FAMILIES],
    }


@app.post("/session/freeze")
def freeze(req: FreezeRequest):
    now = int(time.time())
    caveat = ScopeCaveat(
        allowed_targets=(MERCHANT,),
        max_value=usdc(req.cap_usdc),
        token=USDC_ADDRESS,
        not_before=now - 60,
        not_after=now + req.ttl_seconds,
    )
    if req.signer_address and req.signature:
        # Wallet-signed: build mandate, attach the wallet signature.
        guard = Guard(expected_signer=req.signer_address)
        mandate = guard.build_mandate(
            req.instruction, caveat, f"cnf:{req.signer_address}", nonce=req.nonce, chain_id=CHAIN_ID
        )
        signed = guard.attach_signature(mandate, req.signature)
    else:
        # Backend-signed demo mandate (ephemeral planner key).
        guard = Guard()
        signed = guard.freeze_intent(
            req.instruction, caveat, f"cnf:{guard.signer_address}", chain_id=CHAIN_ID
        )

    SESSION.guard = guard
    SESSION.signed = signed
    SESSION.cap_usdc = req.cap_usdc
    SESSION.amount_usdc = req.amount_usdc

    return {
        "mandate_hash": signed.struct_hash,
        "signer": guard.signer_address,
        "nonce": signed.mandate.nonce,
        "caveat": {
            "allowed_targets": list(caveat.allowed_targets),
            "max_value": caveat.max_value,
            "cap_usdc": req.cap_usdc,
            "token": caveat.token,
            "not_before": caveat.not_before,
            "not_after": caveat.not_after,
        },
        "typed_data": eip712.build_typed_data(signed.mandate),
    }


@app.get("/invoice")
def invoice(attack: str = "clean"):
    return make_invoice_402(
        attack=attack, merchant=MERCHANT, attacker=ATTACKER, token=USDC_ADDRESS,
        amount_usdc=SESSION.amount_usdc, cap_usdc=SESSION.cap_usdc,
    )


@app.post("/agent/run")
def agent_run(req: RunRequest):
    if SESSION.guard is None or SESSION.signed is None:
        raise HTTPException(status_code=400, detail="No mandate frozen. POST /session/freeze first.")
    inv = make_invoice_402(
        attack=req.attack, merchant=MERCHANT, attacker=ATTACKER, token=USDC_ADDRESS,
        amount_usdc=SESSION.amount_usdc, cap_usdc=SESSION.cap_usdc,
    )
    # A judge may override the invoice text with their own (edited) injection.
    if req.invoice_text is not None:
        inv["invoice"] = {**inv["invoice"], "text": req.invoice_text, "edited": True}
    agent = PaymentAgent(SESSION.guard, SESSION.signed, venice)
    run = agent.run(inv["invoice"]["text"], guarded=req.guarded, planner=req.planner)
    return {
        "invoice": inv["invoice"],
        "guarded": run.guarded,
        "planner": run.planner,
        "llm_backend": run.llm_backend,
        "extracted": run.extracted,
        "proposal": run.proposal,
        "decision": run.decision,
        "settled": run.settled,
        "receipt": run.receipt,
        "attack_succeeded": run.attack_succeeded,
        "reasons": run.reasons,
        "narrative": run.narrative,
    }


@app.get("/metrics", response_class=PlainTextResponse)
def metrics():
    if SESSION.guard is None:
        return "# no session\n"
    return SESSION.guard.metrics_text()
