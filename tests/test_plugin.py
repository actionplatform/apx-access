import asyncio
import os
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from action_platform.plugins import Loaded, Plugins, PluginState, registry

from apx_access import AccessPlugin
from apx_access.abc import AccessError
from apx_access.settings import configured, connect, provider

TOOLS = {
    "access_who",
    "access_audit",
    "access_grant",
    "access_revoke",
    "access_offboard",
    "access_sync",
}


class PluginTest(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.plugins = Plugins(
            [Loaded(AccessPlugin(), "apx-access", "0.1.0")],
            PluginState(file=Path(self.tmp.name) / "plugins.json"),
        )
        registry._current = self.plugins
        self.addCleanup(registry.reset)

    def tools(self):
        from action_platform.mcp import server

        mcp = server.build()

        return mcp, {t.name: t for t in asyncio.run(mcp.list_tools())}

    def test_every_tool_is_registered_with_schemas(self):
        _, tools = self.tools()

        self.assertTrue(TOOLS <= set(tools))

        for name in TOOLS:
            self.assertTrue(tools[name].output_schema, name)

        self.assertFalse(
            tools["access_sync"].input_schema["properties"]["apply"]["default"]
        )

    def test_a_disabled_plugin_refuses(self):
        mcp, _ = self.tools()
        self.plugins.disable("access")

        with self.assertRaisesRegex(Exception, "plugin access is disabled"):
            asyncio.run(mcp.call_tool("access_audit", {}))

    def test_nothing_configured_says_what_to_set(self):
        with mock.patch.dict(os.environ, {"AP_HOME": self.tmp.name}, clear=False):
            with self.assertRaisesRegex(AccessError, "AP_ACCESS_GITHUB_ORG"):
                connect()

    def test_a_missing_credential_is_named(self):
        env = {"AP_HOME": self.tmp.name, "AP_ACCESS_JENKINS_URL": "https://j"}

        with mock.patch.dict(os.environ, env, clear=False):
            self.assertEqual(configured(), ["jenkins"])

            with self.assertRaisesRegex(
                AccessError, "AP_ACCESS_JENKINS_USER, AP_ACCESS_JENKINS_TOKEN"
            ):
                provider("jenkins")

    def test_options_declare_secrets_as_secret(self):
        kinds = {o.key: o.kind for o in AccessPlugin.options}

        for key in ("github_token", "jenkins_token", "sentry_token", "dokploy_api_key"):
            self.assertEqual(kinds[key], "secret")
