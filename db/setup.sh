#!/usr/bin/env bash
# Run this ONCE in your terminal to create the postgres role and database.
# Usage: bash db/setup.sh
set -e

DB_USER="gooddelusions"
DB_NAME="problems"
DB_PASS="devpassword"

sudo -u postgres psql <<SQL
DO \$\$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '${DB_USER}') THEN
    CREATE USER ${DB_USER} WITH PASSWORD '${DB_PASS}';
  END IF;
END
\$\$;

SELECT 'CREATE DATABASE ${DB_NAME} OWNER ${DB_USER}'
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}')
\gexec

GRANT ALL PRIVILEGES ON DATABASE ${DB_NAME} TO ${DB_USER};
SQL

echo "Done. Connect with: psql postgresql://${DB_USER}:${DB_PASS}@localhost/${DB_NAME}"
