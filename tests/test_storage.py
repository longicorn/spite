import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from spite.cli import main


class StorageTests(unittest.TestCase):
    def run_cli(self, args):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(main(args), 0)
        return out.getvalue().splitlines()[0].split(': ', 1)[1]

    def test_continuation_saves_parent_and_compares_total(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.run_cli(['simulate', '--output', root, '--iterations', '10', '--seed', '1', '--tasks-per-period', '5'])
            second = self.run_cli(['simulate', '--output', root, '--continue-from', first, '--elapsed-periods', '2', '--completed-tasks', '5', '--remaining-tasks', '3', '--seed', '2'])
            a = json.loads((Path(root) / 'simulate' / first / 'snapshot.json').read_text())
            path = Path(root) / 'simulate' / second
            b = json.loads((path / 'snapshot.json').read_text())
            self.assertNotEqual(first, second)
            self.assertEqual(b['parent_run_id'], first)
            self.assertEqual(b['config']['tasks_per_period'], 5)
            self.assertEqual(b['config']['iterations'], 10)
            self.assertEqual(b['progress']['remaining_tasks'], 3)
            self.assertEqual(len(b['samples']['Nominal']), 10)
            self.assertAlmostEqual(b['summary']['Nominal']['total']['p80'], b['summary']['Nominal']['remaining']['p80'] + 2)
            report = (path / 'report.md').read_text()
            self.assertIn('| Scenario | Percentile | Previous total | Remaining | Updated total |', report)
            for label in ('P50', 'P80', 'P90'):
                self.assertIn(f'| Nominal | {label} |', report)
            self.assertIn('new synthetic graph', report)
            self.assertTrue(a['samples']['Nominal'])

    def test_zero_remaining_and_invalid_continuation(self):
        with tempfile.TemporaryDirectory() as root:
            first = self.run_cli(['simulate', '--output', root, '--iterations', '3'])
            second = self.run_cli(['simulate', '--output', root, '--continue-from', first, '--elapsed-periods', '2', '--completed-tasks', '5', '--remaining-tasks', '0'])
            data = json.loads((Path(root) / 'simulate' / second / 'snapshot.json').read_text())
            self.assertEqual(data['summary']['Nominal']['total']['p80'], 2)
            for args in [ ['--continue-from', '../x', '--elapsed-periods', '2', '--completed-tasks', '5', '--remaining-tasks', '1'], ['--continue-from', second, '--elapsed-periods', '1', '--completed-tasks', '5', '--remaining-tasks', '1'], ['--continue-from', first] ]:
                with self.subTest(args=args), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                    main(['simulate', '--output', root] + args)

    def test_runs_are_distinct_and_seed_recorded(self):
        with tempfile.TemporaryDirectory() as root:
            ids = [self.run_cli(['simulate', '--output', root, '--iterations', '2']) for _ in range(2)]
            self.assertNotEqual(*ids)
            self.assertIsInstance(json.loads((Path(root) / 'simulate' / ids[0] / 'snapshot.json').read_text())['seed'], int)


if __name__ == '__main__':
    unittest.main()
