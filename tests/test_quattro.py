"""Exercise the installed timer with isolated state and harmless suspend stubs."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

LIVE = Path(__file__).resolve().parents[1] / 'bin/sleep-in'

STUB = r'''#!/usr/bin/python3
import json, os, pathlib, subprocess, sys
name = pathlib.Path(sys.argv[0]).name
root = pathlib.Path(os.environ['FIXTURE_ROOT'])
args = sys.argv[1:]
with (root / 'calls.jsonl').open('a') as f:
    f.write(json.dumps([name, *args]) + '\n')
if name == 'hyprctl':
    if os.environ.get('DISPATCH_REJECT') == '1':
        sys.exit(1)
    assert len(args) == 2 and args[0] == 'dispatch', args
    expr = args[1]
    assert expr.startswith('hl.dsp.exec_cmd(') and expr.endswith(')'), expr
    command = json.loads(expr[len('hl.dsp.exec_cmd('):-1])
    subprocess.run(['bash', '-c', command], check=False)
elif name == 'safe-suspend':
    if (root / 'application-block').exists():
        print('Call to Suspend failed: Operation denied due to active block inhibitor', file=sys.stderr)
        sys.exit(1)
    with (root / 'suspend-requests').open('a') as f:
        f.write('harmless test request\n')
elif name == 'journalctl':
    if '--show-cursor' in args:
        print('-- cursor: fixture-cursor')
    elif '-u' in args and '--after-cursor=fixture-cursor' in args:
        print(json.dumps({'UNIT': 'systemd-suspend.service', 'JOB_RESULT': os.environ.get('SUSPEND_JOB_RESULT', 'done')}))
elif name == 'omarchy-update-lock':
    assert args[:1] == ['run']
    if os.environ.get('UPDATE_ACTIVE') == '1':
        print('An Omarchy update is already running.')
        sys.exit(1)
    sys.exit(subprocess.run(args[1:]).returncode)
elif name == 'omarchy-update-stay-awake':
    assert args == ['stop']
    (root / 'stale-update-block').unlink(missing_ok=True)
elif name == 'systemd-inhibit':
    print('WHO WHAT WHY MODE')
    if (root / 'application-block').exists():
        print('FixtureApp sleep unsaved-work block')
    if (root / 'stale-update-block').exists() or os.environ.get('UPDATE_ACTIVE') == '1':
        print('omarchy-update sleep update-in-progress block')
elif name == 'omarchy-toggle-idle':
    p = root / 'stay-awake'
    value = p.read_text() == 'true'
    if args == ['status']:
        print(json.dumps({'enabled': value}))
    else:
        p.write_text('false' if value else 'true')
elif name == 'systemd-run':
    sys.exit(1 if os.environ.get('SCHEDULE_FAIL') == '1' else 0)
elif name == 'systemd-cat':
    with (root / 'journal').open('a') as f:
        f.write(sys.stdin.read())
elif name in ('systemctl', 'notify-send', 'pkill', 'sleep'):
    pass
else:
    raise AssertionError(name)
'''


class SleepInTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="sleep regression ' ü ")
        self.root = Path(self.tmp.name)
        self.bin = self.root / 'bin'
        self.bin.mkdir()
        self.script = self.bin / 'sleep-in'
        shutil.copy2(LIVE, self.script)
        # Exercise Quattro idle behavior even on CI hosts without Omarchy.
        source = self.script.read_text().replace(
            '[[ -f /usr/share/omarchy/shell/plugins/services/idle/Service.qml ]]', 'true')
        self.script.write_text(source)
        self.state = self.root / 'state/sleep-in'
        self.state.mkdir(parents=True)
        self.env = os.environ.copy()
        self.env.update(FIXTURE_ROOT=str(self.root),
                        XDG_STATE_HOME=str(self.root / 'state'),
                        PATH=str(self.bin) + ':' + self.env['PATH'],
                        SLEEP_IN_IDLE_TOGGLE='omarchy-toggle-idle')
        for flag in ['UPDATE_ACTIVE', 'DISPATCH_REJECT', 'SUSPEND_JOB_RESULT', 'SCHEDULE_FAIL']:
            self.env.pop(flag, None)
        for name in ['hyprctl', 'safe-suspend', 'journalctl', 'omarchy-update-lock',
                     'omarchy-update-stay-awake', 'systemd-inhibit', 'systemctl',
                     'systemd-run', 'systemd-cat', 'notify-send', 'pkill', 'sleep',
                     'omarchy-toggle-idle']:
            p = self.bin / name
            p.write_text(STUB)
            p.chmod(0o755)
        # No test invokes the real suspend command, even in the direct fallback.
        import shlex
        self.env['SLEEP_IN_SUSPEND_CMD'] = shlex.quote(str(self.bin / 'safe-suspend'))
        (self.root / 'stay-awake').write_text('true')

    def tearDown(self):
        self.tmp.cleanup()

    def run_script(self, *args):
        return subprocess.run([str(self.script), *args], env=self.env,
                              capture_output=True, text=True, timeout=20)

    def timer(self, token='fixture-token'):
        (self.state / 'timer').write_text(f'deadline=1\nminutes=120\nrestore_idle=0\ntoken={token}\n')

    def calls(self, name):
        p = self.root / 'calls.jsonl'
        return [x for line in (p.read_text().splitlines() if p.exists() else [])
                if (x := json.loads(line))[0] == name]

    def test_full_fire_uses_lua_dispatch_and_handles_quoted_paths(self):
        self.timer()
        result = self.run_script('fire', 'fixture-token')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls('safe-suspend')), 1)
        self.assertEqual(len(self.calls('hyprctl')), 1)
        self.assertFalse((self.state / 'timer').exists())
        self.assertFalse((self.state / 'failure').exists())
        self.assertIn('suspend completed successfully', (self.root / 'journal').read_text())

    def test_stale_update_block_is_cleaned_before_request(self):
        self.timer()
        (self.root / 'stale-update-block').touch()
        result = self.run_script('fire', 'fixture-token')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / 'stale-update-block').exists())
        self.assertEqual(len(self.calls('safe-suspend')), 1)

    def test_active_update_is_not_interrupted(self):
        self.timer()
        self.env['UPDATE_ACTIVE'] = '1'
        result = self.run_script('fire', 'fixture-token')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.calls('safe-suspend'), [])
        self.assertEqual(self.calls('omarchy-update-stay-awake'), [])
        self.assertIn('Suspend deferred: an update is running', (self.state / 'failure').read_text())

    def test_other_application_inhibitors_remain_respected_and_diagnosed(self):
        self.timer()
        (self.root / 'application-block').touch()
        result = self.run_script('fire', 'fixture-token')
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue((self.root / 'application-block').exists())
        failure = (self.state / 'failure').read_text()
        self.assertIn('active block inhibitor', failure)
        self.assertIn('FixtureApp', failure)

    def test_dispatch_failure_has_a_safe_direct_fallback(self):
        self.timer()
        self.env['DISPATCH_REJECT'] = '1'
        result = self.run_script('fire', 'fixture-token')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(len(self.calls('safe-suspend')), 1)

    def test_kernel_job_failure_is_not_reported_as_success(self):
        self.timer()
        self.env['SUSPEND_JOB_RESULT'] = 'failed'
        result = self.run_script('fire', 'fixture-token')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(len(self.calls('safe-suspend')), 3)
        self.assertTrue((self.state / 'failure').exists())

    def test_old_cancelled_token_cannot_suspend(self):
        self.timer('new-token')
        result = self.run_script('fire', 'old-token')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.calls('safe-suspend'), [])
        self.assertTrue((self.state / 'timer').exists())

    def test_timer_replacement_and_cancellation_restore_original_idle_state(self):
        (self.root / 'stay-awake').write_text('false')
        self.assertEqual(self.run_script('schedule', '2h').returncode, 0)
        self.assertIn('restore_idle=1', (self.state / 'timer').read_text())
        self.assertEqual((self.root / 'stay-awake').read_text(), 'true')
        self.assertEqual(self.run_script('schedule', '30m').returncode, 0)
        self.assertIn('restore_idle=1', (self.state / 'timer').read_text())
        self.assertEqual(self.run_script('cancel').returncode, 0)
        self.assertEqual((self.root / 'stay-awake').read_text(), 'false')
        self.assertFalse((self.state / 'timer').exists())

    def test_timer_start_failure_rolls_back_idle_state_and_timer(self):
        (self.root / 'stay-awake').write_text('false')
        self.env['SCHEDULE_FAIL'] = '1'
        self.assertNotEqual(self.run_script('schedule', '20m').returncode, 0)
        self.assertEqual((self.root / 'stay-awake').read_text(), 'false')
        self.assertFalse((self.state / 'timer').exists())


if __name__ == '__main__':
    unittest.main(verbosity=2)
