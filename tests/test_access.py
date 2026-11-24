import unittest

from apx_access.abc import AccessError
from apx_access.providers.dokploy import DokployProvider
from apx_access.providers.github import GitHubProvider
from apx_access.providers.jenkins import JenkinsProvider, folder_pattern
from apx_access.providers.sentry import SentryProvider
from apx_access.service import Access
from apx_access.spec import Grant, Mapping, Op, Person, spec
from tests.fake import FakeDirectory, FakeDokploy, FakeGitHub, FakeJenkins, FakeSentry

ANA = Person("ana@acme.dev", "u-ana", "Ana", "owner", ("platform",))
BEN = Person("ben@acme.dev", "u-ben", "Ben", "developer", ("backend",))


class World(unittest.TestCase):
    def setUp(self):
        self.github = FakeGitHub()
        self.github.members = {"ana": "admin", "ben": "member", "acme-bot": "admin"}
        self.github.teams = {
            "core": {"members": {"ana": "maintainer"}, "repos": {"api": "push"}}
        }
        self.github.repos = {"api": {"ben": "push"}, "site": {}}

        self.jenkins = FakeJenkins()
        self.jenkins.role(
            "globalRoles", "admin", ["hudson.model.Hudson.Administer"], ["ana"]
        )

        self.sentry = FakeSentry(page=1)
        self.sentry.add("ana@acme.dev", "owner", {"web": "admin"})
        self.sentry.add("ben@acme.dev", "member", {"web": None})
        self.sentry.add("old@agency.dev", "member")

        self.dokploy = FakeDokploy()
        api = self.dokploy.project("api")
        self.dokploy.project("site")
        self.dokploy.member("ana@acme.dev", "owner")
        self.dokploy.member("ben@acme.dev", "member", [api["projectId"]])

        self.directory = FakeDirectory([ANA, BEN])
        self.access = Access(
            self.directory,
            {
                "github": GitHubProvider("acme", "t", http=self.github),
                "jenkins": JenkinsProvider(
                    "https://jenkins.example.com", "u", "t", http=self.jenkins
                ),
                "sentry": SentryProvider("acme", "t", http=self.sentry),
                "dokploy": DokployProvider(
                    "https://dokploy.example.com", "k", http=self.dokploy
                ),
            },
        )
        self.links = {
            "ana@acme.dev": {"github": "ana", "jenkins": "ana"},
            "ben@acme.dev": {"github": "ben"},
        }

    def writes(self):
        return sum(
            len(f.writes())
            for f in (self.github, self.jenkins, self.sentry, self.dokploy)
        )

    def bootstrapped(self):
        self.access.sync(apply=True, links=self.links)


class FirstSync(World):
    def test_first_sync_imports_and_changes_nothing(self):
        plan = self.access.sync(apply=True)

        self.assertTrue(plan.bootstrap)
        self.assertEqual(plan.changes, [])
        self.assertEqual(self.writes(), 0)
        self.assertEqual(
            sorted(self.directory.mapping.imported),
            ["dokploy", "github", "jenkins", "sentry"],
        )

        again = self.access.sync()

        self.assertFalse(again.bootstrap)
        self.assertEqual(again.changes, [])

    def test_dry_run_bootstrap_stores_nothing(self):
        plan = self.access.sync()

        self.assertTrue(plan.bootstrap and plan.dry_run)
        self.assertEqual(self.directory.saved, 0)
        self.assertIn("people", plan.mapping)

    def test_emails_link_themselves_and_outsiders_are_kept(self):
        self.bootstrapped()
        m = self.directory.mapping

        self.assertEqual(m.people["ben@acme.dev"]["sentry"], "ben@acme.dev")
        self.assertEqual(m.people["ana@acme.dev"]["dokploy"], "ana@acme.dev")
        kept = {(r["service"], r["account"]) for r in m.keep}
        self.assertIn(("github", "acme-bot"), kept)
        self.assertIn(("github", "team:core"), kept)
        self.assertIn(("sentry", "old@agency.dev"), kept)
        self.assertIn(spec("github", "repo/api", "push"), m.grants["ben@acme.dev"])

    def test_audit_after_bootstrap_shows_no_drift(self):
        self.bootstrapped()
        audit = self.access.audit()

        self.assertEqual(audit.imported, ["dokploy", "github", "jenkins", "sentry"])
        self.assertTrue(all(s.ok and not s.drift for s in audit.services))
        github = next(s for s in audit.services if s.service == "github")
        self.assertEqual(github.outside_accounts, ["acme-bot", "team:core"])


class Changes(World):
    def test_grant_touches_only_that_person(self):
        self.bootstrapped()
        self.github.members["stranger"] = "member"

        plan = self.access.grant(
            "ben@acme.dev", "github", "repo/site", "pull", apply=True
        )

        self.assertEqual(
            [(c.action, c.account, c.resource, c.status) for c in plan.changes],
            [("add", "ben", "repo/site", "applied")],
        )
        self.assertEqual(self.github.repos["site"], {"ben": "pull"})
        self.assertIn("stranger", self.github.members)
        self.assertIn(
            spec("github", "repo/site", "pull"),
            self.directory.mapping.grants["ben@acme.dev"],
        )

    def test_grant_dry_run_writes_nothing(self):
        self.bootstrapped()
        before = self.writes()

        plan = self.access.grant("ben@acme.dev", "sentry", "team/web", "admin")

        self.assertEqual(plan.changes[0].action, "change")
        self.assertEqual(self.writes(), before)

    def test_grant_refuses_unknown_levels(self):
        self.bootstrapped()

        with self.assertRaisesRegex(AccessError, "takes read, build, configure"):
            self.access.grant("ben@acme.dev", "jenkins", "folder/api", "owner")

    def test_grant_needs_an_account(self):
        self.bootstrapped()

        with self.assertRaisesRegex(AccessError, "no jenkins account"):
            self.access.grant("ben@acme.dev", "jenkins", "folder/api", "build")

    def test_jenkins_folder_grant_creates_the_role_and_global_read(self):
        self.bootstrapped()

        plan = self.access.grant(
            "ben@acme.dev", "jenkins", "folder/api", "build", account="ben", apply=True
        )

        self.assertEqual(
            {(c.resource, c.level) for c in plan.changes},
            {("folder/api", "build"), ("global", "read")},
        )
        role = self.jenkins.roles["projectRoles"]["folder:api:build"]
        self.assertEqual(role["pattern"], folder_pattern("api"))
        self.assertIn("hudson.model.Item.Build", role["permissions"])
        self.assertEqual(self.jenkins.roles["globalRoles"]["read"]["sids"], ["ben"])

    def test_revoke_removes_and_names_what_remains(self):
        self.bootstrapped()
        self.directory.mapping.teams["backend"] = [
            spec("dokploy", "project/api", "access")
        ]

        plan = self.access.revoke("ben@acme.dev", "github", "repo/api", apply=True)

        self.assertEqual(self.github.repos["api"], {})
        self.assertEqual(plan.changes[0].action, "remove")

        inherited = self.access.revoke("ben@acme.dev", "dokploy", "project/api")
        self.assertIn("team:backend", inherited.note)

    def test_offboard_removes_every_account(self):
        self.bootstrapped()

        plan = self.access.offboard(
            "ben@acme.dev", apply=True, remove_from_platform=True
        )

        self.assertTrue(all(c.status == "applied" for c in plan.changes))
        self.assertNotIn("ben", self.github.members)
        self.assertEqual(self.github.repos["api"], {})
        self.assertNotIn("ben@acme.dev", [m["email"] for m in self.sentry.members])
        self.assertNotIn(
            "ben@acme.dev", [m["user"]["email"] for m in self.dokploy.members]
        )
        self.assertNotIn("ben@acme.dev", self.directory.mapping.people)
        self.assertEqual(self.directory.removed, ["ben@acme.dev"])
        self.assertEqual(self.access.sync().changes, [])

    def test_offboard_never_removes_the_last_admin(self):
        self.github.members = {"ana": "admin", "ben": "member"}
        self.bootstrapped()

        plan = self.access.offboard("ana@acme.dev", apply=True)
        refused = {
            (c.service, c.resource) for c in plan.changes if c.status == "refused"
        }

        self.assertIn(("github", "org"), refused)
        self.assertIn(("jenkins", "global"), refused)
        self.assertIn(("sentry", "org"), refused)
        self.assertIn(("dokploy", "org"), refused)
        self.assertEqual(self.github.members["ana"], "admin")

    def test_team_policy_drives_sync(self):
        self.bootstrapped()
        self.directory.mapping.people["ben@acme.dev"]["jenkins"] = "ben"
        self.directory.mapping.teams["backend"] = [
            spec("github", "team/backend", "member"),
            spec("jenkins", "folder/api", "read"),
            spec("jenkins", "global", "read"),
        ]

        plan = self.access.sync(apply=True)

        self.assertEqual(
            sorted((c.service, c.resource) for c in plan.changes),
            [
                ("github", "team/backend"),
                ("jenkins", "folder/api"),
                ("jenkins", "global"),
            ],
        )
        self.assertEqual(self.github.teams["backend"]["members"], {"ben": "member"})
        self.assertEqual(self.access.sync().changes, [])

    def test_leaving_the_organization_is_drift(self):
        self.bootstrapped()
        self.directory.members = [ANA]

        drift = {
            (c.service, c.account, c.action)
            for s in self.access.audit().services
            for c in s.drift
        }

        self.assertIn(("github", "ben", "remove"), drift)
        self.assertIn(("sentry", "ben@acme.dev", "remove"), drift)
        self.assertIn(("dokploy", "ben@acme.dev", "remove"), drift)

    def test_who_by_person_and_by_service(self):
        self.bootstrapped()

        ben = self.access.who("ben@acme.dev")
        self.assertEqual(ben.person.accounts["github"], "ben")
        self.assertIn(
            ("dokploy", "project/api"), {(g.service, g.resource) for g in ben.grants}
        )

        github = self.access.who(service="github")
        bot = next(g for g in github.grants if g.account == "acme-bot")
        self.assertEqual(bot.source, "kept")
        self.assertIsNone(bot.person)

    def test_operations_before_bootstrap_are_refused(self):
        with self.assertRaisesRegex(AccessError, "run access_sync first"):
            self.access.grant("ben@acme.dev", "github", "repo/api", "pull")


class Review(World):
    def test_a_service_that_failed_is_imported_later_not_emptied(self):
        down = self.access.providers.pop("sentry")
        self.access.sync(apply=True, links=self.links)
        self.access.providers["sentry"] = down

        plan = self.access.sync(apply=True)

        self.assertEqual(plan.imported, ["sentry"])
        self.assertEqual(plan.changes, [])
        self.assertIn("old@agency.dev", [m["email"] for m in self.sentry.members])
        self.assertEqual(self.access.sync().changes, [])

    def test_accounts_match_whatever_the_case(self):
        self.access.sync(apply=True, links={"ana@acme.dev": {"github": "ANA"}})

        self.assertEqual(self.directory.mapping.people["ana@acme.dev"]["github"], "ana")
        self.directory.mapping.people["ana@acme.dev"]["github"] = "Ana"

        self.assertEqual(self.access.sync().changes, [])

    def test_a_team_grant_brings_organization_membership(self):
        self.bootstrapped()
        self.directory.members.append(
            Person("cy@acme.dev", "u-cy", "Cy", "developer", ("backend",))
        )
        self.directory.mapping.people["cy@acme.dev"] = {"github": "cy"}
        self.directory.mapping.teams["backend"] = [
            spec("github", "team/backend", "member")
        ]

        self.access.sync(apply=True)

        self.assertEqual(self.github.members["cy"], "member")
        self.assertEqual(self.access.sync().changes, [])

    def test_folder_read_through_a_group_is_left_alone(self):
        self.jenkins.role("projectRoles", "folder:api:build", [], ["ben"])
        self.links["ben@acme.dev"]["jenkins"] = "ben"
        self.bootstrapped()

        self.assertEqual(self.access.sync().changes, [])

    def test_expired_dokploy_invitations_are_not_access(self):
        self.dokploy.invitations = [
            {
                "id": "i1",
                "email": "late@acme.dev",
                "role": "member",
                "status": "pending",
                "expiresAt": "2020-01-01T00:00:00.000Z",
            },
            {
                "id": "i2",
                "email": "soon@acme.dev",
                "role": "member",
                "status": "pending",
                "expiresAt": "2999-01-01T00:00:00.000Z",
            },
        ]

        accounts = {g.account for g in self.access.providers["dokploy"].read()}

        self.assertNotIn("late@acme.dev", accounts)
        self.assertIn("soon@acme.dev", accounts)

        self.access.providers["dokploy"].apply(
            Op("add", Grant("dokploy", "late@acme.dev", "org", "member"))
        )
        self.assertEqual(
            [i["email"] for i in self.dokploy.invitations],
            ["soon@acme.dev", "late@acme.dev"],
        )

    def test_dokploy_admins_need_no_project_grants(self):
        self.bootstrapped()
        self.directory.mapping.roles["owner"] = [
            spec("dokploy", "project/site", "access")
        ]

        self.assertEqual(self.access.sync().changes, [])


class Providers(unittest.TestCase):
    def test_jenkins_without_role_strategy_says_what_to_install(self):
        with self.assertRaisesRegex(AccessError, "role-strategy"):
            JenkinsProvider(
                "https://j", "u", "t", http=FakeJenkins(active=False)
            ).read()

    def test_jenkins_reads_the_legacy_sid_list(self):
        fake = FakeJenkins(legacy=True)
        fake.role("globalRoles", "admin", [], ["ana"])
        fake.role("projectRoles", "folder:api:build", [], ["ben"])
        fake.role("projectRoles", "deployers", [], ["ci"])

        grants = JenkinsProvider("https://j", "u", "t", http=fake).read()

        self.assertEqual(
            grants,
            sorted(
                [
                    Grant("jenkins", "ana", "global", "admin"),
                    Grant("jenkins", "ben", "folder/api", "build"),
                    Grant("jenkins", "ci", "item-role/deployers", "assigned"),
                ]
            ),
        )

    def test_sentry_follows_every_page(self):
        fake = FakeSentry(page=1)

        for n in range(3):
            fake.add(f"p{n}@acme.dev", "member")

        grants = SentryProvider("acme", "t", http=fake).read()

        self.assertEqual(len(grants), 3)
        member_pages = [c for c in fake.calls if c[1].endswith("acme/members")]
        self.assertEqual(len(member_pages), 3)

    def test_dokploy_project_access_keeps_the_other_permissions(self):
        fake = FakeDokploy()
        api = fake.project("api")
        fake.member("ben@acme.dev", "member")["canAccessToDocker"] = True
        provider = DokployProvider("https://d", "k", http=fake)

        provider.apply(
            Op("add", Grant("dokploy", "ben@acme.dev", "project/api", "access"))
        )

        sent = fake.writes()[0][2]
        self.assertEqual(sent["accessedProjects"], [api["projectId"]])
        self.assertEqual(sent["accessedEnvironments"], ["e1"])
        self.assertTrue(sent["canAccessToDocker"])

    def test_github_reads_team_repositories_as_team_accounts(self):
        fake = FakeGitHub()
        fake.teams = {"core": {"members": {}, "repos": {"api": "pull"}}}

        grants = GitHubProvider("acme", "t", http=fake).read()

        self.assertEqual(grants, [Grant("github", "team:core", "repo/api", "pull")])


class Mappings(unittest.TestCase):
    def test_round_trip(self):
        m = Mapping(
            people={"a@x": {"github": "a"}},
            keep=[Grant("github", "b", "org", "member").as_dict()],
            imported={"github": "t"},
        )

        self.assertEqual(Mapping.of(m.as_dict()), m)
        self.assertEqual(m.owner_of("github", "A"), "a@x")
        self.assertEqual(Mapping.of(None), Mapping())
