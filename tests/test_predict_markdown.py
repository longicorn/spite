import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from spite.cli import main


class PredictTests(unittest.TestCase):
    args = ['predict', '--periods', '6']

    def run_cli(self, args):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(args), 0)
        return output.getvalue()

    def test_markdown_and_approximate_conversion(self):
        report = self.run_cli(self.args + ['--format', 'markdown', '--days-per-period', '5'])
        self.assertIn('| Nominal | 7.7 periods (approx. 38.5 days)', report)
        self.assertEqual(report.count('    line ['), 3)
        self.assertNotIn('## Retrospective', report)

    def test_retrospective_and_file(self):
        with tempfile.TemporaryDirectory() as directory:
            result = self.run_cli(self.args + ['--format', 'markdown', '--output', directory, '--actual-periods', '20'])
            run_id = result.splitlines()[0].split(': ', 1)[1]
            run_path = Path(directory) / 'predict' / run_id
            self.assertTrue((run_path / 'snapshot.json').exists())
            report = (run_path / 'report.md').read_text(encoding='utf-8')
            self.assertIn('Actual completion: 20.0 periods', report)
            self.assertIn('Difference from P90:', report)
            self.assertIn('Position in forecast:', report)

    def test_terminal_and_no_conversion_by_default(self):
        output = self.run_cli(self.args)
        self.assertIn('Legend:', output)
        self.assertNotIn('days', output)

    def test_invalid_conversion_and_show(self):
        for extra in (['--days-per-period', '0'], ['--days-per-period', 'nan'], ['--format', 'markdown', '--show']):
            with self.subTest(extra=extra), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(self.args + extra)

    def test_simulation_explains_nominal_percentiles(self):
        for output_format in ('terminal', 'markdown'):
            report = self.run_cli(['simulate', '--iterations', '10', '--seed', '4', '--days-per-period', '5', '--format', output_format])
            nominal = next(line for line in report.splitlines() if line.startswith('| Nominal |'))
            p50, p80, p90 = [cell.strip() for cell in nominal.split('|')[2:5]]
            self.assertIn(f'50% of simulated projects finished within {p50}, 80% within {p80}, and 90% within {p90}', report)
            self.assertIn('do not guarantee actual completion times', report)
            self.assertNotIn('## Nominal distribution', report)

    def test_simulation_labels_review_wait_in_report_and_diagram(self):
        report = self.run_cli(['simulate', '--iterations', '5', '--seed', '4'])
        self.assertIn('Waiting for reviews and approvals does not occupy development team slots', report)
        self.assertIn('review and approval waiting time on the displayed execution path', report)
        self.assertIn('Integration review', report)
        self.assertIn('classDef review', report)
        self.assertNotIn('gate', report.lower())

    def test_simulation_task_mode_changes_forecast(self):
        base_args = ['simulate', '--iterations', '100', '--seed', '4', '--pattern', 'linear', '--scale', 'small']
        default = self.run_cli(base_args)
        faster = self.run_cli(base_args + ['--tasks-per-period', '5', '--days-per-period', '5'])
        self.assertIn('reference tasks per period per team member: 5; base task duration mode: 0.2 periods', faster)
        self.assertNotEqual(next(line for line in default.splitlines() if line.startswith('| Nominal |')), next(line for line in faster.splitlines() if line.startswith('| Nominal |')))
        for value in ('0', '-1', 'nan', 'inf', '1e-320'):
            with self.subTest(value=value), contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
                main(base_args + ['--tasks-per-period', value])

    def test_simulation_conversion_and_no_calendar(self):
        report = self.run_cli(['simulate', '--iterations', '10', '--seed', '4', '--days-per-period', '5'])
        self.assertIn('1 period = 5 days', report)
        self.assertIn('approx.', report)
        self.assertNotIn('Business days', report)
        self.assertNotIn('start:', report)


    def test_target_report_rounds_completion_and_complements_delay(self):
        from spite.target import report

        result = report(10, {'Nominal': (0.725, 0.275), 'Worst': (0.9999, 0.0001), 'Low': (0.0049, 0.9951), 'Zero': (0, 1), 'Full': (1, 0), 'Boundary': (0.005, 0.995), 'High': (0.995, 0.005), 'Tail': (1.0, 1e-20)}, None)
        self.assertIn('| Scenario | Completion probability |', result)
        self.assertIn('| Nominal | 73% (delay 27%) |', result)
        self.assertIn('| Worst | >99% (delay <1%) |', result)
        for expected in ('| Low | <1% (delay >99%) |', '| Zero | 0% (delay 100%) |', '| Full | 100% (delay 0%) |', '| Boundary | 1% (delay 99%) |', '| High | >99% (delay <1%) |', '| Tail | >99% (delay <1%) |'):
            self.assertIn(expected, result)

    def test_target_and_actual_markers_share_ascii_chart(self):
        from spite.params import params_from_mode_and_sigma
        from spite.lognormal import percentile_days
        from spite.render import render_ascii

        params = params_from_mode_and_sigma(10, 0.4)
        scenarios = {name: (params, {'p90': percentile_days(params, .9)}) for name in ('Best', 'Nominal', 'Worst')}
        chart = render_ascii(scenarios, actual_periods=10, target_periods=100)
        self.assertIn('^ Actual: 10 periods', chart)
        self.assertIn('^ Target: 100 periods', chart)


if __name__ == '__main__':
    unittest.main()
