# IntentGuard

**Stop a prompt-injected sentence from draining your AI agent's wallet.**

IntentGuard freezes a user's payment intent into an **EIP-712 mandate** at the approval moment,
delegates a scoped permission to an autonomous agent via **MetaMask Smart Accounts (ERC-7715)**, and
enforces it on-chain with **ERC-7710 caveat enforcers** that a corrupted agent cannot relax. The agent
reasons with **Venice AI**; legitimate payments settle **gaslessly through 1Shot**; everything runs on
**Base Sepolia** over **x402**.

> Built for the MetaMask Smart Accounts Kit × 1Shot API × Venice AI Dev Cook-Off.
> Research backing: [Zenodo DOI 10.5281/zenodo.20575443](https://zenodo.org/record/20575443).

## Why it matters

x402 lets agents pay autonomously — but agents read untrusted data. A prompt injection can **scope-lift**
a payment (redirect recipient / inflate amount). In our study, raw x402 lets **~50%** of these attacks
succeed. IntentGuard drives that to **0%** while keeping **~98%** autonomy (vs. a human-in-the-loop gate
that drops autonomy to 0%).

## Track coverage

| Track | How |
|-------|-----|
| **x402 + ERC-7710** | x402 402-invoice flow + caveat-enforced ERC-7710 redemption |
| **Best Agent** | Autonomous Venice agent spending under delegated authority |
| **Best use of Venice AI** | Venice is the agent's private reasoning brain + MetaMask + x402 |
| **1Shot Relayer** | Gasless ERC-7710 redemption with ERC-7702 account upgrade |

## Architecture

Hybrid: **Next.js + Viem + @metamask/delegation-toolkit** frontend (wallet, ERC-7715 freeze-intent)
and a **Python/FastAPI** backend (`intent_guard` engine, Venice agent, x402 merchant, 1Shot relayer).
See [`docs/design.md`](docs/design.md).

## Repo layout

```
docs/        research paper + technical design
backend/     Python: intent_guard engine, Venice agent, x402, 1Shot relayer
frontend/    Next.js: MetaMask Smart Accounts + ERC-7715 + demo UX
```

## Quickstart

### Backend
```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in Venice / 1Shot keys
uvicorn app:app --reload
```

### Frontend
```bash
cd frontend
npm install
cp .env.local.example .env.local
npm run dev   # http://localhost:3000
```

## Demo flow

1. **Freeze intent** — approve once ("pay up to 5 USDC to Blue Bottle"); MetaMask signs an
   ERC-7710 delegation with `allowedTargets` / `erc20PeriodTransfer` / `timestamp` caveats.
2. **Run the agent** on an invoice — pick an injection (or paste your own), toggle the guard.
   - Guard **off** + poisoned → **wallet drained** to the attacker (baseline x402).
   - Guard **on** + poisoned → **blocked** (`target_not_allowed`, `value_exceeds_cap`).
   - Guard **on** + clean → **paid**, gaslessly via the 1Shot relayer.

## What's built (and verified)

| Layer | Status |
|-------|--------|
| `intent_guard` — EIP-712/secp256k1 freeze→verify→settle | ✅ 13 tests |
| Venice agent — CaMeL planner/quarantined-LLM split | ✅ reproduces 50%→0% |
| x402 merchant + 9 injection families | ✅ |
| FastAPI API (freeze / invoice / run / relayer) | ✅ live-verified |
| Frontend — MetaMask delegation + demo UX | ✅ `next build` passes |
| 1Shot relayer (EIP-7710, keyless) | ✅ live `getCapabilities` reachable |
| **Total** | **23 backend tests passing** |

## Docs

- [`docs/design.md`](docs/design.md) — protocol + threat model
- [`docs/RUNBOOK.md`](docs/RUNBOOK.md) — local run, deploy, on-chain path
- [`docs/demo-script.md`](docs/demo-script.md) — 3-minute video script
- [`docs/deck-outline.md`](docs/deck-outline.md) — pitch deck outline
- [`docs/paper.pdf`](docs/paper.pdf) — research backing

## Submission checklist

- [x] Public repo · [x] Live product (deploy per RUNBOOK) · [ ] 3-min video (script ready)
- [ ] Deck (outline ready) · [x] MetaMask Smart Accounts + ERC-7710 · [x] x402 · [x] Venice · [x] 1Shot
