"use client";

export default function Home() {
  return (
    <main className="mx-auto max-w-5xl px-6 py-16">
      <h1 className="text-3xl font-bold text-white">
        IntentGuard <span className="text-accent">·</span> intent-bound agent payments
      </h1>
      <p className="mt-4 max-w-2xl text-gray-400">
        Freeze your intent into an EIP-712 mandate, delegate a scoped payment
        permission to an AI agent via ERC-7715, and watch on-chain ERC-7710
        caveats block any prompt-injection scope-lift — while legitimate payments
        settle gaslessly through 1Shot.
      </p>
      <p className="mt-8 text-sm text-gray-600">
        Scaffold ready. UI wired in Phase 4 &amp; 6.
      </p>
    </main>
  );
}
