"""`access_*` MCP tools. Reads are safe; every change is a dry run until `apply` is true — show the plan to the user and ask before applying."""

from __future__ import annotations

from typing import Annotated, Any, Optional

from action_platform.mcp.annotations import DESTRUCTIVE, REACHES_OUT, READ_ONLY
from pydantic import Field

from apx_access.models import Audit, Plan, Who
from apx_access.settings import connect

Person = Annotated[
    str,
    Field(description="The member's email on the platform (or user id, or exact name)"),
]
Service = Annotated[str, Field(description="github, jenkins, sentry or dokploy")]
Apply = Annotated[
    bool,
    Field(
        description="False shows the plan; true changes the service. Show the plan and ask first."
    ),
]


def register_tools(mcp: Any, options: Any) -> None:
    @mcp.tool(annotations=READ_ONLY)
    def who(
        person: Annotated[
            Optional[str],
            Field(
                description="A member's email: their accounts and access on every service"
            ),
        ] = None,
        service: Annotated[
            Optional[str],
            Field(
                description="A service: every account with access there and the member it belongs to"
            ),
        ] = None,
    ) -> Who:
        """Who has access to what. Give a person to see their accounts, live grants and drift on each service; give a service to list every account with access there."""
        return connect(options).who(person, service)

    @mcp.tool(annotations=READ_ONLY)
    def audit(
        service: Annotated[
            Optional[str], Field(description="Only this service")
        ] = None,
    ) -> Audit:
        """Drift per service: what each service holds against what the organization's members, roles and teams ask for — what a sync would change, members with no account linked, accounts that belong to no member."""
        return connect(options).audit(service)

    @mcp.tool(annotations=REACHES_OUT)
    def grant(
        person: Person,
        service: Service,
        resource: Annotated[
            str,
            Field(
                description="org, team/<slug>, repo/<name> (github); global, folder/<name> (jenkins); org, team/<slug> (sentry); org, project/<name> (dokploy)"
            ),
        ],
        level: Annotated[
            str,
            Field(
                description="github org member|admin, team member|maintainer, repo pull|triage|push|maintain|admin; jenkins global read|admin, folder read|build|configure; sentry org member|admin|manager|owner, team contributor|admin; dokploy org member|admin, project access"
            ),
        ],
        account: Annotated[
            Optional[str],
            Field(
                description="The person's account on the service (login, user id or email) when the mapping has none yet"
            ),
        ] = None,
        apply: Apply = False,
    ) -> Plan:
        """Give one person access on one service and record it in the mapping. Only that person's account is touched."""
        return connect(options).grant(person, service, resource, level, account, apply)

    @mcp.tool(annotations=DESTRUCTIVE)
    def revoke(
        person: Person,
        service: Service,
        resource: Annotated[
            str, Field(description="The resource as access_who shows it")
        ],
        apply: Apply = False,
    ) -> Plan:
        """Take one grant away from one person and drop it from the mapping. Access that comes from the person's role or team stays; the answer says which."""
        return connect(options).revoke(person, service, resource, apply)

    @mcp.tool(annotations=DESTRUCTIVE)
    def offboard(
        person: Person,
        apply: Apply = False,
        remove_from_platform: Annotated[
            bool,
            Field(
                description="Also remove the member from the organization on the platform"
            ),
        ] = False,
    ) -> Plan:
        """Remove a person everywhere: every grant of every linked account on every configured service, their entries in the mapping, and optionally their platform membership. The last administrator of a service is never removed."""
        return connect(options).offboard(person, apply, remove_from_platform)

    @mcp.tool(annotations=DESTRUCTIVE)
    def sync(
        service: Annotated[
            Optional[str], Field(description="Only this service")
        ] = None,
        apply: Apply = False,
        reimport: Annotated[
            bool,
            Field(
                description="Import live state into the mapping again instead of changing the services"
            ),
        ] = False,
        links: Annotated[
            Optional[dict[str, dict[str, str]]],
            Field(
                description="With an import: {member email: {service: account}} for accounts that are not the member's email (GitHub logins, Jenkins ids)"
            ),
        ] = None,
    ) -> Plan:
        """Make every service match the mapping. The first run only imports what the services hold today (nothing is changed, nothing removed); after that it adds, changes and removes to close the drift access_audit shows."""
        return connect(options).sync(service, apply, reimport, links)
