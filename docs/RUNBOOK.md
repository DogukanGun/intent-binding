# Runbook

## 1. Local — backend

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env        # add VENICE_API_KEY (1Shot relayer is keyless)
uvicorn app:app --reload    # http://localhost:8000
pytest -q                   # 23 tests
```

Without `VENICE_API_KEY` the agent uses a deterministic heuristic reader (still shows
the injection being blocked); with it, the quarantined reader is real Venice AI.

Verify:
```bash
curl localhost:8000/health
curl localhost:8000/relayer/capabilities    # live 1Shot relayer check
curl -X POST localhost:8000/session/freeze -H 'content-type: application/json' -d '{"cap_usdc":5}'
curl -X POST localhost:8000/agent/run -H 'content-type: application/json' \
  -d '{"attack":"priority_hijack","guarded":true,"planner":"naive"}'   # -> blocked
curl -X POST localhost:8000/agent/run -H 'content-type: application/json' \
  -d '{"attack":"priority_hijack","guarded":false,"planner":"naive"}'  # -> drained (baseline)
```

## 2. Local — frontend

```bash
cd frontend
npm install
cp .env.local.example .env.local   # NEXT_PUBLIC_BACKEND_URL=http://localhost:8000
npm run dev                        # http://localhost:3000
```

Connect MetaMask (Base Sepolia), freeze intent, run the injection demo.

## 3. Deploy

**Backend → Render** (or Railway/Fly via `backend/Dockerfile`):
- New Web Service from this repo, root `backend/`, or use `render.yaml`.
- Set `VENICE_API_KEY` and `CORS_ORIGINS` (your Vercel URL).

**Frontend → Vercel:**
- Import the repo, root directory `frontend/`.
- Env: `NEXT_PUBLIC_BACKEND_URL` = the Render backend URL,
  `NEXT_PUBLIC_RPC_URL` = a Base Sepolia RPC.

## 4. On-chain live path (Base Sepolia)

1. Fund the connected EOA with Base Sepolia ETH + test USDC
   (`0x036CbD53842c5426634e7929541eC2318f3dCF7e`).
2. Freeze intent → MetaMask creates the Smart Account + signs the ERC-7710 delegation
   (caveats: allowedTargets=USDC, erc20PeriodTransfer cap, timestamp).
3. Legit payment → backend builds the USDC transfer, 1Shot relays the redemption
   gaslessly (gas paid in stablecoin), tx appears on the Base Sepolia explorer.
4. Injected payment → the redemption violates the caveats → reverts on-chain.

## Troubleshooting

- `relayer/capabilities` returns `available:false` → relayer host blocked by your
  network; the demo's guard/agent flow still works (settlement simulated).
- Toolkit type errors after a version bump → re-check `addCaveat()` config shapes
  in `frontend/lib/delegation.ts` against the new `@metamask/delegation-toolkit`.
