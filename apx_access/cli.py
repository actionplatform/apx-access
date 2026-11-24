"""`action-platform access …` — the same operations as the tools, JSON on stdout."""

from __future__ import annotations

import json
from typing import Any, Optional

import typer

from apx_access.settings import connect

app = typer.Typer(
    help="Who has access to what, and keep it that way.", no_args_is_help=True
)
options: Any = None


def _print(model: Any) -> None:
    typer.echo(json.dumps(model.model_dump(exclude_none=True), indent=2))


@app.command("who")
def who(
    person: Optional[str] = typer.Option(None, help="A member's email"),
    service: Optional[str] = typer.Option(
        None, help="github, jenkins, sentry or dokploy"
    ),
) -> None:
    """A person's accounts and access, or every account on a service."""
    _print(connect(options).who(person, service))


@app.command("audit")
def audit(
    service: Optional[str] = typer.Option(None, help="Only this service"),
) -> None:
    """Drift per service against the organization."""
    _print(connect(options).audit(service))


@app.command("grant")
def grant(
    person: str,
    service: str,
    resource: str,
    level: str,
    account: Optional[str] = typer.Option(
        None, help="The person's account on the service"
    ),
    apply: bool = typer.Option(
        False, help="Change the service; without it, show the plan"
    ),
) -> None:
    """Give one person access on one service."""
    _print(connect(options).grant(person, service, resource, level, account, apply))


@app.command("revoke")
def revoke(
    person: str,
    service: str,
    resource: str,
    apply: bool = typer.Option(
        False, help="Change the service; without it, show the plan"
    ),
) -> None:
    """Take one grant away from one person."""
    _print(connect(options).revoke(person, service, resource, apply))


@app.command("offboard")
def offboard(
    person: str,
    apply: bool = typer.Option(
        False, help="Change the services; without it, show the plan"
    ),
    remove_from_platform: bool = typer.Option(
        False, help="Also remove the platform membership"
    ),
) -> None:
    """Remove a person from every service."""
    _print(connect(options).offboard(person, apply, remove_from_platform))


@app.command("sync")
def sync(
    service: Optional[str] = typer.Option(None, help="Only this service"),
    apply: bool = typer.Option(
        False, help="Change the services; without it, show the plan"
    ),
    reimport: bool = typer.Option(
        False, help="Import live state into the mapping again"
    ),
    link: list[str] = typer.Option(
        [], help="email:service:account, for an import; repeatable"
    ),
) -> None:
    """Make every service match the mapping; a service not imported yet is only imported."""
    links: dict[str, dict[str, str]] = {}

    for row in link:
        email, service_name, account = row.split(":", 2)
        links.setdefault(email, {})[service_name] = account

    _print(connect(options).sync(service, apply, reimport, links or None))
