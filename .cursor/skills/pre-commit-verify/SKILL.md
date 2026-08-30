---
name: pre-commit-verify
description: >-
  Run the full pre-commit verification suite before committing or opening a PR —
  typecheck, lint, build, and pytest — mirroring CI. Fix failures in a loop until
  green, then produce a CodeRabbit-style summary report. Use when the user asks
  to commit, push, create a PR, verify changes, run pre-commit checks, or wants
  testing done before committing.
---

# Pre-Commit Verification

Run **all** quality gates before any commit or PR — like CodeRabbit reviewing your branch before merge.

## When to use

- User asks to **commit**, **push**, or **create a PR**
- User says "verify", "pre-commit", "run tests before commit", or "check before committing"
- You finished a feature and are about to mark work done
- User references CodeRabbit-style review or pre-merge checks

## Hard rules

1. **Never commit while checks are failing** — fix or report blockers first.
2. **Run the full suite** — do not skip steps because the change "looks small".
3. **Re-run after fixes** until all gates pass.
4. **Do not push** unless the user explicitly asked and all gates pass.

## Quick start

From repo root:

```bash
make verify          # full suite (matches CI)
make verify-quick    # skip build (faster iteration)
./scripts/pre-commit-verify.sh
```

## Verification workflow

Copy this checklist and track progress:

```
Pre-commit verification:
- [ ] Step 1: Inspect changed files (git diff / git status)
- [ ] Step 2: Run make verify
- [ ] Step 3: Fix any failures
- [ ] Step 4: Re-run make verify until green
- [ ] Step 5: Write summary report (template below)
- [ ] Step 6: Commit only if user asked AND all checks pass
```

### Step 1 — Scope the change

Run in parallel:

```bash
git status
git diff
git diff --staged
```

Identify which layers changed (API, web, packages, migrations, Docker) to focus debugging if a gate fails.

### Step 2 — Run the full suite

```bash
make verify
```

This runs, in order:

| Gate | Command | CI job |
|------|---------|--------|
| Typecheck | `pnpm typecheck` | frontend |
| Lint | `pnpm lint` | frontend |
| Build | `pnpm build` | frontend |
| Backend tests | `make test` (pytest + Postgres) | backend |

Requirements:

- `.venv` with deps installed (`make install`)
- Docker running for Postgres (`make test` starts it automatically)
- pnpm available

Use `make verify-quick` only during fix loops; run full `make verify` before the final commit.

### Step 3 — Fix failures

Work **gate by gate**, starting with the first failure:

| Failure | Likely fix |
|---------|------------|
| Typecheck | Fix TS types; run `pnpm typecheck` in the failing package |
| Lint | Fix eslint issues; check `apps/web/eslint.config.mjs` |
| Build | Fix Next.js/build errors; missing exports, client/server boundary |
| Pytest | Fix logic or update tests; ensure Postgres is up (`docker info`) |

After each fix, re-run the **full** `make verify` (not just the failing step) before proceeding.

### Step 4 — Optional targeted checks

While iterating on a single layer:

```bash
make typecheck    # frontend only
make lint         # frontend only
make test         # backend only
pnpm --filter @ai-cio/web build   # web only
```

Always finish with `make verify` before commit.

### Step 5 — Summary report

Post this report to the user before committing:

```markdown
## Pre-commit verification report

### Summary
[✅ All checks passed | ❌ N checks failed] (X/X gates)

### Gates
| Gate | Status | Notes |
|------|--------|-------|
| Typecheck | ✅ / ❌ | |
| Lint | ✅ / ❌ | |
| Build | ✅ / ❌ | |
| Backend tests | ✅ / ❌ | |

### Changed scope
- [list key files or areas touched]

### Failures (if any)
[Paste concise error excerpts and proposed fixes]

### Ready to commit
[Yes — all gates passed | No — fix failures above first]
```

### Step 6 — Commit (only when asked)

Only after **all gates pass** and the user explicitly requested a commit:

1. `git status` / `git diff` / `git log -1 --format='%s'`
2. Stage relevant files (never `.env`, credentials)
3. Commit with a concise message focused on **why**
4. `git status` to confirm

Do **not** push unless explicitly requested.

## Failure handling

- **Postgres unavailable**: ensure Docker is running; `make db-up` then retry `make test`
- **pnpm missing**: `corepack enable && pnpm install`
- **venv missing**: `make install`
- **Lint config missing** in a package: fix or document as known gap; do not skip silently
- **Flaky test**: re-run once; if still failing, investigate — do not `--no-verify` commit

## Do NOT

- Commit with failing tests or type errors
- Use `git commit --no-verify` unless the user explicitly requests it
- Skip `make verify` for "docs-only" changes if CI would still run
- Mark work complete without running at least `make verify` or equivalent

## Related project docs

- CI definition: `.github/workflows/ci.yml`
- Testing conventions: `skills/testing.md`
- Change control: `skills/change-control.md`
