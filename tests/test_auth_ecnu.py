import io
import json
import unittest
from contextlib import redirect_stdout

from auth_ecnu import AuthParams, build_request_params
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
