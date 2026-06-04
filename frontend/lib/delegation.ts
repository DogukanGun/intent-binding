/**
 * MetaMask Smart Accounts — freeze intent as an ERC-7710 delegation.
 *
 * Flow:
 *   1. Build a MetaMask Smart Account for the connected EOA.
 *   2. Build caveats that mirror the IntentMandate:
 *        - allowedTargets : only the USDC token contract may be called
 *        - erc20PeriodTransfer : cap the USDC spend over the mandate window
 *        - timestamp : validity window (not_before / not_after)
 *   3. createDelegation(user -> agent session key) with those caveats.
 *   4. The user signs it in MetaMask (smartAccount.signDelegation).
 *
 * The signed delegation is the on-chain-enforceable twin of the backend mandate;
 * the agent later redeems it (relayed gaslessly via 1Shot).
 *
 * NOTE: caveat config shapes track the installed @metamask/delegation-toolkit
 * (0.13.0). If you bump the toolkit, re-check addCaveat() configs against its types.
 */

import {
  Implementation,
  toMetaMaskSmartAccount,
  createDelegation,
} from "@metamask/delegation-toolkit";
import { createCaveatBuilder } from "@metamask/delegation-toolkit/utils";
import type { Account, Address, Chain, Hex, PublicClient, Transport, WalletClient } from "viem";

/** A connected wallet client (account is guaranteed defined). */
type ConnectedWalletClient = WalletClient<Transport, Chain | undefined, Account>;

export type MandateParams = {
  token: Address; // USDC
  capUnits: bigint; // cap in token base units (6 dp)
  notBefore: number; // unix seconds
  notAfter: number; // unix seconds
  sessionKey: Address; // the agent's session account (delegate)
};

/** Build a MetaMask Smart Account for the connected wallet (Hybrid implementation). */
export async function buildSmartAccount(
  publicClient: PublicClient,
  walletClient: ConnectedWalletClient,
  owner: Address
) {
  return toMetaMaskSmartAccount({
    client: publicClient,
    implementation: Implementation.Hybrid,
    deployParams: [owner, [], [], []],
    deploySalt: "0x" as Hex,
    // The connected wallet signs on behalf of the smart account.
    signer: { walletClient },
  });
}

/** Caveats mirroring the IntentMandate scope (target/amount/time). */
export function buildMandateCaveats(environment: unknown, p: MandateParams) {
  const periodSeconds = Math.max(1, p.notAfter - p.notBefore);
  return (
    createCaveatBuilder(environment as never)
      // Only the USDC contract may be invoked by a redemption.
      .addCaveat("allowedTargets", { targets: [p.token] })
      // Cap the USDC moved within the mandate window.
      .addCaveat("erc20PeriodTransfer", {
        tokenAddress: p.token,
        periodAmount: p.capUnits,
        periodDuration: periodSeconds,
        startDate: p.notBefore,
      })
      // Validity window.
      .addCaveat("timestamp", {
        afterThreshold: p.notBefore,
        beforeThreshold: p.notAfter,
      })
      .build()
  );
}

/**
 * Create + sign the delegation that freezes intent.
 * Returns the signed delegation (to send to the backend / store for redemption).
 */
export async function freezeIntentDelegation(
  smartAccount: Awaited<ReturnType<typeof buildSmartAccount>>,
  params: MandateParams
) {
  // The DeleGator environment carries enforcer addresses for this chain.
  const environment = (smartAccount as unknown as { environment: unknown }).environment;
  const caveats = buildMandateCaveats(environment, params);

  const delegation = createDelegation({
    from: smartAccount.address,
    to: params.sessionKey,
    caveats,
    // @ts-expect-error environment is accepted by the installed toolkit build
    environment,
  });

  const signature = await smartAccount.signDelegation({ delegation });
  return { ...delegation, signature } as typeof delegation & { signature: Hex };
}

/** Serialize a delegation for transport to the backend (bigint-safe). */
export function serializeDelegation(delegation: unknown): string {
  return JSON.stringify(delegation, (_k, v) =>
    typeof v === "bigint" ? v.toString() : v
  );
}
