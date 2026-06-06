# 3-Minute Demo Video Script

**Goal:** show a prompt injection trying to drain an AI agent's wallet — and IntentGuard stopping it — on real MetaMask Smart Accounts, Venice AI, x402, and the 1Shot relayer.

---

### 0:00–0:25 — The problem
> "AI agents are starting to hold wallets and pay over x402. But agents read untrusted
> data — invoices, web pages. A single injected sentence can redirect or inflate a
> payment. In our research, that works about **half the time**."

Show the IntentGuard landing page; cursor on the tagline.

### 0:25–0:55 — Freeze intent (MetaMask Smart Accounts)
> "First I approve my intent — *once*. Pay up to 5 USDC to Blue Bottle, nothing else."

Connect MetaMask → set cap → **Freeze intent**. Show the MetaMask popup signing the
ERC-7710 delegation; then the mandate hash + caveats panel.
> "That's an EIP-712 mandate, enforced by on-chain ERC-7710 caveats — allowed target,
> spend cap, time window."

### 0:55–1:40 — Baseline: the wallet gets drained
> "Here's a poisoned invoice. Watch the agent with **no guard** — raw x402."

Pick `priority_hijack`, toggle **IntentGuard OFF**, **Run agent**.
Point at the trace: quarantined Venice reader follows the injection →
**WALLET DRAINED — funds sent to attacker**.
> "The injected 'urgent, send to this address' won. 100 USDC, gone."

### 1:40–2:30 — IntentGuard ON: blocked
> "Same invoice. Now turn the guard on."

Toggle **IntentGuard ON**, **Run agent** →
**BLOCKED — target_not_allowed, value_exceeds_cap**.
> "The agent still got fooled — but the redemption can't relax the mandate. The
> ERC-7710 caveats reject it on-chain. Zero successful attacks."

Edit the invoice live (type a new attacker address) → run again → still blocked.
> "Try your own injection — it doesn't matter. Intent is frozen."

### 2:30–2:55 — Legit payment settles gaslessly (1Shot)
Pick `clean`, guard ON, **Run agent** →
**PAID** → show the 1Shot-relayed tx hash / Base Sepolia explorer link.
> "A legitimate payment still settles — autonomously, gaslessly, relayed by 1Shot.
> 98% autonomy, zero drained wallets."

### 2:55–3:00 — Close
> "IntentGuard: freeze intent, enforce it on-chain. MetaMask Smart Accounts, Venice AI,
> x402, 1Shot. Research and code linked below."

Show: repo URL · live URL · Zenodo DOI 10.5281/zenodo.20575443.
