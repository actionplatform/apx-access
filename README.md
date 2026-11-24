# apx-access — deprecated

Access management moved out of this plugin:

- **The core** ([action-platform](https://github.com/actionplatform/action-platform) 0.33 and later) holds the engine — the mapping of members, roles and teams onto grants, the import that changes nothing, drift, dry runs — and the `access_audit`, `access_who`, `access_grant`, `access_revoke`, `access_offboard` and `access_sync` operations (remote MCP tools, `action-platform access …`, `/api/v1/access/*`). See [service access](https://github.com/actionplatform/action-platform/blob/master/docs/concept_service_access.md).
- **Each service's plugin** brings access on its service, beside its other tools:

| Service | Plugin |
|---|---|
| GitHub | [apx-github](https://github.com/actionplatform/apx-github) |
| Jenkins | [apx-jenkins](https://github.com/actionplatform/apx-jenkins) |
| Sentry | [apx-sentry](https://github.com/actionplatform/apx-sentry) |
| Dokploy | [apx-dokploy](https://github.com/actionplatform/apx-dokploy) 0.6.0 and later |

The core refuses to load a plugin with the slug `access`, so uninstall this one (`pip uninstall apx-access`) before upgrading the core.

A mapping stored by this plugin (the organization's options of the `access` plugin, key `mapping`) is where the core reads it, so an organization keeps what it imported.
