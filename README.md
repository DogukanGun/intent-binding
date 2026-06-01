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

## Status

Scaffold + research import complete. Build phases tracked in the plan; the
`intent_guard` engine (freeze → verify → settle) is ported next with real EIP-712 signing.
