"use client";

import { useEffect, useState } from "react";
import { api, type AgentRun, type AttackFamily, type Config } from "@/lib/api";

export function InjectionDemo({ config, ready }: { config: Config | null; ready: boolean }) {
  const [attack, setAttack] = useState("priority_hijack");
  const [guarded, setGuarded] = useState(true);
  const [planner, setPlanner] = useState<"naive" | "camel">("naive");
  const [invoiceText, setInvoiceText] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  // Load the invoice text whenever the attack changes (judge can then edit it).
  useEffect(() => {
    api.invoice(attack).then((r) => setInvoiceText(r.invoice.text)).catch(() => {});
  }, [attack]);

  async function execute() {
    setBusy(true);
    setErr(null);
    try {
      setRun(await api.run({ attack, guarded, planner, invoice_text: invoiceText }));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
    }
  }

  const attacks: AttackFamily[] = config?.attacks ?? [];

  return (
    <section className="rounded-xl border border-gray-800 bg-panel p-5">
      <h2 className="text-lg font-semibold text-white">2 · Run the agent on an invoice</h2>
      <p className="mt-1 text-sm text-gray-400">
        The Venice agent reads this (untrusted) invoice and tries to pay. Pick an injection,
        edit the text yourself, toggle the guard — and watch.
      </p>

      {/* controls */}
      <div className="mt-4 flex flex-wrap items-center gap-3 text-sm">
        <select
          value={attack}
          onChange={(e) => setAttack(e.target.value)}
          className="rounded-lg border border-gray-700 bg-bg px-3 py-2"
        >
          <option value="clean">clean invoice</option>
          {attacks.map((a) => (
            <option key={a.name} value={a.name}>
              {a.name} ({a.dimension})
            </option>
          ))}
        </select>

        <Toggle label="IntentGuard" on={guarded} onClick={() => setGuarded((v) => !v)} />

        <select
          value={planner}
          onChange={(e) => setPlanner(e.target.value as "naive" | "camel")}
          className="rounded-lg border border-gray-700 bg-bg px-3 py-2"
        >
          <option value="naive">naive planner</option>
          <option value="camel">CaMeL planner</option>
        </select>

        <button
          onClick={execute}
          disabled={busy || !ready}
          className="ml-auto rounded-lg bg-accent px-4 py-2 font-semibold text-black hover:opacity-90 disabled:opacity-50"
          title={ready ? "" : "Freeze intent first"}
        >
          {busy ? "Running…" : "Run agent"}
        </button>
      </div>

      {/* editable invoice */}
      <textarea
        value={invoiceText}
        onChange={(e) => setInvoiceText(e.target.value)}
        spellCheck={false}
        className="mt-4 h-36 w-full resize-y rounded-lg border border-gray-800 bg-bg p-3 font-mono text-xs text-gray-300"
      />

      {err && <p className="mt-3 text-sm text-danger">{err}</p>}
      {run && <Outcome run={run} />}
    </section>
  );
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border px-3 py-2 ${
        on ? "border-ok text-ok" : "border-gray-700 text-gray-500"
      }`}
    >
      {label}: {on ? "ON" : "OFF"}
    </button>
  );
}

function Outcome({ run }: { run: AgentRun }) {
  const blocked = run.guarded && !run.settled;
  const drained = run.attack_succeeded;
  const verdict = drained
    ? { text: "WALLET DRAINED — funds sent to attacker", cls: "border-danger text-danger" }
    : blocked
    ? { text: "BLOCKED — scope-lift rejected by the mandate", cls: "border-ok text-ok" }
    : { text: "PAID — legitimate payment settled", cls: "border-ok text-ok" };

  return (
    <div className="mt-5 space-y-4">
      <div className={`rounded-lg border p-3 text-center font-semibold ${verdict.cls}`}>
        {verdict.text}
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        <Card title="quarantined-LLM extracted">
          <KV k="recipient" v={run.extracted.to} mono />
          <KV k="amount" v={`${run.extracted.amount_usdc} USDC`} />
          <KV k="reader" v={run.llm_backend} />
        </Card>
        <Card title={run.guarded ? "guard decision" : "no guard (baseline)"}>
          {run.decision ? (
            <>
              <KV k="allowed" v={String(run.decision.allowed)} />
              {run.decision.reasons.length > 0 && (
                <KV k="reasons" v={run.decision.reasons.join(", ")} />
              )}
            </>
          ) : (
            <span className="text-xs text-gray-500">enforcement disabled</span>
          )}
          {run.receipt && (
            <>
              <KV k="paid to" v={run.receipt.target} mono />
              <KV k="amount" v={`${run.receipt.amount_usdc} USDC`} />
              <KV k="tx" v={run.receipt.tx_hash} mono />
            </>
          )}
        </Card>
      </div>

      <Card title="agent trace">
        <ol className="space-y-1 text-xs text-gray-400">
          {run.narrative.map((line, i) => (
            <li key={i} className="font-mono">
              {line}
            </li>
          ))}
        </ol>
      </Card>
    </div>
  );
}

function Card({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-bg p-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">{title}</div>
      {children}
    </div>
  );
}

function KV({ k, v, mono }: { k: string; v: string; mono?: boolean }) {
  return (
    <div className="flex justify-between gap-3 text-xs">
      <span className="text-gray-500">{k}</span>
      <span className={`truncate text-gray-300 ${mono ? "font-mono" : ""}`} title={v}>
        {v}
      </span>
    </div>
  );
}
