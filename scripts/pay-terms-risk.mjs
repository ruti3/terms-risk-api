#!/usr/bin/env node
/**
 * Pay for and call POST /terms-risk via x402 (CDP buyer wallet).
 *
 * Prerequisites:
 *   - API running with X402_ENABLED=true, X402_SKIP_PAYMENT=false
 *   - Buyer wallet funded: npm run wallet:fund
 *
 * Usage:
 *   node scripts/pay-terms-risk.mjs
 *   node scripts/pay-terms-risk.mjs --url http://localhost:8000
 *   node scripts/pay-terms-risk.mjs --buyer-name terms-risk-buyer
 */

import { toAccount } from "viem/accounts";
import { x402Client, wrapFetchWithPayment, x402HTTPClient } from "@x402/fetch";
import { registerExactEvmScheme } from "@x402/evm/exact/client";
import { createCdpClient } from "./lib/cdp-credentials.mjs";

const DEFAULT_API = "http://localhost:8000";
const DEFAULT_BUYER = "terms-risk-buyer";
const DEFAULT_BODY = {
  url: "https://www.cloudflare.com/website-terms/",
  use_case: "Can I scrape and commercially reuse public listings?",
};

function parseArgs() {
  const args = process.argv.slice(2);
  let apiUrl = DEFAULT_API;
  let buyerName = DEFAULT_BUYER;
  for (let i = 0; i < args.length; i++) {
    if (args[i] === "--url" && args[i + 1]) apiUrl = args[++i];
    if (args[i] === "--buyer-name" && args[i + 1]) buyerName = args[++i];
  }
  return { apiUrl: apiUrl.replace(/\/$/, ""), buyerName };
}

async function main() {
  const { apiUrl, buyerName } = parseArgs();
  const endpoint = `${apiUrl}/terms-risk`;

  console.log(`Buyer:  ${buyerName}`);
  console.log(`Target: POST ${endpoint}\n`);

  const cdp = createCdpClient();
  const cdpAccount = await cdp.evm.getOrCreateAccount({ name: buyerName });
  const signer = toAccount(cdpAccount);

  console.log(`Payer address: ${signer.address}\n`);

  const client = new x402Client();
  registerExactEvmScheme(client, {
    signer,
    schemeOptions: {
      84532: { rpcUrl: "https://sepolia.base.org" },
    },
  });

  const fetchWithPayment = wrapFetchWithPayment(fetch, client);

  console.log("Calling API (402 → pay → retry)...\n");

  const response = await fetchWithPayment(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(DEFAULT_BODY),
  });

  const text = await response.text();

  if (!response.ok) {
    console.error(`Failed: HTTP ${response.status}`);
    console.error(text.slice(0, 500));
    process.exit(1);
  }

  const data = JSON.parse(text);
  console.log("✓ Paid request succeeded\n");
  console.log(JSON.stringify(data, null, 2));

  const httpClient = new x402HTTPClient(client);
  const settle = httpClient.getPaymentSettleResponse((name) =>
    response.headers.get(name),
  );
  if (settle) {
    console.log("\nPayment settled:", JSON.stringify(settle, null, 2));
  }
}

main().catch((err) => {
  console.error(err.message || err);
  if (String(err.message || err).toLowerCase().includes("insufficient")) {
    console.error("\nTry: npm run wallet:fund");
  }
  process.exit(1);
});
