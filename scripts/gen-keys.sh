#!/usr/bin/env bash
# usage: ./scripts/gen-keys.sh [--force]   (--force makes a new pair, old tokens stop working)
set -euo pipefail

cd "$(dirname "$0")/.."

PRIVATE=${JWT_PRIVATE_KEY_FILE:-keys/jwt_private.pem}
PUBLIC=${JWT_PUBLIC_KEY_FILE:-keys/jwt_public.pem}

mkdir -p "$(dirname "$PRIVATE")" "$(dirname "$PUBLIC")"

if [ "${1:-}" = "--force" ] || [ ! -f "$PRIVATE" ]; then
  openssl genpkey -algorithm RSA -pkeyopt rsa_keygen_bits:2048 -out "$PRIVATE"
  chmod 600 "$PRIVATE"
  echo "created $PRIVATE"
fi

openssl pkey -in "$PRIVATE" -pubout -out "$PUBLIC"
echo "wrote $PUBLIC"
