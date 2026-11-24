"""The four services and the platform in memory. Each fake answers only the routes and fields the real API sends, and keeps state, so a change shows up on the next read."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Optional

from apx_access.abc import Directory
from apx_access.http import Http, Response
from apx_access.spec import Mapping, Person


class FakeHttp(Http):
    def __init__(self, service: str, base: str) -> None:
        super().__init__(service, base, {})
        self.calls: list[tuple[str, str, Any]] = []

    def send(self, method, path, body=None, query=None, form=None) -> Response:
        url = urllib.parse.urlsplit(self.url(path, query))
        q = {k: v[0] for k, v in urllib.parse.parse_qs(url.query).items()}
        q.update({k: str(v) for k, v in (form or {}).items()})
        route = url.path.replace(urllib.parse.urlsplit(self.base).path, "", 1).strip(
            "/"
        )
        sent = json.loads(json.dumps(body)) if body is not None else None
        self.calls.append((method, route, sent if form is None else dict(form)))

        return self.handle(method, route, q, sent)

    def writes(self) -> list[tuple[str, str, Any]]:
        return [c for c in self.calls if c[0] != "GET"]

    def handle(self, method: str, route: str, q: dict, body: Any) -> Response:
        raise NotImplementedError


def _page(items: list, q: dict, size: Optional[int], url: str) -> Response:
    if size is None:
        return Response(200, items)

    start = int(q.get("cursor", "0"))
    chunk = items[start : start + size]
    headers = {}

    if start + size < len(items):
        headers["link"] = (
            f'<https://fake/next?cursor=0:0:1>; rel="previous"; results="false", '
            f'<{url}?cursor={start + size}>; rel="next"; results="true"; cursor="{start + size}"'
        )

    return Response(200, chunk, headers)


class FakeGitHub(FakeHttp):
    def __init__(self) -> None:
        super().__init__("github", "https://api.github.com")
        self.members: dict[str, str] = {}
        self.invited: dict[str, str] = {}
        self.teams: dict[str, dict] = {}
        self.repos: dict[str, dict[str, str]] = {}

    def handle(self, method, route, q, body):
        p = route.split("/")
        perm_names = {"pull": "read", "push": "write"}

        if p[:3] == ["orgs", "acme", "members"] and method == "GET":
            return Response(
                200, [{"login": u} for u, r in self.members.items() if r == q["role"]]
            )

        if p[:3] == ["orgs", "acme", "invitations"]:
            return Response(
                200,
                [
                    {"login": u, "role": "direct_member" if r == "member" else r}
                    for u, r in self.invited.items()
                ],
            )

        if p[:3] == ["orgs", "acme", "memberships"]:
            if method == "PUT":
                self.members[p[3]] = body["role"]
            else:
                self.members.pop(p[3], None)
            return Response(200, {})

        if route == "orgs/acme/teams" and method == "GET":
            return Response(200, [{"slug": s} for s in self.teams])

        if route == "orgs/acme/teams" and method == "POST":
            self.teams[body["name"]] = {"members": {}, "repos": {}}
            return Response(201, {"slug": body["name"]})

        if p[:2] == ["orgs", "acme"] and p[2] == "teams":
            team = self.teams.get(p[3])

            if team is None:
                return Response(404, {"message": "Not Found"})

            if len(p) == 4:
                return Response(200, {"slug": p[3]})

            if p[4] == "members":
                return Response(
                    200,
                    [
                        {"login": u}
                        for u, r in team["members"].items()
                        if r == q["role"]
                    ],
                )

            if p[4] == "memberships":
                if method == "PUT":
                    team["members"][p[5]] = body["role"]
                else:
                    team["members"].pop(p[5], None)
                return Response(200, {})

            if p[4] == "repos" and method == "GET":
                return Response(
                    200,
                    [
                        {"name": n, "role_name": perm_names.get(v, v)}
                        for n, v in team["repos"].items()
                    ],
                )

            if p[4] == "repos":
                if method == "PUT":
                    team["repos"][p[6]] = body["permission"]
                else:
                    team["repos"].pop(p[6], None)
                return Response(204, None)

        if route == "orgs/acme/repos":
            return Response(200, [{"name": n} for n in self.repos])

        if p[0] == "repos" and p[3] == "collaborators":
            repo = self.repos[p[2]]

            if method == "GET":
                return Response(
                    200,
                    [
                        {"login": u, "role_name": perm_names.get(v, v)}
                        for u, v in repo.items()
                    ],
                )

            if method == "PUT":
                repo[p[4]] = body["permission"]
            else:
                repo.pop(p[4], None)
            return Response(201, {})

        if p[0] == "repos" and p[3] == "invitations":
            return Response(200, [])

        return Response(404, {"message": f"no route {method} {route}"})


class FakeJenkins(FakeHttp):
    def __init__(self, active: bool = True, legacy: bool = False) -> None:
        super().__init__("jenkins", "https://jenkins.example.com")
        self.active = active
        self.legacy = legacy
        self.roles: dict[str, dict[str, dict]] = {"globalRoles": {}, "projectRoles": {}}

    def role(
        self,
        kind: str,
        name: str,
        permissions: list[str],
        sids: list[str],
        pattern: str = ".*",
    ) -> None:
        self.roles[kind][name] = {
            "permissions": permissions,
            "pattern": pattern,
            "sids": list(sids),
        }

    def handle(self, method, route, q, body):
        if not self.active:
            return Response(404, "Not Found")

        verb = route.rsplit("/", 1)[-1]
        roles = self.roles[q["type"]]

        if verb == "getAllRoles":
            if self.legacy:
                return Response(200, {n: list(r["sids"]) for n, r in roles.items()})

            return Response(
                200,
                {
                    n: [{"type": "USER", "sid": s} for s in r["sids"]]
                    for n, r in roles.items()
                },
            )

        if verb == "getRole":
            r = roles.get(q["roleName"])

            if r is None:
                return Response(200, {})

            return Response(
                200,
                {
                    "permissionIds": {p: True for p in r["permissions"]},
                    "pattern": r["pattern"],
                    "sids": r["sids"],
                },
            )

        if verb == "addRole":
            roles.setdefault(
                q["roleName"],
                {
                    "permissions": q["permissionIds"].split(","),
                    "pattern": q.get("pattern", ".*"),
                    "sids": [],
                },
            )
            return Response(200, None)

        if verb in ("assignUserRole", "unassignUserRole"):
            if q["roleName"] not in roles:
                return Response(400, "no such role")

            sids = roles[q["roleName"]]["sids"]

            if verb.startswith("assign") and q["user"] not in sids:
                sids.append(q["user"])
            elif verb.startswith("unassign") and q["user"] in sids:
                sids.remove(q["user"])
            return Response(200, None)

        return Response(404, "Not Found")


class FakeSentry(FakeHttp):
    """The member list carries no teams; team membership and team role come from each team's member list, as on sentry.io."""

    def __init__(self, page: int = 1) -> None:
        super().__init__("sentry", "https://sentry.io")
        self.page = page
        self.members: list[dict] = []
        self.teams: dict[str, dict[str, Optional[str]]] = {}
        self.next_id = 100

    def add(
        self, email: str, role: str, teams: dict[str, Optional[str]] | None = None
    ) -> None:
        self.next_id += 1
        member = {
            "id": str(self.next_id),
            "email": email,
            "orgRole": role,
            "role": role,
            "pending": False,
        }
        self.members.append(member)

        for slug, team_role in (teams or {}).items():
            self.teams.setdefault(slug, {})[member["id"]] = team_role

    def handle(self, method, route, q, body):
        p = route.split("/")
        base = ["api", "0", "organizations", "acme", "members"]

        if p == ["api", "0", "organizations", "acme", "teams"]:
            return _page(
                [{"slug": s} for s in self.teams], q, self.page, self.url(route)
            )

        if p[:4] == ["api", "0", "teams", "acme"] and p[5] == "members":
            rows = [
                {**m, "teamRole": self.teams[p[4]][m["id"]], "teamSlug": p[4]}
                for m in self.members
                if m["id"] in self.teams.get(p[4], {})
            ]
            return _page(rows, q, self.page, self.url(route))

        if p == base and method == "GET":
            return _page(self.members, q, self.page, self.url(route))

        if p == base and method == "POST":
            self.add(body["email"], body["orgRole"])
            self.members[-1]["pending"] = True
            return Response(201, {"id": self.members[-1]["id"], "email": body["email"]})

        member = next((m for m in self.members if p[:6] == base + [m["id"]]), None)

        if member is None:
            return Response(404, {"detail": "The requested resource does not exist"})

        if len(p) == 6 and method == "PUT":
            member["orgRole"] = member["role"] = body["orgRole"]
            return Response(200, member)

        if len(p) == 6 and method == "DELETE":
            self.members.remove(member)

            for team in self.teams.values():
                team.pop(member["id"], None)
            return Response(204, None)

        team = self.teams.get(p[7])

        if team is None:
            return Response(404, {"detail": "The requested resource does not exist"})

        if method == "POST":
            team.setdefault(member["id"], None)
            return Response(201, {})

        if method == "PUT":
            team[member["id"]] = body["teamRole"]
            return Response(200, {})

        team.pop(member["id"], None)
        return Response(204, None)


class FakeDokploy(FakeHttp):
    def __init__(self) -> None:
        super().__init__("dokploy", "https://dokploy.example.com/api")
        self.members: list[dict] = []
        self.projects: list[dict] = []
        self.invitations: list[dict] = []

    def member(self, email: str, role: str, projects: list[str] | None = None) -> dict:
        n = len(self.members) + 1
        row = {
            "id": f"m{n}",
            "userId": f"u{n}",
            "role": role,
            "user": {"id": f"u{n}", "email": email},
            "accessedProjects": list(projects or []),
            "accessedEnvironments": [],
            "accessedServices": [],
            "accessedGitProviders": [],
            "accessedServers": [],
            "canCreateProjects": False,
            "canAccessToDocker": False,
        }
        self.members.append(row)

        return row

    def project(self, name: str) -> dict:
        n = len(self.projects) + 1
        row = {
            "projectId": f"p{n}",
            "name": name,
            "environments": [{"environmentId": f"e{n}", "name": "production"}],
        }
        self.projects.append(row)

        return row

    def handle(self, method, route, q, body):
        if route == "user.all":
            return Response(200, self.members)

        if route == "project.all":
            return Response(200, self.projects)

        if route == "organization.allInvitations":
            return Response(200, self.invitations)

        if route == "organization.inviteMember":
            self.invitations.append(
                {
                    "id": f"i{len(self.invitations) + 1}",
                    "email": body["email"],
                    "role": body["role"],
                    "status": "pending",
                }
            )
            return Response(200, {})

        if route == "organization.removeInvitation":
            self.invitations = [
                i for i in self.invitations if i["id"] != body["invitationId"]
            ]
            return Response(200, {})

        if route == "organization.updateMemberRole":
            next(m for m in self.members if m["id"] == body["memberId"])["role"] = body[
                "role"
            ]
            return Response(200, {})

        if route == "user.remove":
            self.members = [m for m in self.members if m["userId"] != body["userId"]]
            return Response(200, True)

        if route == "user.assignPermissions":
            m = next(m for m in self.members if m["userId"] == body["id"])
            m.update({k: v for k, v in body.items() if k != "id"})
            return Response(200, None)

        return Response(404, {"message": "not found"})


class FakeDirectory(Directory):
    def __init__(self, people: list[Person], mapping: Optional[Mapping] = None) -> None:
        self.members = list(people)
        self.mapping = mapping or Mapping()
        self.saved = 0
        self.removed: list[str] = []

    def people(self) -> list[Person]:
        return list(self.members)

    def load(self) -> Mapping:
        return Mapping.of(self.mapping.as_dict())

    def save(self, mapping: Mapping) -> None:
        self.mapping = Mapping.of(mapping.as_dict())
        self.saved += 1

    def remove(self, person: Person) -> None:
        self.removed.append(person.email)
        self.members = [p for p in self.members if p.email != person.email]
