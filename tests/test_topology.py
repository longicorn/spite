import tempfile
import unittest
from pathlib import Path

import yaml
from spite.simulation.topology import load, template, git_draft


class TopologyTests(unittest.TestCase):
    def read(self, data):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'input.yaml'
            path.write_text(yaml.safe_dump(data))
            return load(path)

    def test_completed_dependencies_and_unordered_tasks(self):
        data = template()
        data['elapsed_periods'] = 4
        data['tasks'][0]['status'] = 'completed'
        data['tasks'].reverse()
        nodes, elapsed, completed = self.read(data)
        self.assertEqual((elapsed, completed), (4, 1))
        self.assertEqual([(n.name, n.deps) for n in nodes], [('Build', ()), ('Review', (0,))])

    def test_invalid_graphs(self):
        data = template()
        data['tasks'][0]['depends_on'] = ['review']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            self.read(data)
        data = template()
        data['tasks'][1]['status'] = 'completed'
        with self.assertRaisesRegex(ValueError, 'completed task depends'):
            self.read(data)
        data = template()
        data['tasks'][0]['depends_on'] = ['missing']
        with self.assertRaisesRegex(ValueError, 'unknown dependency'):
            self.read(data)

    def test_git_draft_does_not_infer_dependencies(self):
        draft = git_draft('HEAD')
        self.assertEqual(draft, {'tasks': []})
        self.assertEqual(self.read(draft), ([], 0, 0))

class TopologyCliTests(unittest.TestCase):
    def invoke(self, *args):
        import subprocess
        import sys
        return subprocess.run([sys.executable, '-c', 'import sys; from spite.cli import main; sys.exit(main())', *args], capture_output=True, text=True)

    def test_yaml_error_names_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'bad.yaml'
            data = template()
            data['tasks'][0]['depends_on'] = ['missing']
            path.write_text(yaml.safe_dump(data))
            result = self.invoke('simulate', '--topology', str(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertIn('Invalid YAML topology', result.stderr)
            self.assertIn(str(path), result.stderr)
            self.assertIn('unknown dependency missing', result.stderr)

    def test_pattern_and_scale_are_ignored_with_warning(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'topology.yaml'
            path.write_text(yaml.safe_dump(template()))
            result = self.invoke('simulate', '--topology', str(path), '--pattern', 'linear', '--scale', 'small', '--iterations', '1', '--seed', '1', '--format', 'terminal')
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn('warning: --topology ignores --pattern, --scale', result.stderr)
            self.assertIn('Topology:', result.stdout)
