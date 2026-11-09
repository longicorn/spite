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

class StaffingComparisonTests(unittest.TestCase):
    def test_direction_and_zero_baseline(self):
        from spite.simulation.cli import staffing_comparison
        self.assertIn('10.0% lower', staffing_comparison(10, 9, 2))
        self.assertIn('10.0% higher', staffing_comparison(10, 11, 2))
        self.assertIn('approximately unchanged', staffing_comparison(10, 10, 2))
        self.assertIn('baseline P80 is zero', staffing_comparison(0, 0, 2))
        self.assertIn('sampling noise', staffing_comparison(10, 9, 2))

class PairedRandomTests(unittest.TestCase):
    def test_pairing_survives_changed_schedule_and_discovery(self):
        from spite.simulation.engine import PairedRandom
        nodes = [Node('a', 'exploratory', ()), Node('b', 'task', ()),
                 Node('review', 'gate', (0, 1))]
        serial = simulate(nodes, 1, 1, .5, 1, PairedRandom(7))
        parallel = simulate(nodes, 2, 1, .5, 1, PairedRandom(7))
        self.assertLessEqual(parallel.duration, serial.duration)
        self.assertEqual(sum('rework' in n.name for n in serial.nodes),
                         sum('rework' in n.name for n in parallel.nodes))
        self.assertEqual(serial, simulate(nodes, 1, 1, .5, 1, PairedRandom(7)))

    def test_draws_are_addressed_by_logical_event(self):
        from spite.simulation.engine import PairedRandom
        first, second = PairedRandom(99), PairedRandom(99)
        a, b = (('node', 0), 'duration', 0), (('node', 1), 'duration', 0)
        values = (first.source(a).random(), first.source(b).random())
        self.assertEqual(values, (second.source(b).random(), second.source(a).random())[::-1])
        self.assertNotEqual(values[0], values[1])

class ComplexityRiskTests(unittest.TestCase):
    def test_factor_scales_tasks_but_not_review_wait(self):
        from spite.simulation.engine import PairedRandom
        nodes = [Node('task', 'task', ()), Node('review', 'gate', (0,))]
        base = simulate(nodes, 1, 0, 0, 1, PairedRandom(42))
        risk = simulate(nodes, 1, 0, 0, 1, PairedRandom(42), complexity_risk='high')
        factor = PairedRandom(42).source(('complexity',)).triangular(1, 2, 1)
        self.assertAlmostEqual(risk.gate_time, base.gate_time)
        self.assertAlmostEqual(risk.duration - risk.gate_time, (base.duration - base.gate_time) * factor)

    def test_factor_increases_discovery_probability(self):
        from spite.simulation.engine import PairedRandom
        nodes = [Node('explore', 'exploratory', ())]
        seed = next(i for i in range(1000) if .5 < PairedRandom(i).source((('node', 0), 'discovery')).random() < min(1, .5 * PairedRandom(i).source(('complexity',)).triangular(1, 2, 1)))
        base = simulate(nodes, 1, .5, 0, 1, PairedRandom(seed))
        risk = simulate(nodes, 1, .5, 0, 1, PairedRandom(seed), complexity_risk='high')
        self.assertEqual(len(base.nodes), 1)
        self.assertEqual(len(risk.nodes), 2)

    def test_off_preserves_random_stream(self):
        nodes = generate('complex', 'small')
        self.assertEqual(simulate(nodes, 2, .3, .15, 1, random.Random(4)),
                         simulate(nodes, 2, .3, .15, 1, random.Random(4), complexity_risk='off'))

    def test_saved_risk_is_inherited_and_can_be_disabled(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from spite.cli import main
        with tempfile.TemporaryDirectory() as root:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(['simulate', '--output', root, '--iterations', '2', '--seed', '1', '--complexity-risk', 'high'])
            run_id = output.getvalue().split('Run ID: ')[1].splitlines()[0]
            for options, expected in [([], 'high'), (['--complexity-risk', 'off'], 'off')]:
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    main(['simulate', '--output', root, '--continue-from', run_id, '--elapsed-periods', '1', '--completed-tasks', '1', '--remaining-tasks', '2', *options])
                child = output.getvalue().split('Run ID: ')[1].splitlines()[0]
                snapshot = json.loads((Path(root) / 'simulate' / child / 'snapshot.json').read_text())
                self.assertEqual(snapshot['config']['complexity_risk'], expected)

class TopologyVariationTests(unittest.TestCase):
    def test_complex_variation_is_reproducible_acyclic_and_connected(self):
        for pattern in ('complex', 'exploratory'):
            graphs = [generate(pattern, 'small', topology_rng=random.Random(seed)) for seed in range(8)]
            self.assertEqual(graphs[0], generate(pattern, 'small', topology_rng=random.Random(0)))
            self.assertGreater(len({tuple(graph) for graph in graphs}), 1)
            for nodes in graphs:
                self.assertTrue(all(dep < i for i, node in enumerate(nodes) for dep in node.deps))
                used = {dep for node in nodes[:-1] for dep in node.deps}
                self.assertEqual(set(nodes[-1].deps), set(range(len(nodes) - 1)) - used)

    def test_linear_and_parallel_stay_fixed(self):
        for pattern in ('linear', 'parallel'):
            self.assertEqual(generate(pattern, 'small'), generate(pattern, 'small', topology_rng=random.Random(1)))

    def test_seeded_report_reproducible_and_variation_inherited(self):
        import contextlib
        import io
        import json
        import tempfile
        from pathlib import Path
        from spite.cli import main
        with tempfile.TemporaryDirectory() as root:
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(['simulate', '--output', root, '--iterations', '3', '--seed', '5', '--topology-variation', 'random'])
            run_id = output.getvalue().split('Run ID: ')[1].splitlines()[0]
            path = Path(root) / 'simulate' / run_id
            data = json.loads((path / 'snapshot.json').read_text())
            self.assertEqual(data['config']['topology_variation'], 'random')
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                main(['simulate', '--output', root, '--continue-from', run_id, '--elapsed-periods', '1', '--completed-tasks', '1', '--remaining-tasks', '5'])
            child = output.getvalue().split('Run ID: ')[1].splitlines()[0]
            data = json.loads((Path(root) / 'simulate' / child / 'snapshot.json').read_text())
            self.assertEqual(data['config']['topology_variation'], 'random')
