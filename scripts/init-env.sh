#!/usr/bin/env bash
# Creates .env from .env.example with freshly generated random secrets.
# Demo user passwords are kept as documented so the walkthrough works.
set -euo pipefail
cd "$(dirname "$0")/.."

if [[ -f .env && "${1:-}" != "--force" ]]; then
  echo ".env already exists (use --force to regenerate)"
  exit 0
fi

rand() { openssl rand -hex "${1:-24}" 2>/dev/null || head -c "${1:-24}" /dev/urandom | od -An -tx1 | tr -d ' \n'; }

cp .env.example .env
for var in POSTGRES_PASSWORD REDIS_PASSWORD RABBITMQ_PASSWORD KEYCLOAK_ADMIN_PASSWORD OIDC_CLIENT_SECRET \
           IDENTITY_CLIENT_SECRET EDUCATION_API_KEY EMPLOYMENT_BASIC_PASSWORD SKILL_API_KEY GRIEVANCE_CLIENT_SECRET \
           MOCK_ADMIN_KEY GRAFANA_ADMIN_PASSWORD; do
  value="$(rand 18)"
  sed -i.bak "s|^${var}=.*|${var}=${value}|" .env
done
sed -i.bak "s|^SESSION_SECRET=.*|SESSION_SECRET=$(rand 32)|" .env
rm -f .env.bak
echo "✔ .env created with random secrets."
echo "  Note: if Postgres/Keycloak volumes already exist from a previous run, remove them first: docker compose down -v"
