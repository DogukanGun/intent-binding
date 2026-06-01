import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "IntentGuard — intent-bound agent payments",
  description:
    "Freeze human intent into an EIP-712 mandate and enforce it with ERC-7710 caveats so a prompt-injected agent can't drain your wallet.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body className="min-h-screen font-mono">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
