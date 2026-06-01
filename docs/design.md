# IntentGuard — Technical Design

> Binding agent payments to human intent so a prompt-injected sentence can't drain a wallet.
> Research backing: Zenodo DOI [10.5281/zenodo.20575443](https://zenodo.org/record/20575443) (`docs/paper.pdf`).

## Problem

x402 lets AI agents pay autonomously over HTTP 402. But the agent reads untrusted data
(invoices, web pages, tool output). A **prompt injection** hidden in that data can perform a
**scope-lift**: redirect the recipient or inflate the amount while staying "within budget."
In the paper's simulation, raw x402 lets **~50%** of scope-lift attacks succeed. A human-in-the-loop
gate stops them but destroys autonomy (task completion → 0%).

## Solution: freeze intent early, enforce it on-chain

Move the human decision **earlier** (once, at approval) instead of **more often** (per payment):

1. **Freeze** — at the human-approval moment, the user's natural-language intent is anchored into a
   typed **EIP-712 mandate** `m` and signed (`σ = Sign_skU(H712(m))`). The hash is committed via an
   **ERC-7715 `wallet_grantPermissions`** request, producing a scoped delegation to the agent.
2. **Verify** — the agent's proposed payment is checked against the frozen mandate (off-chain pre-flight).
3. **Enforce** — redemption goes through **ERC-7710 caveat enforcers** in the EVM. Because enforcement
   runs on-chain (not in the agent's prompt), a corrupted agent **cannot relax** the scope; it can only
   fail to submit a valid redemption.

Result in simulation: scope-lift ASR **0.0%** (vs 49.7% unbounded), autonomy **97.9%**, replay blocked 99.995%.

## Mandate structure (`backend/intent_guard/types.py`)

| Field | Maps to on-chain enforcer |
|-------|---------------------------|
| `allowed_targets` | `AllowedTargets` |
| `max_value` + `token` | `ValueLte` + `ERC20PeriodTransfer` |
| `not_before` / `not_after` | `Timestamp` |
| `nonce` | `Nonce` (replay guard) |
| `exact_calldata_hash` (optional) | `ExactCalldata` |
| `cnf_jwk` | same-agent key confirmation |

## The 9-check verify chain (`backend/intent_guard/core.py:verify_payment`)

1. **alg pinning** (ES256 only — blocks algorithm confusion)
2. **signature coverage** (recompute struct hash over ALL fields — blocks constraint stripping)
3. **provenance** (CaMeL: `TOOL`-tainted data can't originate a payment)
4. **cnf binding** (same-agent proof — blocks split-agent)
5. **nonce** binding + replay guard
6. **AllowedTargets**
7. **token** match + **ValueLte**
8. **Timestamp** window
9. **ExactCalldata** (optional)

A proposal is allowed **only if every check passes**.

## Threat model & attack taxonomy (`backend/x402/injections.py`)

Adversary controls untrusted observations and can inject arbitrary instructions; the planner LLM is
fully corruptible but cannot forge `σ` or break `H712`. Nine scope-lifting families:
recipient redirection, amount inflation, repeat-spend, replay, scope extension, priority-hijack,
obfuscated (homoglyph), encoded (base64), adaptive (picks the weakest enforced dimension).

## Architecture (hybrid)

```
┌─────────────── Frontend (Next.js + Viem + @metamask/delegation-toolkit) ───────────────┐
│  Connect MetaMask → create Smart Account (7702/4337)                                    │
│  Freeze intent  → wallet_grantPermissions (ERC-7715) with caveats → delegation context  │
└───────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ delegation context
┌───────────────────────────────────▼─────────────── Backend (Python / FastAPI) ──────────┐
│  intent_guard   freeze/verify/settle (EIP-712 + secp256k1)                                │
│  agent          Venice planner  +  quarantined-LLM (CaMeL provenance)                     │
│  x402           mock merchant (HTTP 402) + injection harness                              │
│  relayer        1Shot → ERC-7710 redeemDelegation (gas-abstracted, 7702 upgrade)          │
└───────────────────────────────────┬─────────────────────────────────────────────────────┘
                                     │ relays redemption
                          Base Sepolia: caveat enforcers + EIP-3009 USDC
```

## Track mapping

- **x402 + ERC-7710** — 402 invoice flow + caveat-enforced redemption
- **Best Agent** — autonomous Venice agent spending under delegated authority
- **Best use of Venice AI** — Venice is the agent's reasoning brain (privacy-first) + MetaMask + x402
- **1Shot Relayer** — gasless ERC-7710 redemption with ERC-7702 upgrade

## What is real vs. what the paper simulated

The paper's metrics come from a numpy Monte-Carlo simulation. This dApp converts that design into a
**live on-chain demonstration**: real MetaMask Smart Accounts, real ERC-7715/7710 caveats, real Venice
reasoning, real 1Shot-relayed redemption on Base Sepolia, with a judge-editable injection demo.
