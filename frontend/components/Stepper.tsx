"use client";

import { motion } from "framer-motion";

const EXPLAINER = [
  { icon: "🔒", title: "Freeze intent", body: "Approve once: pay up to N USDC to one merchant." },
  { icon: "🤝", title: "Delegate to agent", body: "An ERC-7710 delegation scopes the agent's power." },
  { icon: "🛡️", title: "Enforce on-chain", body: "Caveats reject any payment outside your intent." },
];

export function Explainer() {
  return (
    <div className="grid gap-3 sm:grid-cols-3">
      {EXPLAINER.map((e, i) => (
        <motion.div
          key={e.title}
          initial={{ opacity: 0, y: 8 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.05 * i, duration: 0.3 }}
          className="rounded-lg border border-gray-800 bg-panel p-4"
        >
          <div className="text-xl">{e.icon}</div>
          <div className="mt-1 text-sm font-semibold text-white">
            {i + 1}. {e.title}
          </div>
          <div className="mt-1 text-xs text-gray-500">{e.body}</div>
        </motion.div>
      ))}
    </div>
  );
}

export function Stepper({ step }: { step: 1 | 2 }) {
  const steps = [
    { n: 1, label: "Freeze intent" },
    { n: 2, label: "Run the agent" },
  ];
  return (
    <div className="flex items-center gap-3">
      {steps.map((s, i) => {
        const done = step > s.n;
        const current = step === s.n;
        return (
          <div key={s.n} className="flex items-center gap-3">
            <div
              className={`flex h-7 w-7 items-center justify-center rounded-full border text-xs font-bold ${
                done
                  ? "border-ok bg-ok text-black"
                  : current
                  ? "border-accent text-accent"
                  : "border-gray-700 text-gray-600"
              }`}
            >
              {done ? "✓" : s.n}
            </div>
            <span className={`text-sm ${current ? "text-white" : "text-gray-500"}`}>{s.label}</span>
            {i < steps.length - 1 && <div className="h-px w-8 bg-gray-700" />}
          </div>
        );
      })}
    </div>
  );
}
