# comic-scraper

UPC/EAN-5 comic issue lookup against the [Metron](https://metron.cloud) API, with a browser UI (camera barcode scan + manual entry) served by the same FastAPI app.

## Run with Docker

```bash
cp .env.example .env          # fill in METRON_USERNAME / METRON_PASSWORD / DB_PASSWORD
docker compose up --build
```

Service listens on `http://localhost:9095`.

```bash
curl "http://localhost:9095/lookup/75960608612100?ean5=00121"
```

`docker-compose.override.yml` is picked up automatically by `docker compose up` and adds a bind mount + `--reload` for **backend** local development. It targets the `builder` Dockerfile stage, which does not include the built frontend — visiting `/` in this mode will 404. **To see the UI**, bypass the override and build the full multi-stage image (includes the `frontend-builder` stage):

```bash
docker compose -f docker-compose.yml up --build
```

Then open `http://localhost:9095/` (or your Caddy-proxied domain) in a browser.

## Frontend

`frontend/` is a Vite + React 19 + TypeScript app (see `frontend/package.json` for exact versions). It's built as static assets and served by FastAPI itself (`api.py` mounts `StaticFiles` at `/`, after the `/health` and `/lookup` routes so those still take precedence) — one container, one domain, no CORS configuration needed.

Barcode scanning uses [`zxing-wasm`](https://www.npmjs.com/package/zxing-wasm) (the `reader` subpath, WASM bundled as a local static asset rather than fetched from a CDN — matches the self-hosted approach used everywhere else in this project). A camera capture reads the UPC-A/EAN-13 symbol and, if present, the EAN-5 add-on symbol (`eanAddOnSymbol: "Read"` — reads it if found, doesn't require it, so older comics with no EAN-5 barcode at all scan fine too). `getUserMedia` requests the highest resolution the device offers (`width`/`height` `ideal: 3840`/`2160`) since the EAN-5's bars are much narrower than the main UPC-A bars and need more effective resolution to resolve — reading the add-on via camera is inherently less reliable than the main code even with this, so a hardware scanner (see `ScanInput` below) is the more dependable option when the EAN-5 specifically matters.

Unlike the hardware-scanner path, the camera does **not** auto-submit: it keeps scanning continuously and shows whatever it currently has decoded (upgrading from UPC-only to UPC+EAN-5 if a later frame catches the add-on), and only queries once you click "Look Up" — deliberate, since a query fired the instant the main UPC alone is recognized would skip the add-on entirely if it just hadn't been caught yet. This also fixed a real bug: `onDetected` was in the scanning `useEffect`'s dependency array, and `App.tsx` passes it as a fresh inline function on every render, so the camera stream was being torn down and restarted on nearly every state change elsewhere in the app (e.g. every completed lookup) — never running long enough to reliably catch the add-on. The effect no longer depends on `onDetected` at all now that it isn't called from inside it.

Both fields in the detected-code box are editable — if the camera only caught the UPC and the EAN-5 field is empty, type it in by hand before clicking "Look Up." Once you start editing either field, a `userEditedRef` flag stops the still-running scan loop from overwriting your typing with its next frame's read; it resets on submit or when scanning is stopped/restarted, so the camera goes back to auto-updating for the next item.

`ScanInput` (`frontend/src/ScanInput.tsx`) supports a hardware keyboard-wedge barcode scanner typed directly into the page — it reads the UPC+EAN5 concatenated with no terminator keystroke, so unlike the camera it *does* auto-submit: it debounces ~150ms after the input stops changing and submits once the digit count is a valid length (12 = UPC only, 17 = UPC+EAN5 concatenated, auto-split 12/5). Camera confirmations, hardware scans, and manual typing all feed the same lookup path and append to a running list on screen; nothing is persisted server-side yet, per the current scope.

### Batch mode

The "Batch mode" checkbox switches camera scans and `ScanInput` submissions from "look up immediately" to "add to a staged, reviewable list" instead (default behavior is unchanged when it's off). The staged list supports inline editing and removal before submitting, and `BatchPanel` also accepts pasting multiple codes at once, one per line (12 or 17 digits each — invalid lines are silently skipped). Capped at 20 items client-side.

Submitting posts the batch to `POST /lookup/batch`, which streams results back one at a time as a hand-rolled SSE-over-`fetch` response (`frontend/src/batchApi.ts` parses `data: {...}\n\n` frames from `response.body`'s `ReadableStream` — plain `EventSource` can't be used here since it only supports `GET`, and this needs a request body). Results merge into the same running list used by single lookups, updating each entry in place as its result arrives rather than waiting for the whole batch.

`MetronClient` now has a `RateLimiter` (`metron/ratelimit.py`, sliding-window, thread-safe) built in — capped at 18 calls/minute by default (`metron_max_calls_per_minute` in `config.py`), a bit under Metron's documented 20/minute burst limit to leave headroom. This applies to *all* Metron traffic, not just batch requests, since a single item can already need 2 calls (concatenated code, then bare-UPC fallback) and a full 20-item batch of never-before-seen comics could need up to 40. The backend endpoint processes batch items sequentially and yields each result as it completes, so the rate limiter naturally paces the whole stream; a fully uncached 20-item batch can take a couple of minutes; that's expected and why results stream in incrementally instead of appearing all at once.

**Local frontend iteration** (fast HMR, without rebuilding the Docker image each time): run the backend via Docker as usual, then in a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Vite's dev server proxies `/lookup` and `/health` to `http://localhost:9095` (configured in `vite.config.ts`), so the UI works against the real running backend with no CORS setup.

## Run the CLI directly

```bash
docker compose run --rm app lookup 75960608612100 00121
```

## Local dev without Docker

```bash
uv sync
uv run comic-scraper lookup 75960608612100 00121
```

## Notes / known scaffold simplifications

- No `uv.lock` is committed yet — run `uv lock` locally once and commit it, then switch the Dockerfile's `uv sync` calls to `uv sync --frozen` for reproducible builds.
- The dev override runs `uvicorn` directly via `/app/.venv/bin/python -m uvicorn ... --reload`, not `uv run uvicorn ...`. `uv run` re-syncs (rebuilds/reinstalls) the editable `comic-scraper` package on every invocation, which raced against uvicorn's `--reload` supervisor spawning its worker subprocess and left the worker unable to import `comic_scraper` (`ModuleNotFoundError`) even though the parent process had just reinstalled it. Invoking the venv's Python directly, with `PYTHONPATH=/app/src` set explicitly, sidesteps that race.
- **SELinux**: on a host with SELinux enforcing (e.g. RHEL), the `./src:/app/src` bind mount in `docker-compose.override.yml` must carry the `:Z` suffix (already set) so Docker relabels the directory for exclusive container access — without it, SELinux denies the read with errors like `--reload-dir: Path '/app/src' is not readable`, even though the Unix permission bits look completely normal. If you bind-mount any other host path in the future, it needs the same treatment.
- The Postgres password is a plain env var (`DB_PASSWORD` in `.env`), not a Docker secret. Compose's `secrets:` only enforces file permissions/ownership under Swarm — in plain `docker compose up` those settings are ignored, the secret is just a bind-mounted file, and Compose's `secrets:` block has no mount-option syntax to add `:z`/`:Z` for SELinux. Not worth that combination of platform-dependent breakage for a local-dev-only credential; revisit with a real secrets manager if this ever runs in Swarm/K8s.
- The app takes discrete `POSTGRES_USER` / `POSTGRES_PASSWORD` / `POSTGRES_HOST` / `POSTGRES_DB` env vars and assembles the DB connection string in Python via SQLAlchemy's `URL.create()` (`config.py`), rather than interpolating `${DB_PASSWORD}` directly into a `postgresql://user:pass@host/db`-style string in YAML. A password containing URL-reserved characters (`@`, `#`, `%`, etc.) breaks naive string concatenation — an `@` inside the password gets misread as the userinfo/host separator, so part of the password silently becomes the "hostname" and DNS resolution fails with a garbled name. `URL.create()` percent-encodes each component correctly regardless of what characters the password contains.
- **UPC lookup strategy**: Metron stores the base UPC and EAN-5 supplement concatenated as one string in `Issue.upc` (and per-variant in `Variant.upc`), not as two separate fields — confirmed against real data. `UpcLookupService._find_issue()` queries with `upc12 + ean5` concatenated first; if that finds nothing (community-entered records are inconsistent, or the comic is old enough to predate the EAN-5 supplement entirely) it falls back to the bare 12-digit UPC alone. `_match_variant()` then checks the same concatenated code against each `Variant.upc` to identify the specific cover/printing, independent of which query actually found the issue.
- **Frontend scope**: the scanned/typed list lives only in browser state (a page refresh clears it) — no server-side persistence yet, per current scope. There's no client-side router either; it's a single view, so an unmatched path falls through to a plain 404 rather than an SPA fallback to `index.html`. Camera access (`getUserMedia`) requires a secure context — works on `localhost` and on the Caddy-fronted HTTPS domain, but not over plain HTTP on a LAN IP.
- No `frontend/package-lock.json` regeneration is automated — if you add/update npm dependencies, run `npm install` locally and commit the updated lockfile so the Dockerfile's `npm ci` in the `frontend-builder` stage stays reproducible.
- **`LookupResult` fields beyond the core UPC match**: `series_volume`, `publisher_name`, `store_date`, `writers`, `pencillers`, `inkers`, and the full raw `credits` list (creator + every role Metron attached) are all populated from fields Metron's API already returns — nothing new is being inferred. Role-based fields (`writers`/`pencillers`/`inkers`/`cover_artists`) use case-insensitive *substring* matching against whatever role names Metron actually returns (e.g. `"pencil"` matches `"Penciller"`), since I don't have the exact enumerated role vocabulary confirmed — check the raw `credits` field, or `GET /api/role/` against your own Metron account, if a role doesn't show up as expected. All of these new fields are optional with empty/`None` defaults specifically so rows cached before this change still validate on a cache hit instead of 500ing.
