#!/bin/sh
# Creates the Keycloak database alongside the platform database (first start only).
set -e
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
  SELECT 'CREATE DATABASE keycloak' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'keycloak')\gexec
  SELECT 'CREATE DATABASE middly_test' WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'middly_test')\gexec
EOSQL
