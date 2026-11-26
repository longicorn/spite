import tempfile
import unittest
from pathlib import Path

import yaml
from spite.simulation.topology import load, template, git_draft


def read_topology(data):
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / 'input.yaml'
        path.write_text(yaml.safe_dump(data))
        return load(path)


class TopologyTests(unittest.TestCase):

    def test_completed_dependencies_and_unordered_tasks(self):
        data = template()
        data['elapsed_periods'] = 4
        data['tasks'][0]['status'] = 'completed'
        data['tasks'].reverse()
        nodes, elapsed, completed = read_topology(data)
        self.assertEqual((elapsed, completed), (4, 1))
        self.assertEqual([(n.name, n.deps) for n in nodes], [('Build', ()), ('Review', (0,))])

    def test_invalid_graphs(self):
        data = template()
        data['tasks'][0]['depends_on'] = ['review']
        with self.assertRaisesRegex(ValueError, 'cycle'):
            read_topology(data)
        data = template()
        data['tasks'][1]['status'] = 'completed'
        with self.assertRaisesRegex(ValueError, 'completed task depends'):
            read_topology(data)
        data = template()
        data['tasks'][0]['depends_on'] = ['missing']
        with self.assertRaisesRegex(ValueError, 'unknown dependency'):
            read_topology(data)

    def test_effort_fields_and_validation(self):
        data = template()
        data['tasks'][0]['discovery_effort'] = 2
        data['tasks'][1]['effort'] = 4
        data['tasks'][2]['rework_fraction'] = .3
        nodes, _, _ = read_topology(data)
        self.assertEqual(nodes[0].discovery_effort, 2)
        self.assertEqual(nodes[2].rework_target_effort, 4)
        self.assertEqual(nodes[2].rework_fraction, .3)
        for index, field, value in [(2, 'rework_fraction', 1.1), (1, 'discovery_effort', 2), (0, 'discovery_effort', 0), (1, 'rework_fraction', .3)]:
            bad = template()
            bad['tasks'][index][field] = value
            with self.subTest(field=field, value=value, index=index), self.assertRaises(ValueError):
                read_topology(bad)

    def test_git_draft_does_not_infer_dependencies(self):
        draft = git_draft('HEAD')
        self.assertEqual(draft, {'tasks': []})
        self.assertEqual(read_topology(draft), ([], 0, 0))

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

class ReworkTargetTests(unittest.TestCase):
    def test_explicit_rework_target_and_validation(self):
        data = template()
        nodes, _, _ = read_topology(data)
        self.assertEqual(nodes[-1].rework_target, ('Build', ()))
        data['tasks'][-1]['rework_target'] = 'missing'
        with self.assertRaisesRegex(ValueError, 'upstream'):
            read_topology(data)
        data['tasks'][-1]['rework_target'] = 'review'
        with self.assertRaisesRegex(ValueError, 'upstream'):
            read_topology(data)

    def test_completed_target_is_preserved(self):
        data = template()
        data['tasks'][0]['status'] = 'completed'
        data['tasks'][1]['status'] = 'completed'
        data['tasks'][1]['roles'] = ['dev']
        nodes, _, _ = read_topology(data)
        self.assertEqual(nodes[0].rework_target, ('Build', ('dev',)))
