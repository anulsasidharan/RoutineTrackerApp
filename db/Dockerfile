FROM postgres:16-alpine

# Copy the initialisation script into the Docker-entrypoint init directory.
# Postgres automatically runs all *.sql files in this directory the first time
# the data volume is created (i.e. on a fresh container with an empty volume).
COPY init.sql /docker-entrypoint-initdb.d/init.sql
