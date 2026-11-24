# AGENTS.md

Rules an AI agent (or a new contributor) follows in this repository.

## What this is

`apx-access`, an Action Platform plugin: `access_*` tools and `action-platform access` commands that map an organization's members, teams and roles onto GitHub, Jenkins, Sentry and Dokploy. The contract every plugin follows is `SPEC.md` in [apx-example](https://github.com/actionplatform/apx-example); read it before changing the shape of anything here.

## How it works

Grants are `(service, account, resource, level)`. A `Provider` per service (`providers/`) reads every grant and applies one `Op`; `policy.py` turns the platform's people and the mapping into the grants each service should hold and diffs them against live state; `service.py` holds the six operations; `directory.py` reads members and teams and keeps the mapping as the organization's plugin options on the platform.

## Rules that protect users

- Dry run unless `apply`. Never change a default to apply.
- The first sync imports and changes nothing; never remove access while there is no mapping.
- `Provider.guard` refuses removing or demoting the last administrator of a service; a new provider ships with its guard.
- A credential never reaches a message, a log line, the mapping or a test fixture.
- A tool, a level or a README line ships only with the code path that makes it true, exercised against the real service.

## Code

- Python 3.11+, `poetry run ruff check . && poetry run ruff format --check . && poetry run pytest` green before a commit.
- No comments inside function bodies; no test docstrings. Module docstrings say what the module is for.
- `register` declares only — no I/O at import or in `register`. Never monkey-patch `action_platform.*`.
- Talk to a service through `http.Http` only; tests drive `tests/fake.py`, never the network. The fake answers only the routes and fields the real API sends — read the service's API reference for each one.
- `needs` lists every host and environment variable the plugin touches.

## Commits and branches

[Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/): `type(scope): description`; one commit per concern. Git-flow: `<kind>/<issue>-<slug>` from `master`, kinds `feature bugfix hotfix release chore docs refactor test ci perf`; never commit on `master`. One pull request per issue.

## Release

`action-platform release <level>`; the published GitHub release runs `publish.yml`, which publishes to PyPI; then a PR to `plugins-index` with the new `latest`.
