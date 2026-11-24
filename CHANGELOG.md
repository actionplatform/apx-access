# Changelog

## v0.1.2 — 2026-11-24

### Bug Fixes
- **audit:** a service that could not be read is not reported as imported (#5)

## v0.1.1 — 2026-11-24

### CI
- publish with the pypa action from the workflow, as apx-example does (#3)

## v0.1.0 — 2026-11-24

### Features
- who, audit, grant, revoke, offboard and sync as tools and commands (#1)
- **providers:** GitHub, Jenkins role-strategy, Sentry and Dokploy (#1)
- grants, the mapping, the provider contract and the diff (#1)

### Bug Fixes
- **providers:** team grants bring org membership, folder grants ask for global read, expired Dokploy invitations are no access (#1)
- import each service on the sync that first reads it; accounts compare without case (#1)

### Docs
- README with tools, settings and what each service does (#1)
- README and AGENTS (#1)

### Tests
- a failed read, case, team and folder companions, Dokploy invitations and admins (#1)
- services in memory, the operations end to end, a read-only live suite (#1)

### Build
- poetry package apx-access with the access entry point

### CI
- checks and git-flow through ci-github, PyPI publish on release (#1)

### Chores
- repository skeleton
