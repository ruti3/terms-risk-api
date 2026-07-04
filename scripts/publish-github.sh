#!/usr/bin/env bash
# Create GitHub repo and push terms-risk-api.
# Prerequisites: gh auth login
set -euo pipefail

REPO_NAME="${1:-terms-risk-api}"
VISIBILITY="${2:-public}"

cd "$(dirname "$0")/.."

if ! gh auth status &>/dev/null; then
  echo "Run: gh auth login"
  exit 1
fi

gh repo create "$REPO_NAME" \
  --source=. \
  --public \
  --description "FastAPI Terms of Service risk analyzer with x402 payment and agent discovery" \
  --push

echo ""
echo "Done: https://github.com/$(gh api user -q .login)/$REPO_NAME"
