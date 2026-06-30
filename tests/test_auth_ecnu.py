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
    def test_protocol_worked_example_matches_spec(self) -> None:
        """Lock down the worked example from docs/protocol.md.

        Any change to xencode / quirk_base64_encode / build_request_params
        that breaks this test means the wire format moved. Either revert
        the change or update docs/protocol.md so the spec and the code
        stay in sync.
        """
        from auth_ecnu.protocol import quirk_base64_encode, xencode

        info_json = (
            '{"acid":"1","enc_ver":"srun_bx1","ip":"192.0.2.10",'
            '"password":"secret","username":"alice"}'
        )
        token = "abcdefghijklmnop"

        expected_xencode = (
            "7954a04f4b8dac2a85c30ca65171156bb20dd038d527e4685e8cf0d9dcae7468"
            "d1c7430df3429e03933f103b65c1fdffae828787d04d8cac1ddb0c197bb3bd56"
            "273520489c5eab9c42266a1eb0c11ceecfbae42b90a078f13d743a60a3ff936a"
        )
        expected_info_b64 = (
            "rumSFtK0lodivvxUHcPuOE20tJkuRQh/c/zvInxKnCkh6t904t8rLe9APJfpvs7A"
            "l/8NT5V0k8vnIvv1rEy5uXMj2PXMcdKM+X1dNlJVNyEgKK+lY8VD4FjtyUokAe0d"
        )
        expected_chksum = "31788c4f2352942da2b506e9a1015569416f5744"
        expected_password = "{MD5}5ebe2294ecd0e0f08eab7690d2a6ee69"

        encoded = xencode(info_json, token)
        self.assertEqual(encoded.hex(), expected_xencode,
                         "xencode output changed — diff against docs/protocol.md")
        self.assertEqual(quirk_base64_encode(encoded), expected_info_b64,
                         "quirk_base64_encode output changed — diff against docs/protocol.md")

        request = build_request_params(AuthParams(
            username="alice", password="secret", token=token,
            action="login", ip="192.0.2.10", acid=1,
        ))
        self.assertEqual(request["chksum"], expected_chksum,
                         "chksum field order or hashing changed — diff against docs/protocol.md")
        self.assertEqual(request["info"], "{SRBX1}" + expected_info_b64)
        self.assertEqual(request["password"], expected_password)

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

    def test_parse_auth_setting(self) -> None:
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

    def test_parse_setting_silently_ignores_username_key(self) -> None:
        # The config file must not store credentials. ``username`` is no
        # longer a recognised key — it parses without error but does not
        # populate any AuthSetting field.
        setting = parse_setting_text('username="alice"\nhost="10.0.0.1"\n')
        self.assertEqual(setting.host, "10.0.0.1")
        self.assertFalse(hasattr(setting, "username"))

    def test_auth_preview_uses_config_and_prints_machine_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "auth-setting"
            config_path.write_text('acid="1"\nhost="172.20.20.11"\n', encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(
                    [
                        "login",
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
        self.assertEqual(payload["meta"]["command"], "login")

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

    def test_default_config_path_honours_xdg_config_home(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmpdir}):
                path = default_config_path()
        self.assertEqual(path, Path(tmpdir) / "auth_ecnu" / "setting")

    def test_legacy_auth_setting_is_not_read(self) -> None:
        # ~/.auth-setting is no longer a fallback. A file at that path
        # must not affect config loading.
        with tempfile.TemporaryDirectory() as tmpdir:
            xdg_root = Path(tmpdir) / "config"
            xdg_root.mkdir()  # empty — no auth_ecnu/setting
            legacy_home = Path(tmpdir) / "home"
            legacy_home.mkdir()
            (legacy_home / ".auth-setting").write_text(
                'host="legacy.host"\nacid="7"\n', encoding="utf-8"
            )

            env = {"XDG_CONFIG_HOME": str(xdg_root), "HOME": str(legacy_home)}
            with patch.dict(os.environ, env):
                setting = load_auth_setting(None)
            self.assertEqual(setting.host, "")
            self.assertIsNone(setting.acid)

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

    def test_in_json_top_level_dispatches_via_action_field(self) -> None:
        class FakeClient:
            def check_online_status(self) -> OnlineStatus:
                return OnlineStatus(
                    online=True, username="alice",
                    raw="alice,1,2,0,0,0,0,0,1.2.3.4,0",
                )

        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({
                "schema_version": 1,
                "action": "check",
                "host": "portal.example",
                "output": "json",
            }), encoding="utf-8")

            stdout = io.StringIO()
            with patch("auth_ecnu.cli.make_client", return_value=FakeClient()):
                with redirect_stdout(stdout):
                    rc = main(["--in-json", str(in_json)])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["meta"]["command"], "check")
        self.assertEqual(payload["username"], "alice")

    def test_in_json_fills_params_under_explicit_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({
                "schema_version": 1,
                "host": "172.20.20.11",
                "acid": 1,
                "username": "alice",
                "password": "secret",
                "token": "abcdefghijklmnop",
                "preview": True,
                "output": "json",
            }), encoding="utf-8")

            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main(["login", "--in-json", str(in_json)])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["request"]["username"], "alice")
        self.assertEqual(payload["request"]["action"], "login")

    def test_in_json_cli_flags_override_json_values(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({
                "schema_version": 1,
                "host": "172.20.20.11",
                "acid": 1,
                "username": "alice",
                "password": "secret",
                "token": "abcdefghijklmnop",
                "preview": True,
                "output": "rich",
            }), encoding="utf-8")

            stdout = io.StringIO()
            # --json on CLI must override "output: rich" from JSON.
            # --username on CLI must override the JSON value.
            with redirect_stdout(stdout):
                rc = main([
                    "login", "--in-json", str(in_json),
                    "--username", "bob", "--json",
                ])

        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["request"]["username"], "bob")

    def test_in_json_missing_action_with_no_subcommand_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({"schema_version": 1, "host": "x"}),
                               encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["--in-json", str(in_json)])
            self.assertEqual(rc, 2)
            self.assertIn("action", stderr.getvalue())

    def test_in_json_rejects_removed_alias_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({"schema_version": 1, "action": "auth"}),
                               encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["--json", "--in-json", str(in_json)])
            self.assertEqual(rc, 2)
            payload = json.loads(stderr.getvalue())
            self.assertIn("action", payload["error"]["message"])
            self.assertIn("auth", payload["error"]["message"])

    def test_in_json_unsupported_schema_version_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            in_json = Path(tmpdir) / "run.json"
            in_json.write_text(json.dumps({"schema_version": 99, "action": "check"}),
                               encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main(["--in-json", str(in_json)])
            self.assertEqual(rc, 2)
            self.assertIn("schema_version", stderr.getvalue())

    def test_in_json_bad_path_errors(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = main(["--in-json", "/nonexistent/run.json"])
        self.assertEqual(rc, 2)
        self.assertIn("could not read", stderr.getvalue())

    def test_in_json_preparse_error_respects_json_output(self) -> None:
        stderr = io.StringIO()
        with redirect_stderr(stderr):
            rc = main(["--json", "--in-json", "/nonexistent/run.json"])
        self.assertEqual(rc, 2)
        payload = json.loads(stderr.getvalue())
        self.assertEqual(payload["error"]["code"], "usage_error")
        self.assertIn("could not read", payload["error"]["message"])

    def test_in_json_preparse_error_respects_quiet_output(self) -> None:
        stdout = io.StringIO()
        stderr = io.StringIO()
        with redirect_stdout(stdout), redirect_stderr(stderr):
            rc = main(["--quiet", "--in-json", "/nonexistent/run.json"])
        self.assertEqual(rc, 2)
        self.assertEqual(stdout.getvalue(), "")
        self.assertEqual(stderr.getvalue(), "")

    def test_input_template_emits_valid_json_with_schema(self) -> None:
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(["input-template", "--action", "login"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertEqual(payload["schema_version"], 1)
        self.assertEqual(payload["action"], "login")
        self.assertIn("host", payload)
        self.assertIn("username", payload)

    def test_input_template_no_meta_block(self) -> None:
        # Templates are raw JSON so users can copy-paste into a file.
        stdout = io.StringIO()
        with redirect_stdout(stdout):
            rc = main(["input-template", "--action", "check"])
        self.assertEqual(rc, 0)
        payload = json.loads(stdout.getvalue())
        self.assertNotIn("meta", payload)

    def test_config_init_writes_and_show_reads_back(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "setting"
            stdout = io.StringIO()
            with redirect_stdout(stdout):
                rc = main([
                    "config", "init",
                    "--config", str(cfg),
                    "--yes",
                    "--host", "10.0.0.1",
                    "--acid", "3",
                    "--campus-postfix", "",
                ])
            self.assertEqual(rc, 0)
            self.assertTrue(cfg.exists())

            stdout2 = io.StringIO()
            with redirect_stdout(stdout2):
                rc = main(["config", "show", "--config", str(cfg), "--json"])
            self.assertEqual(rc, 0)
            payload = json.loads(stdout2.getvalue())
            self.assertEqual(payload["host"], "10.0.0.1")
            self.assertEqual(payload["acid"], 3)
            self.assertTrue(payload["exists"])

    def test_config_init_refuses_overwrite_without_force(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            cfg = Path(tmpdir) / "setting"
            cfg.write_text('host="old"\nacid="1"\n', encoding="utf-8")
            stderr = io.StringIO()
            with redirect_stderr(stderr):
                rc = main([
                    "config", "init",
                    "--config", str(cfg),
                    "--yes",
                    "--host", "new",
                ])
            self.assertEqual(rc, 2)
            # File untouched.
            self.assertIn("old", cfg.read_text(encoding="utf-8"))

    def test_config_path_prints_resolved_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            with patch.dict(os.environ, {"XDG_CONFIG_HOME": tmpdir}):
                stdout = io.StringIO()
                with redirect_stdout(stdout):
                    rc = main(["config", "path"])
        self.assertEqual(rc, 0)
        self.assertIn(tmpdir, stdout.getvalue())
        self.assertIn("auth_ecnu/setting", stdout.getvalue())

    def test_status_subtitle_carries_portal_host(self) -> None:
        from auth_ecnu.render import render_status
        from io import StringIO
        # Force rich to render to a captured stream so we can read the markup.
        with patch("auth_ecnu.render.Console") as fake_console_cls:
            captured = StringIO()

            def fake_print(line, *args, **kwargs):
                captured.write(str(line) + "\n")

            instance = fake_console_cls.return_value
            instance.print = fake_print
            render_status(
                OnlineStatus(online=True, username="alice",
                             raw="alice,1,2,0,0,0,0,0,1.2.3.4,0"),
                "rich",
                command="check",
                host="172.20.20.11",
            )
        self.assertIn("portal=172.20.20.11", captured.getvalue())


if __name__ == "__main__":
    unittest.main()
