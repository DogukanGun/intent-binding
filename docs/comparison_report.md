# Comparison Report: x402-intent-binding-injection

## Our Approach
We built an intent-proof caveat enforcer for x402 micropayments that cryptographically binds each transaction to a prior user instruction and enforces it deterministically on-chain via ERC-7715 caveats. A Monte-Carlo harness pits intent-bound delegations against unbounded, allowance-only, and HITL regimes across 5400 injection cases, measuring scope-lift attack success, false rejections, task completion, and replay resistance.

## Compared Systems
- AP2 Agent Payments Protocol (Intent-Cart-Payment mandate chain, off-chain intent binding)
- ERC-7715 allowance caveats / xpay Smart Proxy / Bedrock AgentCore (magnitude caps, not intent-bound)
- AgentDojo banking suite (prompt-injection ASR benchmark, no payment scope-lift tests)

## Strengths
- Drives scope-lift ASR to 0% vs ~49.7% unbounded baseline
- Preserves autonomy: ~98% task completion vs 0% for HITL gate
- Deterministic on-chain enforcement at low cost (~72k gas, 27ms added latency)
- Blocks replay/temporal attacks at 99.99%

## Weaknesses
- Evaluation is offline Bernoulli simulation, not real LLMs/Anvil/AgentDojo
- Small usability cost: 0.3pp false-rejection increase, ~2.1pp lower task completion
- Relies on accurate NL-to-structured intent anchoring, untested on live benchmarks
- Not yet validated against an end-to-end on-chain x402 deployment
