/** Typed client for the IntentGuard backend. */

import { BACKEND_URL } from "./wagmi";

export type AttackFamily = { name: string; dimension: string; desc: string };

export type Config = {
  chain_id: number;
  usdc: string;
  merchant: string;
  attacker: string;
  llm_backend: string;
  attacks: AttackFamily[];
};

export type FreezeResult = {
  mandate_hash: string;
  signer: string;
  nonce: string;
  caveat: {
    allowed_targets: string[];
    max_value: number;
    cap_usdc: number;
    token: string;
    not_before: number;
    not_after: number;
  };
  typed_data: unknown;
};

export type AgentRun = {
  invoice: { attack: string; dimension: string; poisoned: boolean; text: string; desc?: string };
  guarded: boolean;
  planner: string;
  llm_backend: string;
  extracted: { to: string; amount_usdc: number; backend: string };
  proposal: {
    target: string;
    value: number;
    amount_usdc: number;
    token: string;
    provenance: string;
  } | null;
  decision: { allowed: boolean; reasons: string[] } | null;
  settled: boolean;
  receipt: {
    tx_hash: string;
    amount_usdc: number;
    target: string;
    mandate_hash: string;
  } | null;
  attack_succeeded: boolean;
  reasons: string[];
  narrative: string[];
};

async function jpost<T>(path: string, body: unknown): Promise<T> {
  const r = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!r.ok) throw new Error(`${path} → ${r.status} ${await r.text()}`);
  return r.json();
}

async function jget<T>(path: string): Promise<T> {
  const r = await fetch(`${BACKEND_URL}${path}`);
  if (!r.ok) throw new Error(`${path} → ${r.status}`);
  return r.json();
}

export type Invoice402 = {
  status: number;
  payment: { accepts: { payTo: string; maxAmountRequired: string; asset: string }[] };
  invoice: { attack: string; dimension: string; poisoned: boolean; text: string; desc?: string };
};

export const api = {
  config: () => jget<Config>("/config"),
  health: () => jget<{ ok: boolean; llm_backend: string; chain_id: number }>("/health"),
  freeze: (body: {
    instruction?: string;
    cap_usdc?: number;
    amount_usdc?: number;
    ttl_seconds?: number;
    signer_address?: string;
    signature?: string;
    nonce?: string;
  }) => jpost<FreezeResult>("/session/freeze", body),
  invoice: (attack: string) => jget<Invoice402>(`/invoice?attack=${encodeURIComponent(attack)}`),
  run: (body: { attack: string; guarded: boolean; planner: string; invoice_text?: string }) =>
    jpost<AgentRun>("/agent/run", body),
};
