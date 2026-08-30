# Change Control — AI-CIO

## Purpose

Prevent unnecessary frameworks, duplicated implementations, and architectural drift during AI-CIO development.

## When to use

Before introducing:

- A new framework or major dependency
- A new database or storage system
- A new user-facing application or dashboard
- A duplicated business logic path (e.g., frontend scoring, MCP-only portfolio math)
- A new microservice or message broker

## Architectural rules

1. **Inspect first** — search the repository for an existing implementation
2. **One product** — users experience one AI-CIO, not internal engines
3. **One database** — PostgreSQL is the system of record
4. **One domain layer** — API, MCP, and CLI call the same services
5. **Backend owns validation** — psychometrics, money, documents scored/parsed server-side

## Implementation rules

- Prefer moving and integrating over rewriting
- Document the reason for any new layer in the PR / commit message
- Add or update tests for every behavioural change
- Update `docs/migration-map.md` when deprecating or moving code

## Testing requirements

- All existing tests must pass before merge
- New endpoints require API tests
- User isolation must be tested for any user-owned resource

## Security considerations

- Never store plaintext passwords
- Never expose raw CAS text or psychometric answers via API
- Scope every query by authenticated user_id

## Definition of done

- [ ] Existing implementation searched and documented
- [ ] Change justified in writing (why not extend existing code?)
- [ ] Tests pass (`pytest -q`, `pnpm typecheck`, `pnpm build`)
- [ ] Documentation updated (architecture, migration map if applicable)
- [ ] No duplicate business logic introduced
