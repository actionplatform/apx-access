"""The plugin: `access_*` tools, `action-platform access` commands, and the settings each service needs."""

from __future__ import annotations

from action_platform.abc import Option, Plugin, Surface

from apx_access import cli
from apx_access.tools import register_tools


class AccessPlugin(Plugin):
    slug = "access"
    name = "Access"
    description = (
        "Map an organization's members, teams and roles onto GitHub, Jenkins, Sentry "
        "and Dokploy: who has what, drift, grant, revoke, offboard, sync"
    )
    min_core = "0.32"
    needs = [
        "net: the Action Platform the CLI is logged in to (members, teams, the mapping)",
        "net: api.github.com (or github_url), the Jenkins url, sentry.io (or sentry_url), the Dokploy url — only the services configured",
        "env: AP_ACCESS_ORGANIZATION; AP_ACCESS_GITHUB_ORG, AP_ACCESS_GITHUB_TOKEN, AP_ACCESS_GITHUB_URL; AP_ACCESS_JENKINS_URL, AP_ACCESS_JENKINS_USER, AP_ACCESS_JENKINS_TOKEN; AP_ACCESS_SENTRY_ORG, AP_ACCESS_SENTRY_TOKEN, AP_ACCESS_SENTRY_URL; AP_ACCESS_DOKPLOY_URL, AP_ACCESS_DOKPLOY_API_KEY (or the same keys in the plugin's options)",
        "jenkins: the role-strategy plugin, selected as the authorization strategy",
    ]
    options = [
        Option(
            "organization",
            "Organization",
            "text",
            help="The platform organization (slug) whose members are mapped; empty uses the token's.",
        ),
        Option(
            "github_org",
            "GitHub organization",
            "text",
            help="The organization login, e.g. my-company.",
        ),
        Option(
            "github_token",
            "GitHub token",
            "secret",
            help="Classic token with admin:org and repo, from an organization owner. read:org and repo are enough to read.",
        ),
        Option(
            "github_url",
            "GitHub API URL",
            "url",
            help="Only for GitHub Enterprise Server: https://github.example.com/api/v3.",
        ),
        Option(
            "jenkins_url",
            "Jenkins URL",
            "url",
            help="https://jenkins.example.com, running Role-based Authorization Strategy.",
        ),
        Option(
            "jenkins_user", "Jenkins user", "text", help="An administrator's user id."
        ),
        Option(
            "jenkins_token",
            "Jenkins API token",
            "secret",
            help="That user's API token (user menu > Security > API Token).",
        ),
        Option(
            "sentry_org", "Sentry organization", "text", help="The organization slug."
        ),
        Option(
            "sentry_token",
            "Sentry token",
            "secret",
            help="A personal token with member:admin, team:write and org:read (member:read and team:read to read only).",
        ),
        Option("sentry_url", "Sentry URL", "url", help="Only for self-hosted Sentry."),
        Option(
            "dokploy_url",
            "Dokploy URL",
            "url",
            help="Where the Dokploy dashboard answers.",
        ),
        Option(
            "dokploy_api_key",
            "Dokploy API key",
            "secret",
            help="An owner's API key (Settings > Profile > API keys).",
        ),
    ]

    def register(self, surface: Surface) -> None:
        if surface.mcp is not None:
            register_tools(surface.mcp, surface.options)

        if surface.cli is not None:
            cli.options = surface.options
            surface.cli.add_typer(cli.app, name="access")
