"""One contract per responsibility: a `Provider` reads and changes access on one service, a `Directory` says who belongs to the organization and keeps its mapping."""

from __future__ import annotations

from abc import ABC, abstractmethod

from action_platform.core.exception import ActionPlatformError

from apx_access.spec import Grant, Mapping, Op, Person


class AccessError(ActionPlatformError):
    """A service refused or could not be reached; the message names the service and the call, never a credential."""


class Provider(ABC):
    """Access on one service as grants `(account, resource, level)`. `levels` orders the levels of each resource kind, lowest first."""

    name: str
    levels: dict[str, tuple[str, ...]]

    @abstractmethod
    def read(self) -> list[Grant]:
        """Every grant the service holds today."""

    @abstractmethod
    def apply(self, op: Op) -> None:
        """Make one change; raise `AccessError` when the service refuses."""

    def kind(self, resource: str) -> str:
        return resource.split("/", 1)[0]

    def valid(self, resource: str, level: str) -> str:
        """Why the pair is not something this service can grant, or an empty string."""
        allowed = self.levels.get(self.kind(resource))

        if allowed is None:
            return f"{self.name}: unknown resource {resource!r}; use one of {', '.join(k + '/…' if k not in ('org', 'global') else k for k in self.levels)}"

        if level not in allowed:
            return f"{self.name}: {resource} takes {', '.join(allowed)}, not {level!r}"

        return ""

    def rank(self, grant: Grant) -> int:
        allowed = self.levels.get(self.kind(grant.resource), ())

        return allowed.index(grant.level) if grant.level in allowed else -1

    def strongest(self, grants: list[Grant]) -> list[Grant]:
        """One grant per account and resource, the highest level when a service reports several."""
        best: dict[tuple[str, str, str], Grant] = {}

        for g in grants:
            kept = best.get(g.key)

            if kept is None or self.rank(g) > self.rank(kept):
                best[g.key] = g

        return sorted(best.values())

    def expand(self, grants: set[Grant]) -> set[Grant]:
        """Grants the service needs alongside the ones asked for."""
        return grants

    def guard(self, ops: list[Op], live: list[Grant]) -> dict[Op, str]:
        """Changes refused before anything is sent, with the reason — the last administrator of a service is never removed."""
        return {}

    def order(self, op: Op) -> tuple[int, str]:
        first = self.kind(op.grant.resource) in ("org", "global")

        if op.action == "remove":
            return (2 if first else 1, op.grant.account)

        return (0 if first else 1, op.grant.account)


class Directory(ABC):
    """The organization on the platform: its people with role and teams, and where the mapping is kept."""

    @abstractmethod
    def people(self) -> list[Person]:
        """Every member with role and team slugs."""

    @abstractmethod
    def load(self) -> Mapping:
        """The stored mapping, empty before the first bootstrap."""

    @abstractmethod
    def save(self, mapping: Mapping) -> None:
        """Store the mapping for the organization."""

    @abstractmethod
    def remove(self, person: Person) -> None:
        """Take the person out of the organization on the platform."""
