import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from spite.cli import main


class HtmlTests(unittest.TestCase):
    def test_commands_and_saved_report(self):
        with tempfile.TemporaryDirectory() as root:
            for command in (['predict', '--periods', '6'],
                            ['simulate', '--iterations', '2', '--seed', '1'],
                            ['history', '--base', 'HEAD']):
                out = io.StringIO()
                with contextlib.redirect_stdout(out):
                    self.assertEqual(main(command + ['--format', 'html', '--output', root]), 0)
                run_id = out.getvalue().splitlines()[0].split(': ')[1]
                directory = Path(root) / command[0] / run_id
                result = (directory / 'report.html').read_text()
                self.assertIn('<!doctype html>', result)
                self.assertIn('@media print', result)
                self.assertTrue((directory / 'report.md').exists())
                if command[0] != 'history':
                    self.assertIn('data:image/png;base64,', result)
                self.assertNotIn('<script', result)

    def test_simulation_html_labels_remaining_target(self):
        from unittest.mock import patch
        from matplotlib.axes import Axes

        labels = []
        original = Axes.axvline

        def capture(axis, *args, **kwargs):
            labels.append((args[0], kwargs.get('label')))
            return original(axis, *args, **kwargs)

        with tempfile.TemporaryDirectory() as root:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['simulate', '--iterations', '2', '--seed', '1', '--output', root]), 0)
            run_id = output.getvalue().split('Run ID: ')[1].splitlines()[0]
            with patch.object(Axes, 'axvline', capture), contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(['simulate', '--output', root, '--continue-from', run_id,
                                       '--format', 'html', '--target-periods', '16',
                                       '--elapsed-periods', '3', '--completed-tasks', '1',
                                       '--remaining-tasks', '2']), 0)
        self.assertIn((13.0, 'Target (remaining): 13 periods'), labels)

    def test_overdue_target_warning_for_yaml_and_continuation(self):
        warning = 'Warning: Target duration is earlier than the elapsed duration.'
        with tempfile.TemporaryDirectory() as root:
            topology = Path(root) / 'topology.yaml'
            topology.write_text('elapsed_periods: 10\ntasks: []\n')
            for target_value, expected in [('8', True), ('10', False), ('12', False)]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(['simulate', '--topology', str(topology), '--iterations', '2',
                                           '--target-periods', target_value]), 0)
                self.assertEqual(warning in output.getvalue(), expected)
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(main(['simulate', '--iterations', '2', '--output', root]), 0)
            run_id = output.getvalue().split('Run ID: ')[1].splitlines()[0]
            for target_value, expected in [('8', True), ('10', False)]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    self.assertEqual(main(['simulate', '--output', root, '--continue-from', run_id,
                                           '--elapsed-periods', '10', '--completed-tasks', '1',
                                           '--remaining-tasks', '0', '--target-periods', target_value,
                                           '--format', 'html']), 0)
                child = output.getvalue().split('Run ID: ')[1].splitlines()[0]
                html = (Path(root) / 'simulate' / child / 'report.html').read_text()
                self.assertEqual(warning in html, expected)

    def test_japanese_diagram_has_no_missing_glyph_warnings(self):
        import warnings
        from spite.html import diagram
        from matplotlib import font_manager
        from matplotlib.ft2font import FT2Font
        required = set(map(ord, '応答処理'))
        if not any(required <= set(FT2Font(font.fname).get_charmap())
                   for font in font_manager.fontManager.ttflist
                   if 'lastresort' not in font.name.lower().replace(' ', '')):
            self.skipTest('Japanese font is not installed')
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter('always')
            result = diagram('flowchart LR\n    N0["応答処理"]\n    N1["処理"]\n    N0 --> N1')
        self.assertTrue(result)
        self.assertFalse(any('Glyph' in str(w.message) for w in caught))
