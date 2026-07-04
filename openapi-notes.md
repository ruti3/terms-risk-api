# OpenAPI notes (x402scan discovery)

Spec: https://x402scan.com/discovery/spec

## Discovery endpoints

| Path | Description |
|------|-------------|
| `/openapi.json` | OpenAPI-first discovery (recommended) |
| `/.well-known/x402` | Compatibility resource fan-out |
| `/.well-known/x402.json` | Same payload (some clients fetch `.json`) |

## POST /terms-risk

### OpenAPI extensions (per operation)

- `x-payment-info` — dynamic USD pricing $0.01–$0.03, `protocols: [{x402}]`
- `responses.402` — Payment Required
- `info.x-guidance` — agent instructions at document level

### Request body

| Field | Type | Required |
|-------|------|----------|
| `url` | string (URL) | yes |
| `use_case` | string | yes |

### Response 200

See `TermsRiskResponse` schema in `/openapi.json`.

### Runtime 402 (x402scan requirement)

When `X402_ENABLED=true`, probing without payment:

```bash
curl -i -X POST https://yourdomain.com/terms-risk
```

Must return `402` with parseable `accepts` array and Bazaar input schema (provided by x402 SDK middleware).

### Errors

| Status | `error_type` examples |
|--------|------------------------|
| 400 | `invalid_url`, `timeout`, `blocked`, `non_html`, `empty_content` |
| 402 | Payment required (x402) |
| 502 | `analysis_error` |

## Environment

```
X402_ENABLED=true
X402_PAY_TO=0x...
X402_NETWORK=eip155:84532
X402_FACILITATOR_URL=https://x402.org/facilitator
X402_SKIP_PAYMENT=false
PUBLIC_BASE_URL=https://api.yourdomain.com
```

`eip155:84532` (Base Sepolia) works with `https://x402.org/facilitator`. For Base mainnet (`eip155:8453`), use a mainnet facilitator.

## Validate

```bash
npx -y @agentcash/discovery yourdomain.com -v
```
