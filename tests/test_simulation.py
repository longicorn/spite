import random
import unittest
from spite.simulation.engine import Node, generate, simulate
from spite.simulation.cli import distribution_chart, percentile


class SimulationTests(unittest.TestCase):
    def test_parallel_respects_team_capacity(self):
        nodes = [Node('a', 'task', ()), Node('b', 'task', ())]
        serial = simulate(nodes, 1, 0, 0, 1, random.Random(7))
        parallel = simulate(nodes, 2, 0, 0, 1, random.Random(7))
        self.assertGreater(serial.duration, parallel.duration)

    def test_task_mode_scales_task_and_discovery_durations(self):
        nodes = [Node('explore', 'exploratory', ())]
        baseline = simulate(nodes, 1, 1, 0, 1, random.Random(4), task_periods=1)
        faster = simulate(nodes, 1, 1, 0, 1, random.Random(4), task_periods=.2)
        self.assertAlmostEqual(faster.duration, baseline.duration * .2)

    def test_rework_duration_uses_task_mode(self):
        nodes = [Node('work', 'task', ()), Node('review', 'gate', (0,))]
        full = simulate(nodes, 1, 0, 1, 1, random.Random(4), task_periods=1)
        short = simulate(nodes, 1, 0, 1, 1, random.Random(4), task_periods=.2)
        self.assertEqual(len(full.nodes), len(short.nodes))
        self.assertAlmostEqual(short.gate_time, full.gate_time)
        self.assertAlmostEqual(short.duration - short.gate_time, (full.duration - full.gate_time) * .2)

    def test_task_mode_does_not_change_review_wait(self):
        nodes = [Node('review', 'gate', ())]
        baseline = simulate(nodes, 1, 0, 0, 1, random.Random(4), task_periods=1)
        faster = simulate(nodes, 1, 0, 0, 1, random.Random(4), task_periods=.2)
        self.assertEqual(baseline.duration, faster.duration)

    def test_discovery_blocks_successors(self):
        nodes = [Node('explore', 'exploratory', ()), Node('finish', 'task', (0,))]
        result = simulate(nodes, 1, 1, 0, 1, random.Random(4))
        self.assertEqual([node.name for node in result.nodes], ['explore', 'Discovery 0', 'finish'])
        self.assertIn(1, result.nodes[2].deps)
        self.assertEqual(result.critical_path, [0, 1, 2])

    def test_rework_is_bounded_at_certain_rejection(self):
        nodes = [Node('work', 'task', ()), Node('gate', 'gate', (0,))]
        result = simulate(nodes, 1, 0, 1, 1, random.Random(4))
        self.assertEqual(len(result.nodes), 22)
        self.assertEqual(sum('work (rework' in n.name for n in result.nodes), 10)
        self.assertTrue(all(dep != i for i, node in enumerate(result.nodes) for dep in node.deps))

    def test_resource_wait_is_in_critical_path(self):
        nodes = [Node('a', 'task', ()), Node('b', 'task', ())]
        result = simulate(nodes, 1, 0, 0, 1, random.Random(7))
        self.assertEqual(result.critical_path, [0, 1])
        self.assertEqual(result.resource_edges, [(0, 1)])

    def test_seed_reproducibility_and_patterns(self):
        for pattern in ('linear', 'parallel', 'complex', 'exploratory'):
            a = simulate(generate(pattern, 'small'), 2, .3, .15, 1, random.Random(17))
            b = simulate(generate(pattern, 'small'), 2, .3, .15, 1, random.Random(17))
            self.assertEqual(a, b)

    def test_distribution_chart_uses_three_sample_distributions(self):
        samples = {'Best': [2, 3, 4], 'Nominal': [4, 5, 6], 'Worst': [7, 8, 9]}
        chart = distribution_chart(samples)
        curves = [line for line in chart if line.startswith('    line [')]
        self.assertEqual(len(curves), 3)
        self.assertEqual(len(set(curves)), 3)
        self.assertIn('    x-axis "Periods" 0 --> 10', chart)

    def test_distribution_chart_accepts_single_identical_samples(self):
        chart = distribution_chart({name: [3] for name in ('Best', 'Nominal', 'Worst')})
        self.assertEqual(sum(line.startswith('    line [') for line in chart), 3)

    def test_percentile_interpolation(self):
        self.assertEqual(percentile([1, 3], .5), 2)


if __name__ == '__main__':
    unittest.main()
