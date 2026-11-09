"""CLI and reports for structural simulation."""
import math
import random
import secrets
import statistics
import sys
from pathlib import Path
from ..units import duration, positive_float
from ..storage import load_run, save_run
from .engine import PairedRandom, generate, simulate


def configure(subparsers):
    p = subparsers.add_parser('simulate', help='Structural Monte Carlo forecasting')
    p.add_argument('--tasks-per-period', type=positive_float, default=None, help='Reference tasks per period per team member; task duration mode is its reciprocal (default: 1)')
    p.add_argument('--days-per-period', type=positive_float, help='Optional approximate days per period')
    p.add_argument('--pattern', choices=['linear', 'parallel', 'complex', 'exploratory'], default=None)
    p.add_argument('--scale', choices=['small', 'medium', 'large'], default=None)
    p.add_argument('--uncertainty', choices=['low', 'medium', 'high'], default=None)
    p.add_argument('--rework-rate', type=float, default=None)
    p.add_argument('--team-size', type=int, default=None)
    p.add_argument('--iterations', type=int, default=None)
    p.add_argument('--format', choices=['markdown', 'terminal', 'png'], default='markdown')
    p.add_argument('--output', help='Root directory for stored runs')
    p.add_argument('--continue-from', help='Prior simulation run ID under --output')
    p.add_argument('--elapsed-periods', type=float, help='Total elapsed periods since project start')
    p.add_argument('--completed-tasks', type=int, help='Total completed tasks so far')
    p.add_argument('--remaining-tasks', type=int, help='Known remaining tasks for a new synthetic graph')
    p.add_argument('--seed', type=int)
    p.add_argument('--topology', help='YAML topology file')
    p.add_argument('--template', action='store_true', help='Print a YAML template')
    p.add_argument('--from-git', metavar='BASE', help='Print a YAML draft from BASE..HEAD')
    return p


def percentile(values, q):
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def distribution_chart(samples):
    """Render smoothed empirical densities using a common period axis."""
    upper = max(max(values) for values in samples.values())
    upper = max(1, math.ceil(upper * 1.05))
    points = 61
    xs = [upper * i / (points - 1) for i in range(points)]
    curves = []
    for values in samples.values():
        # Gaussian kernel density estimate, with a floor for one or identical samples.
        spread = statistics.pstdev(values)
        bandwidth = max(1.06 * spread * len(values) ** (-.2), upper / 100)
        norm = len(values) * bandwidth * math.sqrt(2 * math.pi)
        curves.append([sum(math.exp(-.5 * ((x - v) / bandwidth) ** 2)
                           for v in values) / norm for x in xs])
    maximum = max(max(curve) for curve in curves)
    ceiling = max(.001, math.ceil(maximum * 1000 * 1.1) / 1000)
    lines = [
        '## Completion distribution', '',
        'Smoothed empirical density from each scenario’s simulation samples; '
        'the curves are estimates, not fitted lognormal distributions. '
        'Best: green; Nominal: blue; Worst: red. '
        'Smoothing can extend slightly outside the observed sample range.', '',
        '```mermaid',
        "%%{init: {'theme': 'base', 'themeVariables': {'xyChart': {'plotColorPalette': '#2e8b57, #3266cc, #d64b40'}}}}%%",
        'xychart-beta',
        '    title "Completion time by scenario"',
        f'    x-axis "Periods" 0 --> {upper}',
        f'    y-axis "Estimated density" 0 --> {ceiling:g}',
    ]
    for curve in curves:
        lines.append('    line [' + ', '.join(f'{value:.6f}' for value in curve) + ']')
    return lines + ['```']


def staffing_comparison(baseline, doubled, team_size):
    """Describe a difference between independently estimated P80 values."""
    if baseline == 0:
        difference = 'percentage change is unavailable because the baseline P80 is zero'
    else:
        change = (doubled - baseline) / baseline * 100
        if abs(change) < .05:
            difference = 'P80 is approximately unchanged'
        else:
            difference = f'P80 is estimated to be {abs(change):.1f}% {"higher" if change > 0 else "lower"}'
    return (f'Nominal staffing sensitivity: doubling team size to {team_size * 2}: {difference}. '
            'Trials use shared task-level random draws; small differences may still be sampling noise.')


def run(args, parser):
    from .topology import dump, git_draft, load, template
    if args.template or args.from_git:
        if args.template and args.from_git or args.topology or args.continue_from:
            parser.error('Template and Git draft modes cannot be combined with topology or continuation')
        try:
            print(dump(template() if args.template else git_draft(args.from_git)), end='')
        except ValueError as exc:
            parser.error(str(exc))
        return 0
    topology = None
    if args.topology:
        if args.continue_from:
            parser.error('--topology cannot be combined with --continue-from; update the YAML to revise the forecast')
        ignored = [name for name in ('pattern', 'scale') if getattr(args, name) is not None]
        if ignored:
            print('warning: --topology ignores ' + ', '.join('--' + name for name in ignored), file=sys.stderr)
            for name in ignored:
                setattr(args, name, None)
        try:
            topology, topology_elapsed, topology_completed = load(args.topology)
        except ValueError as exc:
            parser.error(f'Invalid YAML topology {args.topology!r}: {exc}')
    parent = None
    if args.continue_from:
        if not args.output:
            parser.error('--continue-from requires --output')
        try:
            parent = load_run(args.output, args.continue_from, 'simulate')
        except ValueError as exc:
            parser.error(str(exc))
        if parent.get('topology_input'):
            parser.error('YAML topology runs cannot be continued with --continue-from; update the YAML instead')
        if args.elapsed_periods is None or args.completed_tasks is None or args.remaining_tasks is None:
            parser.error('--continue-from requires --elapsed-periods, --completed-tasks and --remaining-tasks')
        if not isinstance(parent.get('config'), dict) or not isinstance(parent.get('summary'), dict) or any(not isinstance(parent['summary'].get(name, {}).get('total', {}).get(label), (int, float)) for name in ('Best', 'Nominal', 'Worst') for label in ('p50', 'p80', 'p90')):
            parser.error('Snapshot is missing simulation configuration or summary')
        prior = parent.get('progress') or {}
        if args.elapsed_periods < prior.get('elapsed_periods', 0) or args.completed_tasks < prior.get('completed_tasks', 0):
            parser.error('elapsed periods and completed tasks cannot decrease from the previous run')
    elif any(v is not None for v in (args.elapsed_periods, args.completed_tasks, args.remaining_tasks)):
        parser.error('progress inputs require --continue-from')
    if args.elapsed_periods is not None and (not math.isfinite(args.elapsed_periods) or args.elapsed_periods < 0):
        parser.error('--elapsed-periods must be finite and non-negative')
    if args.completed_tasks is not None and (args.completed_tasks < 0 or args.remaining_tasks < 0):
        parser.error('task counts must be non-negative')
    defaults = {'tasks_per_period': 1.0, 'days_per_period': None, 'pattern': 'complex', 'scale': 'medium', 'uncertainty': 'medium', 'rework_rate': .15, 'team_size': 2, 'iterations': 2000}
    for key, default in defaults.items():
        if getattr(args, key) is None:
            setattr(args, key, parent['config'].get(key, default) if parent else default)
    if args.seed is None:
        args.seed = secrets.randbits(64)
    if args.team_size < 1 or args.iterations < 1:
        parser.error('--team-size and --iterations must be positive')
    if not math.isfinite(args.rework_rate) or not 0 <= args.rework_rate <= 1:
        parser.error('--rework-rate must be between 0 and 1')
    if args.format == 'png' and not args.output:
        parser.error('--format png requires --output')
    task_periods = 1.0 / args.tasks_per_period
    if not math.isfinite(task_periods) or task_periods == 0:
        parser.error('--tasks-per-period must have a finite, nonzero reciprocal')
    rng = random.Random(args.seed)
    discovery = {'low': .1, 'medium': .3, 'high': .5}[args.uncertainty]
    paired_seeds = [random.Random(f"{args.seed}:staffing:{i}").getrandbits(128) for i in range(args.iterations)]
    rows, samples = [], {}
    representative = None
    for name, disc, rw, gf in [('Best', discovery * .5, min(args.rework_rate * .25, .049), .6), ('Nominal', discovery, args.rework_rate, 1), ('Worst', min(1, discovery * 1.5), min(1, max(.25, args.rework_rate * 1.5)), 1.5)]:
        results = [simulate(topology if topology is not None else generate(args.pattern, args.scale, args.remaining_tasks), args.team_size, disc, rw, gf, PairedRandom(paired_seeds[i]) if name == 'Nominal' else rng, task_periods=task_periods) for i in range(args.iterations)]
        values = sorted(result.duration for result in results)
        samples[name] = values
        if name == 'Nominal':
            median = percentile(values, .5)
            representative = min(results, key=lambda result: abs(result.duration - median))
        metrics = [percentile(values, q) for q in (.5, .8, .9)]
        cells = [duration(x, args.days_per_period) for x in metrics]
        rows.append(f'| {name} | ' + ' | '.join(cells) + f' | {statistics.mean(values):.1f} | {statistics.pstdev(values):.1f} |')
    # Match logical event draws across the nominal and doubled-team trials.
    doubled = sorted(simulate(topology if topology is not None else generate(args.pattern, args.scale, args.remaining_tasks), args.team_size * 2, discovery, args.rework_rate, 1, PairedRandom(seed), task_periods=task_periods).duration for seed in paired_seeds)
    baseline = percentile(samples['Nominal'], .8)
    staffing_summary = staffing_comparison(baseline, percentile(doubled, .8), args.team_size)
    def write_png(path):
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        for name, values in samples.items():
            ax.hist(values, bins=20, alpha=.45, label=name)
        ax.set(xlabel='Periods', ylabel='Samples', title=f'Structural simulation ({args.tasks_per_period:g} reference tasks per period per member)' + (f' (1 period ≈ {args.days_per_period:g} days)' if args.days_per_period is not None else ''))
        ax.legend()
        fig.tight_layout()
        fig.savefig(path)
        plt.close(fig)
    lines = ['# Structural simulation', '', f'{"Topology input" if topology is not None else f"Pattern: {args.pattern}; scale: {args.scale}"}; uncertainty: {args.uncertainty}; rework rate: {args.rework_rate}; team size: {args.team_size}; reference tasks per period per team member: {args.tasks_per_period:g}; task duration mode: {task_periods:g} periods; iterations per scenario: {args.iterations}; seed: {args.seed}', '', 'Reference tasks per period is the reciprocal of the task duration mode, not guaranteed throughput. Task durations follow a triangular distribution: 0.5 to 2 times the task mode, with the task mode as the most likely value. Waiting for reviews and approvals does not occupy development team slots. Rework is capped at 10 attempts per review.', '', '| Scenario | P50 | P80 | P90 | Mean | Standard deviation |', '| --- | --- | --- | --- | --- | --- |', *rows, '', staffing_summary, '', f'Representative nominal sample: {representative.duration:.1f} periods; review and approval waiting time on the displayed execution path: {representative.gate_time:.1f} periods ({(representative.gate_time / representative.duration * 100 if representative.duration else 0):.1f}% of elapsed time). Dashed edges represent resource contention; solid edges represent dependencies and rework.']
    if parent:
        elapsed = args.elapsed_periods
        lines.insert(5, 'The forecast table and distribution describe remaining time, not time since project start.')
        lines += ['', '## Progress and comparison', '', f'Elapsed: {duration(elapsed, args.days_per_period)}; completed tasks: {args.completed_tasks}; known remaining tasks: {args.remaining_tasks}.', 'A new synthetic graph is generated for the remaining tasks. Completed task identities, dependencies, and work in progress are unknown; this is not a continuation of the previous simulated graph.', '', '| Scenario | Percentile | Previous total | Remaining | Updated total |', '| --- | --- | --- | --- | --- |']
        for name, values in samples.items():
            for label, q in (('p50', .5), ('p80', .8), ('p90', .9)):
                previous = parent['summary'][name]['total'][label]
                current = percentile(values, q)
                lines.append(f'| {name} | {label.upper()} | {duration(previous, args.days_per_period)} | {duration(current, args.days_per_period)} | {duration(elapsed + current, args.days_per_period)} |')
    if topology is not None:
        lines.insert(2, f'Topology: {args.topology}; completed tasks: {topology_completed}; pending tasks: {len(topology)}; elapsed: {duration(topology_elapsed, args.days_per_period)}. The forecast table and distribution describe remaining time.')
        lines += ['', '## Total forecast', '', '| Scenario | P50 | P80 | P90 |', '| --- | --- | --- | --- |']
        for name, values in samples.items():
            lines.append(f'| {name} | ' + ' | '.join(duration(topology_elapsed + percentile(values, q), args.days_per_period) for q in (.5, .8, .9)) + ' |')
    if args.days_per_period is not None:
        lines.insert(3, f'Approximate conversion: 1 period = {args.days_per_period:g} days; conversions use unrounded values and no calendar or holidays are applied.')
    values = samples['Nominal']
    p50, p80, p90 = (duration(percentile(values, q), args.days_per_period) for q in (.5, .8, .9))
    lines += ['', '## What the nominal forecast means', '',
              f'In the Nominal scenario, about 50% of simulated projects finished within {p50}, '
              f'80% within {p80}, and 90% within {p90}.', '',
              'These results depend on the assumptions used in the simulation and do not guarantee actual completion times.']
    if args.format == 'markdown' or args.output:
        lines += ['', *distribution_chart(samples)]
    if (args.format == 'markdown' or args.output) and representative.nodes:
        lines += ['', '## Representative topology', '', '```mermaid', 'flowchart LR']
        for i, node in enumerate(representative.nodes):
            safe_name = node.name.replace('&', '&amp;').replace('\"', '&quot;').replace('\n', ' ')
            lines.append(f'    N{i}["{safe_name}"]')
            for dep in node.deps:
                lines.append(f'    N{dep} {"-.->" if (dep, i) in representative.resource_edges else "-->"} N{i}')
            if node.kind == 'gate':
                lines.append(f'    class N{i} review')
            if i in representative.critical_path:
                lines.append(f'    class N{i} critical')
        lines += ['    classDef review fill:#ffe4a3,stroke:#b76e00', '    classDef critical stroke:#e74c3c,stroke-width:3px', '```']
    report = '\n'.join(lines) + '\n'
    if args.output:
        elapsed = topology_elapsed if topology is not None else (args.elapsed_periods or 0)
        config = {key: getattr(args, key) for key in defaults}
        summary = {name: {'remaining': {f'p{int(q*100)}': percentile(values, q) for q in (.5, .8, .9)},
                          'total': {f'p{int(q*100)}': elapsed + percentile(values, q) for q in (.5, .8, .9)}} for name, values in samples.items()}
        snapshot = {'topology_input': topology is not None, 'parent_run_id': args.continue_from, 'config': config, 'seed': args.seed,
                    'progress': {'elapsed_periods': elapsed, 'completed_tasks': topology_completed if topology is not None else (args.completed_tasks or 0),
                                 'remaining_tasks': len(topology) if topology is not None else args.remaining_tasks},
                    'samples': samples, 'summary': summary,
                    'representative': {'duration': representative.duration, 'gate_time': representative.gate_time,
                        'nodes': [vars(node) for node in representative.nodes], 'critical_path': representative.critical_path,
                        'resource_edges': representative.resource_edges}}
        try:
            path, run_id = save_run(args.output, 'simulate', snapshot, report, write_png if args.format == 'png' else None)
        except (OSError, ValueError) as exc:
            parser.error(f'Cannot save run: {exc}')
        print(f'Run ID: {run_id}\nReport: {path / "report.md"}\nSnapshot: {path / "snapshot.json"}')
        if args.format == 'png':
            print(f'Chart: {path / "chart.png"}')
    else:
        print(report, end='')
    return 0
