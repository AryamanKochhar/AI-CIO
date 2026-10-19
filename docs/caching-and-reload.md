# Decision caching and reload behavior

The Decisions page validates saved analysis and loads the Digital Financial Twin in parallel. A validated decision can render while the Twin request continues. Reloading an authenticated page waits for stored identity hydration before redirecting or persisting authentication state.

## Backend freshness

Each saved decision belongs to one user and one normalized request, including its objective, requested agents, and overrides. A cache hit requires matching financial and implementation fingerprints and an unexpired server timestamp. `DECISION_CACHE_TTL_SECONDS` defaults to 300 seconds; supported values are 0–3600, and 0 disables reuse. Missing, future, malformed, or expired timestamps fail closed. Cache API responses use `Cache-Control: private, no-store`.

The financial fingerprint uses one PostgreSQL statement to digest complete user financial rows. It includes holdings, all transactions, snapshots, liabilities, fixed deposits, goals, cashflows, constraints, documents, behavioral assessments, relevant security metadata, and journey completion flags. Navigation and read-created journey metadata do not invalidate saved analysis. The fingerprint also covers public provider/model configuration, the current date, source code, instrument definitions, knowledge Markdown/JSON, and skill files. Credentials and raw financial inputs are not included in the returned fingerprint metadata.

Identical concurrent requests use a PostgreSQL advisory lock, recheck the cache after acquiring it, and share one completed result across worker connections. The connection remains owned until its lock is released, even when the analysis pipeline commits intermediate work. Financial inputs are fingerprinted again after generation; changes during generation reject the result instead of saving an already stale analysis. Sequential saves retain the latest 12 request variants per user. Concurrent saves for different request variants can temporarily exceed that retention target until the next save prunes them.

Market context is the context saved with the analysis. Cache metadata records the save time, expiry, and input fingerprint; it does not claim to have fetched live prices on every hit. A changed request, changed input, changed knowledge, expiry, or explicit refresh triggers a fresh run.

## Browser storage and invalidation

React Query keys include the user and decision objective. Saved decisions are revalidated with the server on reload and are not persisted in browser storage. Previous results are withheld while validation is pending and cleared when validation fails or reports stale input.

Only a short-lived Twin snapshot is kept in `sessionStorage`: one active user, a 30-second lifetime, an API-server identity, and a limit of 131,072 characters (about 256 KiB of UTF-16 text). Invalid timestamps, another account, an API-server change, or oversized content clear or reject the snapshot. No financial snapshot is written to `localStorage`. Logout/account switching clears the snapshot, cancels old workspace queries, and remounts page state. Late responses cannot write another user's snapshot.

Successful financial mutations clear the Twin snapshot, mark saved analysis stale for every objective, cancel outstanding workspace reads, and refetch the current user's workspace. Requests receive cancellation signals and use `fetch` with `cache: no-store`.

## Verification

Targeted cache validation on the local PostgreSQL 17.6 test database passed 12 backend tests. Coverage includes in-place edits, transactions older than the former 200-row window, one-statement fingerprinting, navigation stability, expiry/future timestamps, changed knowledge/configuration, user isolation, retention, concurrent misses across engine connections, and input changes during generation. The measured fingerprint used one SQL round trip and took 17.172 ms in that local test. These numbers describe the local test environment rather than hosted database latency or model generation time.

Five Node tests passed for browser snapshot expiry, reload restoration, account changes, rejected late writes, bounded storage, corrupt metadata, API identity changes, and mutation targeting. TypeScript checking completed without errors. Actual browser reload behavior and hosted response times are separate runtime checks.

The final browser run used the PowerShell launcher in production mode and the synthetic Tom profile. A hard mobile reload restored the validated saved result in 1.41 seconds. A read-only comparison against the previous delivered fingerprint reduced database statements from 47 to 1 and measured fingerprint time from 6,279 ms to 289 ms. Three saved-decision requests returned cache hits with a median response time of 770 ms. These are observations from one synthetic fixture and the current shared database connection; they do not predict model generation time or general production performance. See [runtime measurements](validation/cache-runtime.json) and [browser checks](screenshots/ui-checks.json).

Run the backend cache tests only with the isolated local test database and `AICIO_TESTING=1`; never point them at a shared application database. The commands below assume the local PostgreSQL test service is already running:

```powershell
$env:AICIO_TESTING = '1'
$env:TEST_DATABASE_URL = 'postgresql://postgres@127.0.0.1:55439/ai_cio_test'
$env:POSTGRES_ADMIN_URL = 'postgresql://postgres@127.0.0.1:55439/postgres'
python -m pytest -q tests/test_decision_cache.py
```

From `apps/web`, run the browser storage tests and TypeScript check with the installed toolchain:

```powershell
node --experimental-strip-types --test src/lib/__tests__/workspace-cache.test.ts
..\..\node_modules\.bin\tsc.CMD --noEmit
```
