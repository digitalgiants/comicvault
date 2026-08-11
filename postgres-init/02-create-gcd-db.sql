-- Only runs on a fresh postgres_data volume (official image only executes
-- docker-entrypoint-initdb.d/ scripts when the data directory is first created).
-- For an already-existing volume, run this once by hand instead:
--   docker compose exec postgres psql -U comicvault -d comicvault -c "CREATE DATABASE gcd;"
CREATE DATABASE gcd;
