import contextlib
import io
import json
import os
import subprocess
import tempfile
import time
from unittest.mock import patch
import unittest
from pathlib import Path
from spite.cli import main


class HistoryTests(unittest.TestCase):
    def setUp(self):
        self.timezone = patch.dict(os.environ, {'TZ': 'UTC'})
        self.timezone.start()
        time.tzset()
        self.addCleanup(self.restore_timezone)
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.repo = Path(self.temp.name) / 'repo'
        self.repo.mkdir()
        self.old = Path.cwd()
        os.chdir(self.repo)
        self.addCleanup(os.chdir, self.old)
        self.git('init', '-q', '-b', 'release')
        self.git('config', 'user.name', 'Test')
        self.git('config', 'user.email', 'test@example.com')
        self.commit('base', '2024-01-01T12:00:00+00:00')
        self.base = self.git('rev-parse', 'HEAD')

    def restore_timezone(self):
        self.timezone.stop()
        time.tzset()

    def git(self, *args, env=None):
        result = subprocess.run(['git', *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=env)
        return result.stdout.strip()

    def commit(self, name, timestamp):
        (self.repo / name).write_text(name)
        self.git('add', name)
        env = dict(os.environ, GIT_AUTHOR_DATE=timestamp, GIT_COMMITTER_DATE=timestamp)
        self.git('commit', '-qm', name, env=env)

    def call(self, args):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        return output.getvalue()

    def test_linear_span_and_empty_range(self):
        self.commit('one', '2024-01-02T12:00:00+00:00')
        self.commit('two', '2024-01-05T12:00:00+00:00')
        report = self.call(['history', '--base', self.base, '--days-per-period', '3'])
        self.assertIn('Observed work units (non-merge commits): 2; merge commits: 0', report)
        self.assertIn('Linear within the observed range', report)
        self.assertIn('Span: 3.00 calendar days (approximately 1.00 periods', report)
        self.assertIn('- Earliest committer timestamp: 2024-01-02 12:00:00(UTC)\n- Latest committer timestamp: 2024-01-05 12:00:00(UTC)\n- Span: 3.00 calendar days (approximately 1.00 periods at 3 days per period)\n\nThis is the elapsed span', report)
        self.assertIn('not measured development duration', report)
        self.assertIn('No commits in the selected range', self.call(['history', '--base', 'HEAD']))

    def test_parallel_merge_and_snapshot(self):
        self.git('checkout', '-qb', 'feature')
        self.commit('feature', '2024-01-03T12:00:00+00:00')
        self.git('checkout', '-q', 'release')
        self.commit('main', '2024-01-02T12:00:00+00:00')
        env = dict(os.environ, GIT_AUTHOR_DATE='2024-01-04T12:00:00+00:00', GIT_COMMITTER_DATE='2024-01-04T12:00:00+00:00')
        self.git('merge', '--no-ff', '-qm', 'merge', 'feature', env=env)
        root = str(self.repo / 'output')
        output = self.call(['history', '--base', self.base, '--output', root, '--days-per-period', '2'])
        run_id = output.splitlines()[0].split(': ', 1)[1]
        path = Path(root) / 'history' / run_id
        snapshot = json.loads((path / 'snapshot.json').read_text())
        report = (path / 'report.md').read_text()
        self.assertEqual(snapshot['work_units'], 2)
        self.assertEqual(snapshot['merge_commits'], 1)
        self.assertEqual(snapshot['classification'], 'Parallel paths present')
        self.assertEqual(snapshot['observed_periods'], 1)
        self.assertIn('Git ancestry does not establish actual task dependencies', report)
        self.assertIn('flowchart LR', report)
        self.assertIn(' --> ', report)

    def test_additional_periods_and_start_validation(self):
        self.git('checkout', '-qb', 'feature')
        self.commit('feature', '2024-01-03T12:00:00+00:00')
        self.git('checkout', '-q', 'release')
        env = dict(os.environ, GIT_AUTHOR_DATE='2024-01-05T12:00:00+00:00', GIT_COMMITTER_DATE='2024-01-05T12:00:00+00:00')
        self.git('merge', '--no-ff', '-qm', 'merge', 'feature', env=env)
        report = self.call(['history', '--base', self.base, '--development-start', '2024-01-01T21:00:00+09:00', '--days-per-period', '2'])
        self.assertIn('Pre-Git: 2.00 calendar days (approximately 1.00 periods)', report)
        self.assertIn('Release wait: 2.00 calendar days (approximately 1.00 periods)', report)
        self.assertIn('- Development start: 2024-01-01 12:00:00(UTC)\n- Earliest commit: 2024-01-03 12:00:00(UTC)\n- Elapsed: 2.00 calendar days (approximately 1.00 periods)\n\nThis may include', report)
        self.assertIn('- Last non-merge commit: 2024-01-03 12:00:00(UTC)\n- Last subsequent merge: 2024-01-05 12:00:00(UTC)\n- Elapsed: 2.00 calendar days (approximately 1.00 periods)\n\nThis proxy', report)
        feature = self.git('rev-parse', 'feature')
        merge = self.git('rev-parse', 'HEAD')
        self.assertIn(f'N{self.base} --> PreGit', report)
        self.assertIn(f'PreGit --> N{feature}', report)
        self.assertIn(f'N{feature} --> ReleaseWait', report)
        self.assertIn(f'ReleaseWait --> N{merge}', report)
        self.assertNotIn(f'N{feature} --> N{merge}', report)
        self.assertIn('not Git commits or evidence of ancestry', report)
        self.assertIn('Dashed borders identify period nodes', report)
        self.assertIn('classDef period stroke-dasharray: 5 5', report)
        self.assertIn('class PreGit period', report)
        self.assertIn('class ReleaseWait period', report)
        for invalid in ('2024-01-04T00:00:00+00:00', '2024-01-01T00:00:00'):
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(['history', '--base', self.base, '--development-start', invalid])
        empty = self.call(['history', '--base', 'HEAD', '--development-start', '2024-01-01T00:00:00+00:00'])
        self.assertNotIn('## Pre-Git period', empty)

    def test_local_timezone_and_dst(self):
        self.commit('winter', '2024-01-15T12:00:00+00:00')
        self.commit('summer', '2024-07-15T12:00:00+00:00')
        try:
            with patch.dict(os.environ, {'TZ': 'America/New_York'}):
                time.tzset()
                report = self.call(['history', '--base', self.base])
        finally:
            time.tzset()
        self.assertIn('2024-01-15 07:00:00(EST)', report)
        self.assertIn('2024-07-15 08:00:00(EDT)', report)

    def test_squash_merge_is_only_one_observed_work_unit(self):
        self.git('checkout', '-qb', 'feature')
        self.commit('feature_a', '2024-01-02T12:00:00+00:00')
        self.commit('feature_b', '2024-01-03T12:00:00+00:00')
        self.git('checkout', '-q', 'release')
        self.git('merge', '--squash', 'feature')
        env = dict(os.environ, GIT_AUTHOR_DATE='2024-01-04T12:00:00+00:00', GIT_COMMITTER_DATE='2024-01-04T12:00:00+00:00')
        self.git('commit', '-qm', 'squashed feature', env=env)
        report = self.call(['history', '--base', self.base])
        self.assertIn('Observed work units (non-merge commits): 1; merge commits: 0', report)
        self.assertIn('Linear within the observed range', report)
        self.assertIn('Squash merges and missing history can hide branches', report)

    def test_detached_head_and_non_ancestor_are_rejected(self):
        self.git('checkout', '-qb', 'other')
        self.commit('other', '2024-01-02T12:00:00+00:00')
        other = self.git('rev-parse', 'HEAD')
        self.git('checkout', '-q', 'release')
        self.commit('release_work', '2024-01-03T12:00:00+00:00')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['history', '--base', other])
        self.git('checkout', '-q', '--detach')
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['history', '--base', self.base])

    def test_predict_forecast_comparison_and_validation(self):
        self.commit('one', '2024-01-02T12:00:00+00:00')
        self.commit('two', '2024-01-04T12:00:00+00:00')
        root = str(self.repo / 'output')
        result = self.call(['predict', '--periods', '6', '--format', 'markdown', '--output', root])
        run_id = result.splitlines()[0].split(': ', 1)[1]
        result = self.call(['history', '--base', self.base, '--output', root, '--forecast-id', run_id, '--forecast-kind', 'predict', '--days-per-period', '2'])
        history_id = result.splitlines()[0].split(': ', 1)[1]
        report = (Path(root) / 'history' / history_id / 'report.md').read_text()
        self.assertIn('Observed commit timestamp span | 1.00', report)
        self.assertIn('Forecast P80', report)
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['history', '--base', self.base, '--forecast-id', run_id, '--output', root])
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            main(['history', '--base', 'not-a-ref'])


if __name__ == '__main__':
    unittest.main()
