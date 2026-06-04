"use client";

import { useEffect, useState } from "react";
import { ConnectButton } from "@/components/ConnectButton";
import { FreezePanel } from "@/components/FreezePanel";
import { InjectionDemo } from "@/components/InjectionDemo";
import { api, type Config, type FreezeResult } from "@/lib/api";

export default function Home() {
  const [config, setConfig] = useState<Config | null>(null);
  const [frozen, setFrozen] = useState<FreezeResult | null>(null);
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    api.config().then((c) => { setConfig(c); setOnline(true); }).catch(() => setOnline(false));
  }, []);

  return (
    <main className="mx-auto max-w-4xl px-6 py-10">
      <header className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">
            IntentGuard <span className="text-accent">·</span> intent-bound agent payments
          </h1>
          <p className="text-xs text-gray-500">
            backend:{" "}
            {online === null ? "…" : online ? `online · ${config?.llm_backend}` : "offline"}
          </p>
        </div>
        <ConnectButton />
      </header>

      <p className="mt-6 max-w-2xl text-gray-400">
        An AI agent holds a delegated payment permission. A prompt-injection hidden in an invoice
        tries to <span className="text-danger">redirect or inflate</span> the payment. IntentGuard
        freezes your intent into an EIP-712 mandate and enforces it with ERC-7710 caveats — so the
        scope-lift is rejected while the legit payment settles. Toggle the guard off to see the
        baseline get drained.
      </p>

      <div className="mt-8 space-y-6">
        <FreezePanel onFrozen={setFrozen} frozen={frozen} />
        <InjectionDemo config={config} ready={!!frozen} />
      </div>

      <footer className="mt-12 border-t border-gray-900 pt-6 text-xs text-gray-600">
        MetaMask Smart Accounts (ERC-7710) · x402 · Venice AI · 1Shot relayer ·{" "}
        <a className="underline" href="https://zenodo.org/record/20575443" target="_blank" rel="noreferrer">
          research (Zenodo)
        </a>
      </footer>
    </main>
  );
}
