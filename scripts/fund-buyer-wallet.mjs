#!/usr/bin/env node
/**
 * Fund a CDP buyer wallet with Base Sepolia ETH (gas) + USDC (x402 payments).
 *
 * Usage:
 *   node scripts/fund-buyer-wallet.mjs
 *   node scripts/fund-buyer-wallet.mjs --name terms-risk-buyer
 */

import { createCdpClient } from "./lib/cdp-credentials.mjs";

const NETWORK = "base-sepolia";
const DEFAULT_NAME = "terms-risk-buyer";

function parseArgs() {
  const args = process.argv.slice(2);
  let name = DEFAULT_NAME;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--name" && args[i + 1]) name = args[++i];
  }
  return { name };
}

async function main() {
  const { name } = parseArgs();
  const cdp = createCdpClient();
  const account = await cdp.evm.getOrCreateAccount({ name });

  console.log(`Buyer wallet: ${account.address} (${name})`);
  console.log(`Funding on ${NETWORK}...`);

  const eth = await account.requestFaucet({ network: NETWORK, token: "eth" });
  console.log(`  ETH faucet tx: ${eth.transactionHash ?? eth}`);

  const usdc = await account.requestFaucet({ network: NETWORK, token: "usdc" });
  console.log(`  USDC faucet tx: ${usdc.transactionHash ?? usdc}`);

  console.log(`
Funded. Run a paid API call:

  npm run x402:pay
`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
