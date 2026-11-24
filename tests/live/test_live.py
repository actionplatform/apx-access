"""Against the real services, read only: set AP_ACCESS_LIVE=1 and the AP_ACCESS_* settings of the services to check. Nothing here changes a service."""

import os
import unittest

from apx_access.settings import configured, provider

LIVE = os.environ.get("AP_ACCESS_LIVE") == "1"


@unittest.skipUnless(LIVE, "AP_ACCESS_LIVE=1 and AP_ACCESS_* settings run this suite")
class LiveRead(unittest.TestCase):
    def test_every_configured_service_reads(self):
        services = configured()
        self.assertTrue(services, "no service configured")

        for service in services:
            with self.subTest(service=service):
                grants = provider(service).read()

                self.assertTrue(grants, f"{service} answered no grants at all")
                self.assertTrue(all(g.service == service for g in grants))
                self.assertEqual(len({g.key for g in grants}), len(grants))

                top = {
                    "github": "admin",
                    "jenkins": "admin",
                    "sentry": "owner",
                    "dokploy": "owner",
                }[service]
                first = "global" if service == "jenkins" else "org"
                self.assertTrue(
                    any(g.resource == first and g.level == top for g in grants),
                    f"{service}: no {top} found",
                )
