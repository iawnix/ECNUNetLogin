import io
import json
import tempfile
import unittest
from pathlib import Path
from contextlib import redirect_stdout, redirect_stderr
from unittest.mock import patch

from auth_ecnu import (
    AuthParams,
    OnlineStatus,
    PortalError,
    __version__,
    build_request_params,
    decode_jsonp_or_json,
    parse_setting_text,
)
from auth_ecnu.cli import main
from auth_ecnu.models import SrunUrlProvider


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
        # JSON envelope must carry meta so downstream scripts can branch on schema_version.
        self.assertEqual(payload["meta"]["tool"], "auth_ecnu")
        self.assertEqual(payload["meta"]["command"], "check")
        self.assertEqual(payload["meta"]["version"], __version__)
        self.assertEqual(payload["meta"]["schema_version"], 1)

    def test_status_alias_routes_to_check(self) -> None:
        class FakeClient:
            def check_online_status(self) -> OnlineStatus:
                return OnlineStatus(online=False, raw="not_online_error")

        stdout = io.StringIO()
        with patch("auth_ecnu.cli.make_client", return_value=FakeClient()):
            with redirect_stdout(stdout):
                rc = main(["status", "--host", "portal.example", "--json"])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertFalse(payload["online"])
        self.assertEqual(payload["meta"]["command"], "status")

    def test_parse_legacy_auth_setting(self) -> None:
        setting = parse_setting_text(
            "\n".join(
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
        self.assertEqual(setting.username, "")

    def test_parse_auth_setting_with_username(self) -> None:
        setting = parse_setting_text('username="alice"\nhost="10.0.0.1"\n')
        self.assertEqual(setting.username, "alice")
        self.assertEqual(setting.host, "10.0.0.1")

    def test_auth_preview_uses_config_and_prints_machine_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "auth-setting"
            config_path.write_text('acid="1"\nhost="172.20.20.11"\n', encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "auth",
                        "--config",
                        str(config_path),
                        "--username",
                        "alice",
                        "--password",
                        "secret",
                        "--token",
                        "abcdefghijklmnop",
                        "--preview",
                        "--output",
                        "json",
                    ]
                )

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["request"]["action"], "login")
        self.assertEqual(payload["request"]["ac_id"], "1")
        self.assertEqual(payload["meta"]["command"], "auth")

    def test_missing_host_emits_structured_error_to_stderr(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = main(["check", "--config", "/nonexistent/path", "--json"])

        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "usage_error")
        self.assertIn("host", payload["error"]["message"])
        self.assertEqual(payload["meta"]["command"], "check")

    def test_login_without_password_returns_usage_exit_code(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = main(["login", "--host", "portal.example", "--username", "alice", "--json"])
        self.assertEqual(rc, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "usage_error")

    def test_invalid_host_scheme_routes_to_usage_error(self) -> None:
        with self.assertRaises(ValueError):
            SrunUrlProvider.from_host("ftp://example.invalid")

        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = main(["check", "--host", "ftp://example.invalid", "--json"])
        self.assertEqual(rc, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "usage_error")

    def test_malformed_portal_json_raises_portal_error(self) -> None:
        with self.assertRaises(PortalError):
            decode_jsonp_or_json("not-json")

    def test_username_falls_back_to_config_file(self) -> None:
        class FakeClient:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def build_auth_request(self, **kwargs):
                self.calls.append(kwargs["username"])
                return {
                    "action": kwargs["action"],
                    "username": kwargs["username"],
                    "ac_id": "1",
                    "ip": "",
                    "chksum": "deadbeef",
                }

        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "auth-setting"
            config_path.write_text(
                'host="10.0.0.1"\nacid="1"\nusername="alice"\n', encoding="utf-8"
            )
            fake = FakeClient()
            stdout = io.StringIO()
            with patch("auth_ecnu.cli.make_client", return_value=fake):
                with redirect_stdout(stdout):
                    rc = main(
                        [
                            "auth",
                            "--config",
                            str(config_path),
                            "--password",
                            "secret",
                            "--token",
                            "abcdefghijklmnop",
                            "--preview",
                            "--json",
                        ]
                    )

        self.assertEqual(rc, 0)
        self.assertEqual(fake.calls, ["alice"])


if __name__ == "__main__":
    unittest.main()
