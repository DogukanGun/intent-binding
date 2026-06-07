"use client";

import { motion } from "framer-motion";
import { useEffect, useState } from "react";
import type { AgentRun } from "@/lib/api";
import { shortAddr, usdc } from "@/lib/format";

/**
 * Animated payment pipeline:
 *   Intent -> Invoice -> Venice Agent -> IntentGuard -> Outcome
 * Nodes activate left-to-right; a colored pulse travels the wires. When the guard
 * blocks, the flow STOPS at the shield (red); otherwise it reaches the outcome
 * (green merchant / red attacker).
 */
const NODES = ["intent", "invoice", "agent", "guard", "outcome"] as const;
const GUARD_IDX = 3;
const OUTCOME_IDX = 4;

type Tone = "idle" | "ok" | "danger" | "warn" | "accent";
const TONE: Record<Tone, { ring: string; text: string; glow: string }> = {
  idle: { ring: "border-gray-800", text: "text-gray-500", glow: "" },
  ok: { ring: "border-ok", text: "text-ok", glow: "shadow-[0_0_24px_-4px] shadow-ok/50" },
  danger: { ring: "border-danger", text: "text-danger", glow: "shadow-[0_0_24px_-4px] shadow-danger/60" },
  warn: { ring: "border-amber-400", text: "text-amber-400", glow: "shadow-[0_0_24px_-4px] shadow-amber-400/50" },
  accent: { ring: "border-accent", text: "text-accent", glow: "shadow-[0_0_24px_-4px] shadow-accent/50" },
};

export function PipelineFlow({
  run,
  capUsdc,
  running,
}: {
  run: AgentRun | null;
  capUsdc: number;
  running: boolean;
}) {
  const [active, setActive] = useState(-1);

  const blocked = !!run && run.guarded && !run.settled;
  const lastStep = blocked ? GUARD_IDX : OUTCOME_IDX;

  // Advance the active node left->right whenever a new run arrives.
  useEffect(() => {
    if (!run) {
      setActive(-1);
      return;
    }
    setActive(0);
    const timers: ReturnType<typeof setTimeout>[] = [];
    for (let i = 1; i <= lastStep; i++) {
      timers.push(setTimeout(() => setActive(i), i * 420));
    }
    return () => timers.forEach(clearTimeout);
  }, [run, lastStep]);

  const flowTone: Tone = !run
    ? "idle"
    : run.attack_succeeded
    ? "danger"
    : blocked
    ? "warn"
    : "ok";

  const nodes = buildNodes(run, capUsdc, blocked);

  return (
    <div className="rounded-xl border border-gray-800 bg-panel p-5">
      <div className="mb-4 flex items-center justify-between">
        <h2 className="text-lg font-semibold text-white">Payment pipeline</h2>
        {running && <span className="text-xs text-accent">running…</span>}
      </div>

      <div className="flex items-stretch gap-1 overflow-x-auto pb-2">
        {nodes.map((n, i) => (
          <div key={NODES[i]} className="flex min-w-[150px] flex-1 items-center">
            <Node node={n} activated={active >= i} index={i} />
            {i < nodes.length - 1 && (
              <Wire
                filled={active > i}
                stopped={i === GUARD_IDX - 1 && blocked ? false : undefined}
                tone={i >= GUARD_IDX ? flowTone : run?.invoice.poisoned ? "danger" : "accent"}
              />
            )}
          </div>
        ))}
      </div>

      {!run && (
        <p className="mt-2 text-center text-xs text-gray-600">
          Freeze intent, then run the agent — the flow animates here.
        </p>
      )}
    </div>
  );
}

type NodeModel = { icon: string; title: string; sub: string; tone: Tone };

function buildNodes(run: AgentRun | null, capUsdc: number, blocked: boolean): NodeModel[] {
  if (!run) {
    return [
      { icon: "🔒", title: "Intent", sub: `cap ${capUsdc} USDC`, tone: "idle" },
      { icon: "📄", title: "Invoice", sub: "—", tone: "idle" },
      { icon: "🧠", title: "Venice agent", sub: "—", tone: "idle" },
      { icon: "🛡️", title: "IntentGuard", sub: "—", tone: "idle" },
      { icon: "🎯", title: "Outcome", sub: "—", tone: "idle" },
    ];
  }

  const poisoned = run.invoice.poisoned;
  const ext = run.extracted;
  const outcomeTone: Tone = run.attack_succeeded ? "danger" : blocked ? "warn" : "ok";

  return [
    { icon: "🔒", title: "Intent", sub: `frozen · cap ${capUsdc} USDC`, tone: "accent" },
    {
      icon: "📄",
      title: "Invoice",
      sub: poisoned ? `poisoned · ${run.invoice.attack}` : "clean",
      tone: poisoned ? "danger" : "ok",
    },
    {
      icon: "🧠",
      title: "Venice agent",
      sub: `${shortAddr(ext.to)} · ${ext.amount_usdc} USDC (TOOL)`,
      tone: poisoned ? "danger" : "accent",
    },
    {
      icon: blocked ? "🛡️" : run.guarded ? "🛡️" : "🚫",
      title: "IntentGuard",
      sub: !run.guarded
        ? "DISABLED (baseline)"
        : blocked
        ? run.reasons.join(", ")
        : "within mandate ✓",
      tone: !run.guarded ? "danger" : blocked ? "warn" : "ok",
    },
    {
      icon: run.attack_succeeded ? "❌" : blocked ? "⛔" : "✅",
      title: run.attack_succeeded ? "Attacker" : blocked ? "Blocked" : "Merchant",
      sub: run.receipt
        ? `${usdc(run.receipt.amount_usdc)} → ${shortAddr(run.receipt.target)}`
        : "no transfer",
      tone: outcomeTone,
    },
  ];
}

function Node({ node, activated, index }: { node: NodeModel; activated: boolean; index: number }) {
  const tone = activated ? node.tone : "idle";
  const t = TONE[tone];
  return (
    <motion.div
      initial={{ opacity: 0.4, scale: 0.96 }}
      animate={activated ? { opacity: 1, scale: 1 } : { opacity: 0.45, scale: 0.97 }}
      transition={{ duration: 0.25, delay: index * 0.02 }}
      className={`flex-1 rounded-lg border ${t.ring} ${activated ? t.glow : ""} bg-bg p-3 text-center transition-colors`}
    >
      <div className="text-2xl">{node.icon}</div>
      <div className={`mt-1 text-xs font-semibold ${t.text}`}>{node.title}</div>
      <div className="mt-0.5 truncate text-[10px] text-gray-500" title={node.sub}>
        {node.sub}
      </div>
    </motion.div>
  );
}

function Wire({ filled, tone }: { filled: boolean; stopped?: boolean; tone: Tone }) {
  const color =
    tone === "danger" ? "#ef4444" : tone === "ok" ? "#22c55e" : tone === "warn" ? "#f59e0b" : "#f6851b";
  return (
    <div className="relative h-0.5 w-6 shrink-0 bg-gray-800">
      <motion.div
        className="absolute inset-y-0 left-0"
        style={{ background: color }}
        initial={{ width: "0%" }}
        animate={{ width: filled ? "100%" : "0%" }}
        transition={{ duration: 0.35 }}
      />
      {filled && (
        <motion.div
          className="absolute top-1/2 h-2 w-2 -translate-y-1/2 rounded-full"
          style={{ background: color, boxShadow: `0 0 8px ${color}` }}
          initial={{ left: "0%" }}
          animate={{ left: "100%" }}
          transition={{ duration: 0.35 }}
        />
      )}
    </div>
  );
}
