"""A Dokploy instance: organization membership with its role, and which projects a member may open."""

from __future__ import annotations

from typing import Any, Optional

from apx_access.abc import AccessError, Provider
from apx_access.http import Http
from apx_access.spec import Grant, Op

FLAGS = (
    "canCreateProjects",
    "canCreateServices",
    "canDeleteProjects",
    "canDeleteServices",
    "canAccessToDocker",
    "canAccessToTraefikFiles",
    "canAccessToAPI",
    "canAccessToSSHKeys",
    "canAccessToGitProviders",
    "canDeleteEnvironments",
    "canCreateEnvironments",
)
LISTS = (
    "accessedProjects",
    "accessedEnvironments",
    "accessedServices",
    "accessedGitProviders",
    "accessedServers",
)


class DokployProvider(Provider):
    """Accounts are user emails. `org` is `member` or `admin` (the owner is read, never changed); `project/<name>` opens one project and its environments to a member — owners and admins see every project already. An added member gets an invitation and counts as granted while it is pending; projects follow once it is accepted."""

    name = "dokploy"
    levels = {"org": ("member", "admin", "owner"), "project": ("access",)}

    def __init__(self, url: str, api_key: str, http: Optional[Http] = None) -> None:
        self.http = http or Http(
            "dokploy", url.rstrip("/") + "/api", {"x-api-key": api_key}
        )

    def read(self) -> list[Grant]:
        grants: list[Grant] = []
        names = {p["projectId"]: p["name"] for p in self._projects()}

        for m in self._members():
            email = (m.get("user") or {}).get("email", "").lower()

            if not email:
                continue

            grants.append(Grant("dokploy", email, "org", m.get("role") or "member"))

            if m.get("role") == "member":
                for pid in m.get("accessedProjects") or []:
                    if pid in names:
                        grants.append(
                            Grant("dokploy", email, f"project/{names[pid]}", "access")
                        )

        for inv in self.http.call("GET", "organization.allInvitations") or []:
            if inv.get("status") == "pending" and inv.get("email"):
                grants.append(
                    Grant(
                        "dokploy",
                        inv["email"].lower(),
                        "org",
                        inv.get("role") or "member",
                    )
                )

        return self.strongest(grants)

    def apply(self, op: Op) -> None:
        g = op.grant
        kind, _, target = g.resource.partition("/")

        if kind == "org":
            self._org(op)
        elif kind == "project":
            self._project(g.account, target, op.action != "remove")
        else:
            raise AccessError(f"dokploy: cannot apply {g.resource}")

    def guard(self, ops: list[Op], live: list[Grant]) -> dict[Op, str]:
        owners = {g.account for g in live if g.resource == "org" and g.level == "owner"}

        return {
            op: f"dokploy: {op.grant.account} owns the instance; the owner is never changed here"
            for op in ops
            if op.grant.resource == "org"
            and (op.grant.account in owners or op.grant.level == "owner")
        }

    def _org(self, op: Op) -> None:
        g = op.grant

        if op.action == "add":
            self.http.call(
                "POST",
                "organization.inviteMember",
                {"email": g.account, "role": g.level},
            )
            return

        member = self._member(g.account)

        if member is None:
            invitation = self._invitation(g.account)

            if invitation is None or op.action != "remove":
                raise AccessError(
                    f"dokploy: {g.account} has not accepted the invitation yet"
                )

            self.http.call(
                "POST",
                "organization.removeInvitation",
                {"invitationId": invitation["id"]},
            )
        elif op.action == "change":
            self.http.call(
                "POST",
                "organization.updateMemberRole",
                {"memberId": member["id"], "role": g.level},
            )
        else:
            self.http.call("POST", "user.remove", {"userId": member["userId"]})

    def _project(self, email: str, name: str, on: bool) -> None:
        member = self._member(email)

        if member is None:
            raise AccessError(
                f"dokploy: {email} is not a member yet — the invitation has to be accepted first"
            )

        project = next((p for p in self._projects() if p["name"] == name), None)

        if project is None:
            raise AccessError(f"dokploy: no project named {name!r}")

        environments = {e["environmentId"] for e in project.get("environments") or []}
        body: dict[str, Any] = {"id": member["userId"]}
        body.update({flag: bool(member.get(flag)) for flag in FLAGS})
        body.update({key: list(member.get(key) or []) for key in LISTS})
        projects, envs = (
            set(body["accessedProjects"]),
            set(body["accessedEnvironments"]),
        )

        if on:
            projects.add(project["projectId"])
            envs |= environments
        else:
            projects.discard(project["projectId"])
            envs -= environments

        body["accessedProjects"], body["accessedEnvironments"] = (
            sorted(projects),
            sorted(envs),
        )
        self.http.call("POST", "user.assignPermissions", body)

    def _members(self) -> list[dict]:
        return list(self.http.call("GET", "user.all") or [])

    def _projects(self) -> list[dict]:
        return list(self.http.call("GET", "project.all") or [])

    def _member(self, email: str) -> Optional[dict]:
        return next(
            (
                m
                for m in self._members()
                if (m.get("user") or {}).get("email", "").lower() == email.lower()
            ),
            None,
        )

    def _invitation(self, email: str) -> Optional[dict]:
        return next(
            (
                i
                for i in self.http.call("GET", "organization.allInvitations") or []
                if i.get("status") == "pending"
                and (i.get("email") or "").lower() == email.lower()
            ),
            None,
        )
