"use client";

import { AnimatePresence, motion } from "framer-motion";
import { useEffect, useState } from "react";
import { api, type AgentRun, type AttackFamily, type Config } from "@/lib/api";
import { usdc, shortAddr } from "@/lib/format";

export function InjectionDemo({
  config,
  ready,
  onResult,
  onRunningChange,
}: {
  config: Config | null;
  ready: boolean;
  onResult: (r: AgentRun | null) => void;
  onRunningChange: (b: boolean) => void;
}) {
  const [attack, setAttack] = useState("priority_hijack");
  const [guarded, setGuarded] = useState(true);
  const [planner, setPlanner] = useState<"naive" | "camel">("naive");
  const [invoiceText, setInvoiceText] = useState("");
  const [run, setRun] = useState<AgentRun | null>(null);
  const [compare, setCompare] = useState<{ off: AgentRun; on: AgentRun } | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    api.invoice(attack).then((r) => setInvoiceText(r.invoice.text)).catch(() => {});
  }, [attack]);

  function setResult(r: AgentRun | null) {
    setRun(r);
    onResult(r);
  }

  async function execute() {
    setBusy(true);
    setErr(null);
    setCompare(null);
    onRunningChange(true);
    try {
      setResult(await api.run({ attack, guarded, planner, invoice_text: invoiceText }));
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      onRunningChange(false);
    }
  }

  async function runBoth() {
    setBusy(true);
    setErr(null);
    setResult(null);
    onRunningChange(true);
    try {
      const off = await api.run({ attack, guarded: false, planner, invoice_text: invoiceText });
      const on = await api.run({ attack, guarded: true, planner, invoice_text: invoiceText });
      setCompare({ off, on });
      setResult(on); // pipeline shows the guarded outcome
    } catch (e) {
      setErr(String(e));
    } finally {
      setBusy(false);
      onRunningChange(false);
    }
  }

  const attacks: AttackFamily[] = config?.attacks ?? [];

  return (
    <section className="rounded-xl border border-gray-800 bg-panel p-5">
      <h2 className="text-lg font-semibold text-white">Run the agent on an invoice</h2>
      <p className="mt-1 text-sm text-gray-400">
        The Venice agent reads this (untrusted) invoice and tries to pay. Pick an injection,
        edit the text, toggle the guard — or run both at once.
      </p>

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
        <div className="ml-auto flex gap-2">
          <button
            onClick={runBoth}
            disabled={busy || !ready}
            className="rounded-lg border border-gray-700 px-3 py-2 hover:border-accent disabled:opacity-50"
            title={ready ? "Run guard OFF then ON" : "Freeze intent first"}
          >
            Run both
          </button>
          <button
            onClick={execute}
            disabled={busy || !ready}
            className="rounded-lg bg-accent px-4 py-2 font-semibold text-black hover:opacity-90 disabled:opacity-50"
            title={ready ? "" : "Freeze intent first"}
          >
            {busy ? "Running…" : "Run agent"}
          </button>
        </div>
      </div>

      <textarea
        value={invoiceText}
        onChange={(e) => setInvoiceText(e.target.value)}
        spellCheck={false}
        className="mt-4 h-32 w-full resize-y rounded-lg border border-gray-800 bg-bg p-3 font-mono text-xs text-gray-300"
      />

      {err && <p className="mt-3 text-sm text-danger">{err}</p>}

      <AnimatePresence mode="wait">
        {compare ? (
          <Compare key="cmp" off={compare.off} on={compare.on} />
        ) : run ? (
          <SingleResult key={run.invoice.attack + String(run.guarded) + run.narrative.length} run={run} />
        ) : null}
      </AnimatePresence>
    </section>
  );
}

function Toggle({ label, on, onClick }: { label: string; on: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-lg border px-3 py-2 transition-colors ${
        on ? "border-ok text-ok" : "border-gray-700 text-gray-500"
      }`}
    >
      {label}: {on ? "ON" : "OFF"}
    </button>
  );
}

function verdictOf(run: AgentRun) {
  if (run.attack_succeeded)
    return { text: "WALLET DRAINED", sub: "funds sent to attacker", cls: "border-danger text-danger", glow: "shadow-danger/40" };
  if (run.guarded && !run.settled)
    return { text: "BLOCKED", sub: "scope-lift rejected by the mandate", cls: "border-ok text-ok", glow: "shadow-ok/40" };
  return { text: "PAID", sub: "legitimate payment settled", cls: "border-ok text-ok", glow: "shadow-ok/40" };
}

function SingleResult({ run }: { run: AgentRun }) {
  const v = verdictOf(run);
  const amount = run.receipt?.amount_usdc ?? run.proposal?.amount_usdc ?? 0;
  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0 }}
      className="mt-5 space-y-4"
    >
      <div className={`rounded-lg border bg-bg p-4 text-center shadow-[0_0_30px_-8px] ${v.cls} ${v.glow}`}>
        <CountUp value={amount} className="text-2xl font-bold" />
        <div className={`mt-1 text-lg font-extrabold ${v.cls.split(" ")[1]}`}>{v.text}</div>
        <div className="text-xs text-gray-500">{v.sub}</div>
      </div>
      <Trace narrative={run.narrative} />
    </motion.div>
  );
}

function Compare({ off, on }: { off: AgentRun; on: AgentRun }) {
  return (
    <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} className="mt-5">
      <div className="mb-2 text-center text-xs uppercase tracking-wide text-gray-500">
        same invoice · same attack
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <CompareCard label="IntentGuard OFF" run={off} />
        <CompareCard label="IntentGuard ON" run={on} />
      </div>
      <p className="mt-3 text-center text-xs text-gray-500">
        50% → 0%: the only difference is the guard.
      </p>
    </motion.div>
  );
}

function CompareCard({ label, run }: { label: string; run: AgentRun }) {
  const v = verdictOf(run);
  return (
    <div className={`rounded-lg border bg-bg p-4 ${v.cls}`}>
      <div className="text-xs uppercase tracking-wide text-gray-500">{label}</div>
      <div className={`mt-2 text-xl font-extrabold ${v.cls.split(" ")[1]}`}>{v.text}</div>
      <div className="mt-1 text-xs text-gray-400">
        {run.receipt ? `${usdc(run.receipt.amount_usdc)} → ${shortAddr(run.receipt.target)}` : "no transfer"}
      </div>
      {run.reasons.length > 0 && (
        <div className="mt-1 text-[10px] text-gray-500">{run.reasons.join(", ")}</div>
      )}
    </div>
  );
}

const ACTOR_STYLE: { match: string; cls: string }[] = [
  { match: "quarantined", cls: "text-amber-400" },
  { match: "naive-planner", cls: "text-gray-300" },
  { match: "intent-guard] ✓", cls: "text-ok" },
  { match: "intent-guard] ✗", cls: "text-danger" },
  { match: "intent-guard] DISABLED", cls: "text-danger" },
  { match: "1shot-relayer", cls: "text-accent" },
  { match: "baseline-x402", cls: "text-danger" },
  { match: "settle", cls: "text-ok" },
];

function Trace({ narrative }: { narrative: string[] }) {
  return (
    <div className="rounded-lg border border-gray-800 bg-bg p-3">
      <div className="mb-2 text-xs uppercase tracking-wide text-gray-500">agent trace</div>
      <ol className="space-y-1">
        {narrative.map((line, i) => {
          const style = ACTOR_STYLE.find((s) => line.includes(s.match))?.cls ?? "text-gray-400";
          return (
            <motion.li
              key={i}
              initial={{ opacity: 0, x: -6 }}
              animate={{ opacity: 1, x: 0 }}
              transition={{ delay: i * 0.12, duration: 0.2 }}
              className={`font-mono text-xs ${style}`}
            >
              {line}
            </motion.li>
          );
        })}
      </ol>
    </div>
  );
}

function CountUp({ value, className }: { value: number; className?: string }) {
  const [n, setN] = useState(0);
  useEffect(() => {
    let raf = 0;
    const start = performance.now();
    const dur = 600;
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / dur);
      setN(value * (1 - Math.pow(1 - p, 3)));
      if (p < 1) raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [value]);
  return <div className={className}>{usdc(n)}</div>;
}
