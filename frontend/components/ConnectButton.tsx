"use client";

import { useAccount, useConnect, useDisconnect } from "wagmi";

export function ConnectButton() {
  const { address, isConnected } = useAccount();
  const { connect, connectors, isPending } = useConnect();
  const { disconnect } = useDisconnect();

  if (isConnected && address) {
    return (
      <button
        onClick={() => disconnect()}
        className="rounded-lg border border-gray-700 bg-panel px-4 py-2 text-sm hover:border-accent"
      >
        {address.slice(0, 6)}…{address.slice(-4)} · disconnect
      </button>
    );
  }

  const mm = connectors.find((c) => c.name.toLowerCase().includes("meta")) ?? connectors[0];
  return (
    <button
      onClick={() => mm && connect({ connector: mm })}
      disabled={isPending || !mm}
      className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-black hover:opacity-90 disabled:opacity-50"
    >
      {isPending ? "Connecting…" : "Connect MetaMask"}
    </button>
  );
}
