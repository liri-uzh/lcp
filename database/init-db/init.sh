#!/bin/bash
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/roles.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/init_lcp.sql
psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /docker-entrypoint-initdb.d/scripts/functions_importer.sql
# xz -dc /docker-entrypoint-initdb.d/initdb.sql.xz | psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"
touch /var/lib/postgresql/data/db.ready
