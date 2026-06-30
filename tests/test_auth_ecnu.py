import io
import json
import os
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
from auth_ecnu.config import (
    default_config_path,
    load_auth_setting,
)
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

    def test_default_config_path_honours_xdg_config_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmpdir}):
                path = default_config_path()
        self.assertEqual(path, Path(tmpdir) / "auth_ecnu" / "setting")

    def test_load_auth_setting_prefers_xdg_over_legacy(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            xdg_root = Path(tmpdir) / "config"
            (xdg_root / "auth_ecnu").mkdir(parents=True)
            (xdg_root / "auth_ecnu" / "setting").write_text(
                'host="xdg.host"\nacid="9"\n', encoding="utf-8"
            )
            legacy_home = Path(tmpdir) / "home"
            legacy_home.mkdir()
            legacy_file = legacy_home / ".auth-setting"
            legacy_file.write_text('host="legacy.host"\nacid="1"\n', encoding="utf-8")

            env = {
                "XDG_CONFIG_HOME": str(xdg_root),
                "HOME": str(legacy_home),
            }
            with patch.dict(os.environ, env):
                with patch("auth_ecnu.config.LEGACY_CONFIG_PATH", legacy_file):
                    setting = load_auth_setting(None)

            self.assertEqual(setting.host, "xdg.host")
            self.assertEqual(setting.acid, 9)

    def test_banner_subcommand_emits_json_with_meta(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(["banner", "--json"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertIn("banner", payload)
        self.assertEqual(payload["meta"]["command"], "banner")

    def test_network_step_is_noop_in_json_mode(self) -> None:
        from auth_ecnu.render import network_step
        # JSON-mode context manager must not write anything and must not error.
        with redirect_stdout(io.StringIO()) as captured:
            with network_step("resolving challenge", "json"):
                pass
        self.assertEqual(captured.getvalue(), "")

    def test_quiet_mode_suppresses_all_output(self) -> None:
        class FakeClient:
            def check_online_status(self) -> OnlineStatus:
                return OnlineStatus(
                    online=True,
                    username="alice",
                    raw="alice,1,2,0,0,0,0,0,198.51.100.10,0",
                )

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("auth_ecnu.cli.make_client", return_value=FakeClient()):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main(["check", "--host", "portal.example", "--quiet"])

        self.assertEqual(rc, 0)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_quiet_mode_swallows_error_output_but_reports_via_exit_code(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = main(["check", "--config", "/nonexistent/path", "--quiet"])
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_quiet_mode_disables_debug_output_at_client_boundary(self) -> None:
        captured_debug: list[bool] = []

        class FakeSrunClient:
            def __init__(self, provider, *, timeout, debug):
                captured_debug.append(debug)

            def check_online_status(self) -> OnlineStatus:
                return OnlineStatus(online=True, username="alice")

        stdout = io.StringIO()
        stderr = io.StringIO()
        with patch("auth_ecnu.cli.SrunClient", FakeSrunClient):
            with redirect_stdout(stdout), redirect_stderr(stderr):
                rc = main(["check", "--host", "portal.example", "--quiet", "--debug"])

        self.assertEqual(rc, 0)
        self.assertEqual(captured_debug, [False])
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_online_status_derives_ip_from_raw(self) -> None:
        # Direct construction picks up ip via __post_init__.
        status = OnlineStatus(
            online=True,
            username="alice",
            raw="alice,1,2,0,0,0,0,0,198.51.100.10,0",
        )
        self.assertEqual(status.ip, "198.51.100.10")

        # from_portal_body parses everything from the wire body.
        parsed = OnlineStatus.from_portal_body("alice,1,2,0,0,0,0,0,198.51.100.10,0")
        self.assertTrue(parsed.online)
        self.assertEqual(parsed.username, "alice")
        self.assertEqual(parsed.ip, "198.51.100.10")

        offline = OnlineStatus.from_portal_body("not_online_error\n")
        self.assertFalse(offline.online)
        self.assertEqual(offline.ip, "")

    def test_render_auth_response_marks_decode_failure(self) -> None:
        from auth_ecnu.client import decode_jsonp_or_json
        from auth_ecnu.render import auth_response_payload, _decode_failed

        payload = auth_response_payload("garbage", decode_jsonp_or_json)
        self.assertTrue(_decode_failed(payload))
        self.assertEqual(payload["raw"], "garbage")

    def test_load_auth_setting_falls_back_to_legacy_when_xdg_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            xdg_root = Path(tmpdir) / "config"
            xdg_root.mkdir()  # no auth_ecnu/setting inside
            legacy_home = Path(tmpdir) / "home"
            legacy_home.mkdir()
            legacy_file = legacy_home / ".auth-setting"
            legacy_file.write_text('host="legacy.host"\nacid="1"\n', encoding="utf-8")

            env = {"XDG_CONFIG_HOME": str(xdg_root)}
            with patch.dict(os.environ, env):
                with patch("auth_ecnu.config.LEGACY_CONFIG_PATH", legacy_file):
                    setting = load_auth_setting(None)

            self.assertEqual(setting.host, "legacy.host")


if __name__ == "__main__":
    unittest.main()
