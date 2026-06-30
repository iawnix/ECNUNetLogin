import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout
from unittest.mock import patch

from auth_ecnu import AuthParams, OnlineStatus, build_request_params, parse_setting_text
from auth_ecnu.cli import main


class AuthEcnuTests(unittest.TestCase):
    def test_build_request_login_contains_signed_fields(self) -> None:
        request = build_request_params(
            AuthParams(
                username="alice",
                password="secret",
                token="abcdefghijklmnop",
                action="login",
                ip="192.0.2.10",
                acid=1,
            )
        )

        self.assertEqual(request["action"], "login")
        self.assertEqual(request["ac_id"], "1")
        self.assertEqual(request["username"], "alice")
        self.assertEqual(request["password"], "{MD5}5ebe2294ecd0e0f08eab7690d2a6ee69")
        self.assertTrue(request["info"].startswith("{SRBX1}"))
        self.assertRegex(request["chksum"], r"^[0-9a-f]{40}$")

    def test_build_subcommand_prints_json(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(
                [
                    "build",
                    "--action",
                    "logout",
                    "--username",
                    "alice",
                    "--token",
                    "abcdefghijklmnop",
                    "--ip",
                    "192.0.2.10",
                    "--acid",
                    "1",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["action"], "logout")
        self.assertNotIn("password", payload)

    def test_build_subcommand_output_json_prints_machine_payload(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(
                [
                    "build",
                    "--action",
                    "logout",
                    "--username",
                    "alice",
                    "--token",
                    "abcdefghijklmnop",
                    "--ip",
                    "192.0.2.10",
                    "--acid",
                    "1",
                    "--output",
                    "json",
                ]
            )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["request"]["action"], "logout")
        self.assertIn("query", payload)

    def test_check_subcommand_output_json_includes_parsed_ip(self) -> None:
        class FakeClient:
            def check_online_status(self) -> OnlineStatus:
                return OnlineStatus(
                    online=True,
                    username="alice",
                    raw="alice,1,2,0,0,0,0,0,198.51.100.10,0",
                )

        stdout = io.StringIO()
        with patch("auth_ecnu.cli.make_client", return_value=FakeClient()):
            with redirect_stdout(stdout):
                rc = main(["check", "--host", "portal.example", "--output", "json"])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["username"], "alice")
        self.assertEqual(payload["ip"], "198.51.100.10")

    def test_parse_legacy_auth_setting(self) -> None:
        setting = parse_setting_text(
            '\n'.join(
                [
                    'campus_url=""',
                    'acid="1"',
                    'host="172.20.20.11"',
                    'campus_postfix=""',
                ]
            )
        )

        self.assertEqual(setting.host, "172.20.20.11")
        self.assertEqual(setting.acid, 1)
        self.assertEqual(setting.campus_postfix, "")

    def test_build_uses_acid_from_config(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "auth-setting"
            config_path.write_text('acid="1"\nhost="172.20.20.11"\n', encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "build",
                        "--config",
                        str(config_path),
                        "--action",
                        "logout",
                        "--username",
                        "alice",
                        "--token",
                        "abcdefghijklmnop",
                        "--output",
                        "json",
                    ]
                )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["request"]["ac_id"], "1")

    def test_legacy_auth_command_uses_config_for_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "auth-setting"
            config_path.write_text('acid="1"\nhost="172.20.20.11"\n', encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "--config",
                        str(config_path),
                        "--username",
                        "alice",
                        "--password",
                        "secret",
                        "--token",
                        "abcdefghijklmnop",
                        "--dry-run",
                        "--format",
                        "json",
                        "auth",
                    ]
                )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["action"], "login")
        self.assertEqual(payload["ac_id"], "1")
        self.assertEqual(payload["callback"], "C_a_l_l_b_a_c_k")

    def test_legacy_offline_entrypoint_still_builds_request(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(
                [
                    "--username",
                    "alice",
                    "--password",
                    "secret",
                    "--token",
                    "abcdefghijklmnop",
                    "--ip",
                    "192.0.2.10",
                    "--acid",
                    "1",
                    "--format",
                    "json",
                ]
            )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["action"], "login")
        self.assertEqual(payload["username"], "alice")


if __name__ == "__main__":
    unittest.main()
