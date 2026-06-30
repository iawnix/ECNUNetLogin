"""Smoke test for scripts/setup.sh.

End-to-end exercises the venv backend in an isolated tempdir:

    setup.sh install --method=venv --yes ...
    -> assert state file + config file + venv binary
    setup.sh status
    -> assert it prints the recorded layout
    setup.sh uninstall --purge --yes
    -> assert venv, config, state file are all gone

The pipx/user backends are not covered here (they'd touch the user's
real environment); the venv path exercises the bulk of the script
logic and the state-file plumbing.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SETUP_SH = PROJECT_ROOT / "scripts" / "setup.sh"


def _has(cmd: str) -> bool:
    return shutil.which(cmd) is not None


@unittest.skipUnless(_has("bash"), "bash not available")
@unittest.skipUnless(SETUP_SH.exists(), "scripts/setup.sh missing")
class SetupShSmokeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.mkdtemp(prefix="auth_ecnu_setup_test_")
        self.xdg = Path(self.tmp) / "config"
        self.venv = Path(self.tmp) / "venv"
        self.env = {
            **os.environ,
            "XDG_CONFIG_HOME": str(self.xdg),
        }

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _run(self, *args: str, expect_ok: bool = True, timeout: int = 180) -> subprocess.CompletedProcess:
        proc = subprocess.run(
            ["bash", str(SETUP_SH), *args],
            env=self.env,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        if expect_ok and proc.returncode != 0:
            self.fail(
                f"setup.sh {' '.join(args)} exited {proc.returncode}\n"
                f"stdout:\n{proc.stdout}\n"
                f"stderr:\n{proc.stderr}"
            )
        return proc

    def test_venv_install_status_uninstall_roundtrip(self) -> None:
        # --- install ---
        self._run(
            "install",
            "--method=venv",
            f"--install-path={self.venv}",
            "--host=test.host.example",
            "--acid=2",
            "--campus-postfix=@u",
            "--yes",
        )

        # state file written
        state_file = self.xdg / "auth_ecnu" / "install-state"
        self.assertTrue(state_file.exists(), "state file not written")
        state = dict(
            line.strip().split("=", 1)
            for line in state_file.read_text(encoding="utf-8").splitlines()
            if "=" in line
        )
        self.assertEqual(state["method"], "venv")
        self.assertEqual(state["install_path"], str(self.venv))

        # config file written, mode 600, contains the host we passed
        config_file = self.xdg / "auth_ecnu" / "setting"
        self.assertTrue(config_file.exists(), "config file not written")
        self.assertEqual(
            config_file.stat().st_mode & 0o777, 0o600,
            "config file should be mode 600",
        )
        body = config_file.read_text(encoding="utf-8")
        self.assertIn('host="test.host.example"', body)
        self.assertIn('acid="2"', body)
        self.assertIn('campus_postfix="@u"', body)
        # Critical: never write a username= or password= key.
        # (The warning comment may *mention* the words; we check key form.)
        config_keys = {
            line.split("=", 1)[0].strip()
            for line in body.splitlines()
            if "=" in line and not line.lstrip().startswith("#")
        }
        self.assertNotIn("username", config_keys)
        self.assertNotIn("password", config_keys)

        # venv binary actually works
        bin_auth = self.venv / "bin" / "auth_ecnu"
        self.assertTrue(bin_auth.exists(), f"auth_ecnu binary not at {bin_auth}")
        result = subprocess.run(
            [str(bin_auth), "--version"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("auth_ecnu", result.stdout)

        # --- status ---
        proc = self._run("status")
        self.assertIn("venv", proc.stdout)
        self.assertIn(str(self.venv), proc.stdout)
        self.assertIn(str(config_file), proc.stdout)

        # --- uninstall --purge ---
        self._run("uninstall", "--purge", "--yes")
        self.assertFalse(self.venv.exists(), "venv should be removed")
        self.assertFalse(config_file.exists(), "config should be removed by --purge")
        self.assertFalse(state_file.exists(), "state should be removed by --purge")

        # status after uninstall is informational; returncode 1 is fine.
        proc = self._run("status", expect_ok=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("no install-state", proc.stderr)

    def test_install_yes_without_method_fails_loud(self) -> None:
        proc = self._run("install", "--yes", expect_ok=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("method", proc.stderr.lower())

    def test_install_unknown_method_fails_loud(self) -> None:
        proc = self._run("install", "--method=banana", "--yes", expect_ok=False)
        self.assertNotEqual(proc.returncode, 0)
        self.assertIn("method", proc.stderr.lower())


if __name__ == "__main__":
    unittest.main()
