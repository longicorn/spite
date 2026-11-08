import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from spite.cli import main


class PredictMarkdownTests(unittest.TestCase):
    args = ['predict', '--start-date', '2024-09-10', '--deadline', '2024-09-30']

    def test_markdown_stdout_includes_scenarios_and_chart(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(main(self.args + ['--format', 'markdown']), 0)
        report = output.getvalue()
        self.assertIn('| Nominal | 18.0 (2024-10-04)', report)
        self.assertEqual(report.count('    line ['), 3)
        self.assertNotIn('## Retrospective', report)

    def test_markdown_file_includes_retrospective(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'report.md'
            with contextlib.redirect_stdout(io.StringIO()) as out:
                main(self.args + ['--format', 'markdown', '--output', str(path), '--actual-end-date', '2024-12-10'])
            self.assertEqual(out.getvalue(), '')
            report = path.read_text(encoding='utf-8')
            self.assertIn('Actual completion: 2024-12-10', report)
            self.assertIn('Difference from P90:', report)
            self.assertIn('Position in forecast:', report)

    def test_default_retains_terminal_output(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            main(self.args)
        self.assertIn('Legend:', out.getvalue())
        self.assertNotIn('```mermaid', out.getvalue())

    def test_markdown_show_is_rejected(self):
        with contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):
                main(self.args + ['--format', 'markdown', '--show'])


if __name__ == '__main__':
    unittest.main()
