"""Where a setting comes from, in order: the process environment (`AP_ACCESS_<KEY>`), then the plugin's options store on this machine. A provider is on when its organization or URL is set."""

from __future__ import annotations

import os
from typing import TYPE_CHECKING, Any, Optional

from action_platform.plugins.options import FileOptions

from apx_access.abc import AccessError, Provider
from apx_access.providers.dokploy import DokployProvider
from apx_access.providers.github import GitHubProvider
from apx_access.providers.jenkins import JenkinsProvider
from apx_access.providers.sentry import SentryProvider

if TYPE_CHECKING:
    from apx_access.service import Access

SLUG = "access"
SERVICES = ("github", "jenkins", "sentry", "dokploy")


def setting(key: str, options: Any = None) -> Optional[str]:
    found = os.environ.get(f"AP_{SLUG}_{key}".upper())

    if not found:
        found = (options or FileOptions(SLUG)).get(key)

    return str(found) if found else None


def _need(service: str, **values: Optional[str]) -> dict[str, str]:
    missing = [k for k, v in values.items() if not v]

    if missing:
        names = ", ".join(f"AP_ACCESS_{k.upper()}" for k in missing)
        raise AccessError(
            f"{service}: set {names} (or the plugin's options) to read it"
        )

    return {k: str(v) for k, v in values.items()}


def configured(options: Any = None) -> list[str]:
    """The services this machine is set up for."""
    keys = {
        "github": "github_org",
        "jenkins": "jenkins_url",
        "sentry": "sentry_org",
        "dokploy": "dokploy_url",
    }

    return [s for s in SERVICES if setting(keys[s], options)]


def provider(service: str, options: Any = None) -> Provider:
    def s(key: str) -> Optional[str]:
        return setting(key, options)

    if service == "github":
        v = _need("github", github_org=s("github_org"), github_token=s("github_token"))
        return GitHubProvider(
            v["github_org"],
            v["github_token"],
            s("github_url") or "https://api.github.com",
        )

    if service == "jenkins":
        v = _need(
            "jenkins",
            jenkins_url=s("jenkins_url"),
            jenkins_user=s("jenkins_user"),
            jenkins_token=s("jenkins_token"),
        )
        return JenkinsProvider(v["jenkins_url"], v["jenkins_user"], v["jenkins_token"])

    if service == "sentry":
        v = _need("sentry", sentry_org=s("sentry_org"), sentry_token=s("sentry_token"))
        return SentryProvider(
            v["sentry_org"], v["sentry_token"], s("sentry_url") or "https://sentry.io"
        )

    if service == "dokploy":
        v = _need(
            "dokploy",
            dokploy_url=s("dokploy_url"),
            dokploy_api_key=s("dokploy_api_key"),
        )
        return DokployProvider(v["dokploy_url"], v["dokploy_api_key"])

    raise AccessError(f"unknown service {service!r}; one of {', '.join(SERVICES)}")


def connect(options: Any = None) -> "Access":
    """The operations wired to the platform the CLI is logged in to and to every service this machine is set up for; a service missing a credential answers with what to set."""
    from apx_access.directory import PlatformDirectory
    from apx_access.service import Access

    providers: dict[str, Provider] = {}
    errors: dict[str, str] = {}

    for service in configured(options):
        try:
            providers[service] = provider(service, options)
        except AccessError as e:
            errors[service] = str(e)

    if not providers and not errors:
        raise AccessError(
            "no service configured: set AP_ACCESS_GITHUB_ORG, AP_ACCESS_JENKINS_URL, AP_ACCESS_SENTRY_ORG or AP_ACCESS_DOKPLOY_URL"
        )

    return Access(
        PlatformDirectory(organization=setting("organization", options)),
        providers,
        errors,
    )
