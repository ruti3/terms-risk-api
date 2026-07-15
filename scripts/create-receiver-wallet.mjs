#!/usr/bin/env node
/**
 * Create (or fetch) a CDP EVM account for receiving x402 payments.
 *
 * Usage:
 *   node scripts/create-receiver-wallet.mjs
 *   node scripts/create-receiver-wallet.mjs --name my-receiver
 *
 * Credentials (first match wins):
 *   - CDP_API_KEY_ID / CDP_API_KEY_SECRET / CDP_WALLET_SECRET in .env
 *   - cdp_api_key.json + cdp_wallet_secret.txt in project root
 */

import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import { createCdpClient } from "./lib/cdp-credentials.mjs";

const __dirname = dirname(fileURLToPath(import.meta.url));
const ROOT = resolve(__dirname, "..");

dotenv.config({ path: resolve(ROOT, ".env") });

const DEFAULT_NAME = "terms-risk-receiver";

function parseArgs() {
  const args = process.argv.slice(2);
  let name = DEFAULT_NAME;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--name" && args[i + 1]) {
      name = args[++i];
    }
  }
  return { name };
}

async function main() {
  const { name } = parseArgs();
  const cdp = createCdpClient();

  const account = await cdp.evm.getOrCreateAccount({ name });
  const address = account.address;

  console.log(`
CDP receiver wallet ready.

  Name:    ${name}
  Address: ${address}
  Network: base-sepolia (eip155:84532)

Add to .env:

  X402_PAY_TO=${address}
  X402_ENABLED=true
  X402_SKIP_PAYMENT=false
  X402_NETWORK=eip155:84532
  X402_FACILITATOR_URL=https://x402.org/facilitator
  X402_PRICE=$0.03

Restart the API, then verify x402:

  node scripts/probe-x402.mjs
`);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
