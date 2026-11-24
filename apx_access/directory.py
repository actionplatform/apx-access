"""The organization on the Action Platform the CLI is logged in to: members with role and teams from `/api/v1/members` and `/api/v1/teams`, and the mapping kept as the organization's options of this plugin — shared by everyone who manages access there."""

from __future__ import annotations

from typing import Any, Optional

from action_platform.remote.client import Remote

from apx_access.abc import Directory
from apx_access.spec import Mapping, Person

KEY = "mapping"
SLUG = "access"


class PlatformDirectory(Directory):
    def __init__(
        self, remote: Optional[Remote] = None, organization: Optional[str] = None
    ) -> None:
        self.remote = remote or Remote.from_credentials()
        self.organization = organization or None

    def people(self) -> list[Person]:
        teams: dict[str, list[str]] = {}

        for team in self.remote.teams(self.organization):
            for m in team.members:
                teams.setdefault(
                    str(m.get("userId") or m.get("user_id") or ""), []
                ).append(team.slug)

        return [
            Person(
                email=m.email.lower(),
                user_id=m.user_id,
                name=m.name,
                role=m.role,
                teams=tuple(sorted(teams.get(m.user_id, []))),
            )
            for m in self.remote.members(self.organization)
        ]

    def load(self) -> Mapping:
        return Mapping.of(self._options().get(KEY))

    def save(self, mapping: Mapping) -> None:
        options = self._options()
        options[KEY] = mapping.as_dict()
        self.remote._call(
            "PUT", f"plugins/{SLUG}/options", {"options": options}, self.organization
        )

    def remove(self, person: Person) -> None:
        self.remote._call(
            "DELETE", f"members/{person.user_id}", None, self.organization
        )

    def _options(self) -> dict[str, Any]:
        data = (
            self.remote._call("GET", f"plugins/{SLUG}/options", None, self.organization)
            or {}
        )

        return dict(data.get("options") or {})
