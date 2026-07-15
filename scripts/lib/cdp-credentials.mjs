import { readFileSync, existsSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import dotenv from "dotenv";
import { CdpClient } from "@coinbase/cdp-sdk";

const __dirname = dirname(fileURLToPath(import.meta.url));
export const ROOT = resolve(__dirname, "../..");

dotenv.config({ path: resolve(ROOT, ".env") });

export function loadCdpCredentials() {
  let apiKeyId = process.env.CDP_API_KEY_ID;
  let apiKeySecret = process.env.CDP_API_KEY_SECRET;
  let walletSecret = process.env.CDP_WALLET_SECRET;

  const keyFile = resolve(ROOT, "cdp_api_key.json");
  const secretFile = resolve(ROOT, "cdp_wallet_secret.txt");

  if ((!apiKeyId || !apiKeySecret) && existsSync(keyFile)) {
    const key = JSON.parse(readFileSync(keyFile, "utf8"));
    apiKeyId = apiKeyId ?? key.id;
    apiKeySecret = apiKeySecret ?? key.privateKey;
  }

  if (!walletSecret && existsSync(secretFile)) {
    walletSecret = readFileSync(secretFile, "utf8").trim();
  }

  if (!apiKeyId || !apiKeySecret || !walletSecret) {
    throw new Error(
      "Missing CDP credentials. Set CDP_API_KEY_ID, CDP_API_KEY_SECRET, CDP_WALLET_SECRET in .env " +
        "or add cdp_api_key.json + cdp_wallet_secret.txt",
    );
  }

  return { apiKeyId, apiKeySecret, walletSecret };
}

export function createCdpClient() {
  const creds = loadCdpCredentials();
  return new CdpClient({
    apiKeyId: creds.apiKeyId,
    apiKeySecret: creds.apiKeySecret,
    walletSecret: creds.walletSecret,
  });
}
