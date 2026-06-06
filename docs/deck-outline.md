# Pitch Deck Outline (8 slides)

1. **Title** — IntentGuard: intent-bound payments for AI agents.
   MetaMask Smart Accounts × x402 × Venice AI × 1Shot. Author: Dogukan Ali Gundogan.

2. **The problem** — Agents hold wallets and pay over x402, but read untrusted data.
   A prompt injection scope-lifts the payment (redirect / inflate). Measured: **~50%**
   of scope-lift attacks succeed on raw x402.

3. **Why existing answers fail** — Allowance-only caveats stop inflation but not
   redirection (~21% still succeed). Human-in-the-loop stops attacks but kills autonomy
   (task completion → 0%). We need secure *and* autonomous.

4. **Insight** — Move the human decision **earlier** (once, at approval), not **more
   often** (per payment). Freeze intent into an EIP-712 mandate; enforce it on-chain.

5. **How it works** — Diagram: Freeze (ERC-7715/7710 delegation w/ caveats) →
   Agent (Venice, CaMeL split) reads invoice → Guard verifies → 1Shot relays redemption.
   The corrupted agent can't relax on-chain caveats.

6. **Results** — Scope-lift ASR **50% → 0%**, autonomy **98%**, replay blocked 99.995%.
   Live demo: judge edits the injection, watches it get blocked; legit pays gaslessly.

7. **Tracks & stack** — x402+ERC-7710 · Best Agent · Venice AI · 1Shot Relayer.
   MetaMask delegation-toolkit, Base Sepolia, EIP-3009 USDC, FastAPI + Next.js.

8. **Ask / links** — Live URL · public repo · 3-min demo · research paper
   (Zenodo DOI 10.5281/zenodo.20575443).
