"""Lifecycle regressions using isolated state and fake desktop/systemd commands."""

import os
from pathlib import Path
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / "bin" / "sleep-in"


class SleepInTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.state = self.root / "state" / "sleep-in"
        self.env = dict(os.environ, HOME=str(self.root), XDG_STATE_HOME=str(self.root / "state"),
                        PATH=f"{self.bin}:{os.environ['PATH']}", MOCK_ROOT=str(self.root),
                        SLEEP_IN_IDLE_TOGGLE="idle-toggle", SLEEP_IN_SUSPEND_CMD="systemctl suspend")
        self.mock("pgrep", 'test -f "$MOCK_ROOT/idle"')
        self.mock("idle-toggle", '''
if [[ "${1:-}" == status ]]; then
  if test -f "$MOCK_ROOT/idle"; then echo '{"enabled":false}'; else echo '{"enabled":true}'; fi
  exit 0
fi
if test -f "$MOCK_ROOT/idle"; then rm "$MOCK_ROOT/idle"; else touch "$MOCK_ROOT/idle"; fi
echo 'notification output'
exit 1
''')
        self.mock("pkill", "exit 1")
        self.mock("notify-send", "exit 1")
        self.mock("wl-copy", 'cat >"$MOCK_ROOT/clipboard"')
        self.mock("makoctl", "exit 0")
        self.mock("systemd-cat", "cat >/dev/null")
        self.mock("sleep", "exit 0")
        self.mock("systemctl", '''
if [[ "$*" == suspend ]]; then
  echo attempt >>"$MOCK_ROOT/attempts"
  exit "${REJECT_REQUEST:-0}"
elif [[ "$*" == *list-units* ]]; then
  exit 0
elif [[ "$*" == *is-active* ]]; then
  test -f "$MOCK_ROOT/active"
else
  rm -f "$MOCK_ROOT/active"
fi
''')
        self.mock("systemd-run", '''
printf '%s\\n' "$@" >"$MOCK_ROOT/run-args"
[[ "${FAIL_RUN:-0}" == 0 ]] || exit 1
touch "$MOCK_ROOT/active"
''')
        self.mock("hyprctl", "exit 1")
        self.mock("systemd-inhibit", "exit 0")
        self.mock("omarchy-update-lock", 'shift; exec "$@"')
        self.mock("omarchy-update-stay-awake", "exit 0")
        self.mock("journalctl", '''
if [[ "$*" == *--show-cursor* ]]; then
  echo '-- cursor: baseline'
elif [[ "$*" == *--after-cursor* ]]; then
  attempts=$(wc -l <"$MOCK_ROOT/attempts")
  result=failed
  [[ "$attempts" -ge "${SUCCESS_AFTER:-1}" ]] && result=done
  [[ "${PENDING:-0}" == 0 ]] || exit 0
  printf '{"UNIT":"systemd-suspend.service","JOB_RESULT":"%s"}\\n' "$result"
else
  echo 'kernel suspend failed: Device or resource busy'
fi
''')

    def mock(self, name, body):
        path = self.bin / name
        path.write_text("#!/usr/bin/env bash\n" + body + "\n")
        path.chmod(0o755)

    def run_cli(self, *args, expected=0):
        result = subprocess.run([str(SCRIPT), *args], env=self.env, text=True,
                                capture_output=True, timeout=45)
        self.assertEqual(result.returncode, expected, result.stderr)
        return result

    def token(self):
        return dict(line.split("=", 1) for line in (self.state / "timer").read_text().splitlines())["token"]

    def test_leading_zero_duration_and_notifications_are_optional(self):
        (self.root / "idle").touch()
        self.run_cli("schedule", "08h09")
        self.assertIn("minutes=489\nrestore_idle=1", (self.state / "timer").read_text())
        self.assertFalse((self.root / "idle").exists())
        self.assertIn(str(SCRIPT), (self.root / "run-args").read_text())
        self.assertIn("scheduled\t", self.run_cli("status").stdout)

    def test_invalid_duration_keeps_existing_timer(self):
        self.run_cli("schedule", "1h")
        token = self.token()
        for duration in ("0", "999999999999999999999h", "999999h", "oops"):
            self.run_cli("schedule", duration, expected=1)
            self.assertEqual(self.token(), token)

    def test_replacement_and_cancel_restore_original_idle(self):
        (self.root / "idle").touch()
        self.run_cli("schedule", "1h")
        self.run_cli("schedule", "2h")
        self.assertIn("restore_idle=1", (self.state / "timer").read_text())
        self.run_cli("cancel")
        self.assertTrue((self.root / "idle").exists())
        self.assertFalse((self.state / "timer").exists())

    def test_failed_schedule_rolls_back_idle_and_state(self):
        (self.root / "idle").touch()
        self.env["FAIL_RUN"] = "1"
        self.run_cli("schedule", "1h", expected=1)
        self.assertTrue((self.root / "idle").exists())
        self.assertFalse((self.state / "timer").exists())

    def test_suspend_retries_real_failure_then_succeeds(self):
        self.env["SUCCESS_AFTER"] = "2"
        self.run_cli("schedule", "1m")
        self.run_cli("fire", self.token())
        self.assertEqual(len((self.root / "attempts").read_text().splitlines()), 2)
        self.assertFalse((self.state / "timer").exists())
        self.assertFalse((self.state / "failure").exists())

    def test_exhausted_retries_preserve_failure(self):
        self.env["SUCCESS_AFTER"] = "99"
        self.run_cli("schedule", "1m")
        self.run_cli("fire", self.token(), expected=1)
        self.assertEqual(len((self.root / "attempts").read_text().splitlines()), 3)
        self.assertIn("Device or resource busy", (self.state / "failure").read_text())

    def test_unknown_outcome_does_not_retry(self):
        self.env["PENDING"] = "1"
        self.run_cli("schedule", "1m")
        self.run_cli("fire", self.token(), expected=1)
        self.assertEqual(len((self.root / "attempts").read_text().splitlines()), 1)

    def test_stale_fire_cannot_suspend_replacement(self):
        self.run_cli("schedule", "1m")
        old = self.token()
        self.run_cli("schedule", "2m")
        self.run_cli("fire", old)
        self.run_cli("request", old, str(self.state / "request.stale"))
        self.assertFalse((self.root / "attempts").exists())
        self.assertTrue((self.state / "timer").exists())

    def test_cancelled_timer_cannot_fire(self):
        self.run_cli("schedule", "1m")
        token = self.token()
        self.run_cli("cancel")
        self.run_cli("fire", token)
        self.assertFalse((self.root / "attempts").exists())

    def test_rejected_request_retries_and_reports_failure(self):
        self.env["REJECT_REQUEST"] = "1"
        self.run_cli("schedule", "1m")
        self.run_cli("fire", self.token(), expected=1)
        self.assertEqual(len((self.root / "attempts").read_text().splitlines()), 3)
        self.assertTrue((self.state / "failure").exists())

    def test_hyprland_failure_falls_back_to_direct_request(self):
        self.mock("hyprctl", "exit 1")
        self.run_cli("schedule", "1m")
        self.run_cli("fire", self.token())
        self.assertEqual(len((self.root / "attempts").read_text().splitlines()), 1)

    def test_already_disabled_idle_stays_disabled_on_cancel(self):
        self.run_cli("schedule", "1m")
        self.run_cli("cancel")
        self.assertFalse((self.root / "idle").exists())

    def test_copy_failure_copies_diagnostics_and_preserves_report(self):
        self.state.mkdir(parents=True)
        report = "Suspend failed\nChrome_ChildIOT refused to freeze\n"
        (self.state / "failure").write_text(report)
        self.run_cli("copy-failure")
        self.assertEqual((self.root / "clipboard").read_text(), report)
        self.run_cli("schedule", "1m")
        self.run_cli("cancel")
        self.assertEqual((self.state / "failure").read_text(), report)

    def test_missing_failure_does_not_replace_clipboard(self):
        self.run_cli("copy-failure", expected=1)
        self.assertFalse((self.root / "clipboard").exists())

    def test_clipboard_owner_does_not_hold_notification_handler_open(self):
        self.state.mkdir(parents=True)
        (self.state / "failure").write_text("Failure details\n")
        self.mock("wl-copy", 'cat >"$MOCK_ROOT/clipboard"; /bin/sleep 3 &')
        proc = subprocess.run([str(SCRIPT), "copy-failure"], env=self.env,
                              capture_output=True, timeout=2)
        self.assertEqual(proc.returncode, 0, proc.stderr)

    def test_failed_clipboard_copy_returns_failure(self):
        self.state.mkdir(parents=True)
        (self.state / "failure").write_text("Failure details\n")
        self.mock("wl-copy", "exit 1")
        self.run_cli("copy-failure", expected=1)

    def test_installer_adds_notification_rule_once(self):
        config = self.root / ".config" / "mako" / "config"
        config.parent.mkdir(parents=True)
        config.write_text("default-timeout=5000\n")
        self.env.pop("HYPRLAND_INSTANCE_SIGNATURE", None)
        for _ in range(2):
            proc = subprocess.run([str(SCRIPT.parent.parent / "install.sh")], env=self.env,
                                  capture_output=True, text=True, timeout=15)
            self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(config.read_text().count("include=~/.config/mako/sleep-in.conf"), 1)
        rule = config.with_name("sleep-in.conf").read_text()
        self.assertIn("default-timeout=0", rule)
        self.assertIn("copy-failure && makoctl dismiss", rule)
        self.assertTrue((self.root / ".local" / "bin" / "sleep-in").exists())


if __name__ == "__main__":
    unittest.main()
