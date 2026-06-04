"use client";

import { useState } from "react";
import { api, type FreezeResult } from "@/lib/api";

export function FreezePanel({
  onFrozen,
  frozen,
}: {
  onFrozen: (f: FreezeResult) => void;
  frozen: FreezeResult | null;
}) {
  const [cap, setCap] = useState(5);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function freeze() {
    setBusy(true);
    setErr(null);
    try {
      const f = await api.freeze({
        instruction: `Pay up to ${cap} USDC to Blue Bottle Coffee`,
        cap_usdc: cap,
        amount_usdc: 4,
      });
      onFrozen(f);
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="rounded-xl border border-gray-800 bg-panel p-5">
      <h2 className="text-lg font-semibold text-white">1 · Freeze intent</h2>
      <p className="mt-1 text-sm text-gray-400">
        Approve once: the agent may pay <span className="text-accent">up to {cap} USDC</span> to
        Blue Bottle — and nothing else. This becomes an EIP-712 mandate enforced by ERC-7710 caveats.
      </p>

      <div className="mt-4 flex items-center gap-4">
        <input
          type="range"
          min={1}
          max={20}
          value={cap}
          onChange={(e) => setCap(Number(e.target.value))}
          className="w-48 accent-accent"
        />
        <span className="font-mono text-white">{cap} USDC cap</span>
        <button
          onClick={freeze}
          disabled={busy}
          className="ml-auto rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-black hover:opacity-90 disabled:opacity-50"
        >
          {busy ? "Freezing…" : frozen ? "Re-freeze" : "Freeze intent"}
        </button>
      </div>

      {err && <p className="mt-3 text-sm text-danger">{err}</p>}

      {frozen && (
        <div className="mt-4 space-y-1 rounded-lg border border-gray-800 bg-bg p-3 text-xs">
          <Row k="mandate hash" v={frozen.mandate_hash} mono />
          <Row k="signer" v={frozen.signer} mono />
          <Row k="allowed target" v={frozen.caveat.allowed_targets[0]} mono />
          <Row k="cap" v={`${frozen.caveat.cap_usdc} USDC`} />
          <Row k="valid until" v={new Date(frozen.caveat.not_after * 1000).toLocaleTimeString()} />
        </div>
      )}
    </section>
  );
}

function Row({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3">
      <span className="text-gray-500">{k}</span>
      <span className={`truncate text-gray-300 ${mono ? "font-mono" : ""}`} title={v}>
        {v}
      </span>
    </div>
  );
}
