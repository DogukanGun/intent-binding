# intent_guard

A minimal prototype of the **intent-binding** defense against prompt-injection
*scope-lifting* on x402 micropayments.

The experiment showed that freezing user intent into a typed, signed mandate at
the human-approval moment — then enforcing that mandate's hash as a deterministic
commitment — drives injection **Attack Success Rate from ~50% to 0%** while
keeping False Rejection Rate at 0.3% and adding ~27 ms / 72k gas per redemption.
This library distills that winning regime into a clean, reusable API.

## What it does

`intent_guard` implements the freeze → verify → settle flow with the full
caveat-enforcer chain proven necessary by the experiment:

| Guard | Defeats |
|-------|---------|
| Signature over **all** mandate fields | constraint stripping / scope-lift |
| `ES256`-only algorithm pinning | algorithm confusion |
| `AllowedTargets` / `ValueLte` / token caveats | redirecting funds, over-spending |
| Timestamp window + nonce uniqueness | temporal & nonce replay |
| Provenance separation (CaMeL) | quarantined-LLM data originating a payment |
| `cnf.jwk` equality | split-agent substitution |

These mirror the production ERC-7710 enforcers (Exact-calldata, AllowedTargets,
ValueLte, Timestamp, Nonce, ERC20 amount) that the agent **cannot relax**.

## Install

Core runs on the **Python 3.11 standard library** — no install needed.
See `requirements.txt` for the optional production crypto/chain stack.

## Run the demo

```bash
cd outputs/x402-intent-binding-injection/prototype
python -m intent_guard.cli
```

You will see a legitimate 4-USDC payment settle, then four injection vectors
(scope-lift, tainted provenance, constraint stripping, replay) get rejected.

## API example

```python
from intent_guard import Guard, PaymentProposal, Provenance, ScopeCaveat

guard = Guard()                                   # the privileged planner
caveat = ScopeCaveat(allowed_targets=("0xMerchant",), max_value=5_000_000,
                     token="0xUSDC", not_before=0, not_after=2_000)

mandate = guard.freeze_intent("Pay <=5 USDC to the coffee shop",
                              caveat, cnf_jwk="planner-key")

proposal = PaymentProposal(target="0xMerchant", value=4_000_000, token="0xUSDC",
                           nonce=mandate.mandate.nonce, cnf_jwk="planner-key",
                           provenance=Provenance.USER, timestamp=100)

if guard.verify_payment(proposal, mandate).allowed:
    receipt = guard.settle(mandate, proposal)     # nonce consumed; no replay
```

## Smoke test

```bash
python tests/test_smoke.py        # or: python -m pytest tests/test_smoke.py
```

## Scope & limitations (research prototype)

- Signing uses **HMAC-SHA256 as a stand-in** for ES256/EIP-712 so the prototype
  runs with zero dependencies. The security *properties* (full-field coverage,
  tamper detection) are faithful; production swaps in `eth-account` (EIP-712) and
  `PyJWT`-ES256 — the verify chain is unchanged.
- `settle()` returns a simulated tx hash; wire `Guard` to the x402 facilitator
  and an ERC-4337 smart account + session keys for live redemption.
- Nonce replay state is in-memory; back it with the on-chain Nonce enforcer in
  production.
