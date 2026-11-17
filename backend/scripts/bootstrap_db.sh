#!/usr/bin/env bash
# Create the local development/test databases and the two database roles.
#   qs_owner : owns the schema and runs migrations (never used by the running API)
#   qs_app   : runtime role, NOBYPASSRLS, DML only -> subject to Row-Level Security
# Usage: PGHOST=localhost PGUSER=postgres ./scripts/bootstrap_db.sh [db_name ...]
# Passwords here are for LOCAL DEVELOPMENT ONLY. Production credentials come from the secret manager.
set -euo pipefail
OWNER_PW="${QS_OWNER_PASSWORD:-qs_owner_dev}"
APP_PW="${QS_APP_PASSWORD:-qs_app_dev}"
DBS=("$@"); [ ${#DBS[@]} -eq 0 ] && DBS=(qs_dev qs_test)
PSQL=(psql -v ON_ERROR_STOP=1 -X -q)
"${PSQL[@]}" <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qs_owner') THEN
    CREATE ROLE qs_owner LOGIN PASSWORD '${OWNER_PW}' NOSUPERUSER NOCREATEROLE;
  END IF;
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'qs_app') THEN
    CREATE ROLE qs_app LOGIN PASSWORD '${APP_PW}' NOSUPERUSER NOCREATEROLE NOCREATEDB NOBYPASSRLS;
  END IF;
END \$\$;
SQL
for db in "${DBS[@]}"; do
  if ! "${PSQL[@]}" -tAc "SELECT 1 FROM pg_database WHERE datname='${db}'" | grep -q 1; then
    "${PSQL[@]}" -c "CREATE DATABASE ${db} OWNER qs_owner"
  fi
  "${PSQL[@]}" -d "${db}" -c "CREATE EXTENSION IF NOT EXISTS vector; CREATE EXTENSION IF NOT EXISTS pg_trgm; REVOKE ALL ON SCHEMA public FROM PUBLIC; GRANT USAGE, CREATE ON SCHEMA public TO qs_owner; GRANT USAGE ON SCHEMA public TO qs_app; ALTER SCHEMA public OWNER TO qs_owner;"
  echo "database ${db} ready"
done
