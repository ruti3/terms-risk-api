#!/usr/bin/env node
/**
 * Probe local Terms Risk API for x402 payment gate.
 *
 * Usage:
 *   node scripts/probe-x402.mjs
 *   node scripts/probe-x402.mjs --url http://localhost:8000
 *
 * Expected when x402 is working: HTTP 402 + Payment-Required header.
 * HTTP 400/200 means the request reached the handler (payment gate bypassed or off).
 */

const baseUrl = (() => {
  const idx = process.argv.indexOf("--url");
  return idx >= 0 && process.argv[idx + 1]
    ? process.argv[idx + 1].replace(/\/$/, "")
    : "http://localhost:8000";
})();

const body = {
  url: "https://example.com/terms",
  use_case: "commercial scraping",
};

async function main() {
  console.log(`Probing ${baseUrl}/terms-risk (unpaid)...\n`);

  const metaRes = await fetch(`${baseUrl}/`);
  if (!metaRes.ok) {
    console.error(`Cannot reach API at ${baseUrl} (GET / → ${metaRes.status})`);
    process.exit(1);
  }
  const meta = await metaRes.json();
  const pricing = meta.pricing ?? {};
  console.log("API status:");
  console.log(`  x402_enabled:       ${pricing.x402_enabled}`);
  console.log(`  x402_skip_payment:  ${pricing.x402_skip_payment}`);
  console.log(`  fresh_usd:          ${pricing.fresh_usd}`);
  console.log("");

  const res = await fetch(`${baseUrl}/terms-risk`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

  const paymentHeader =
    res.headers.get("payment-required") ??
    res.headers.get("Payment-Required");
  const text = await res.text();

  console.log(`POST /terms-risk → ${res.status} ${res.statusText}`);
  if (paymentHeader) {
    console.log(`Payment-Required: ${paymentHeader.slice(0, 80)}...`);
  }

  if (res.status === 402) {
    console.log(`
✓ x402 is working. Unpaid requests are blocked with 402.

Next: fund a buyer wallet with testnet USDC on Base Sepolia and pay via an x402 client.
Docs: https://docs.cdp.coinbase.com/x402/quickstart-for-buyers
`);
    return;
  }

  if (res.status === 400) {
    console.log(`Response: ${text.slice(0, 200)}`);
    console.log(`
✗ Got 400 — payment gate did NOT block this request.
  The handler ran and tried to fetch the URL (example.com/terms → 404).

Fix:
  1. Set X402_ENABLED=true and X402_SKIP_PAYMENT=false in .env
  2. Restart uvicorn (env changes are not hot-reloaded)
  3. Re-run: node scripts/probe-x402.mjs
`);
    process.exit(1);
  }

  if (res.status === 200) {
    console.log(`Response: ${text.slice(0, 120)}...`);
    console.log(`
✗ Got 200 — payment is not required. Check X402_ENABLED / X402_SKIP_PAYMENT and restart the server.
`);
    process.exit(1);
  }

  console.log(`Response: ${text}`);
  console.log(`Unexpected status ${res.status}. Check server logs.`);
  process.exit(1);
}

main().catch((err) => {
  console.error(err.message || err);
  process.exit(1);
});
