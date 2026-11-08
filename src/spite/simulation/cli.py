"""CLI and reports for structural simulation."""
import math
import random
import statistics
from datetime import date
from pathlib import Path
from ..businessdays import add_business_days
from .engine import generate, simulate


def configure(subparsers):
    p = subparsers.add_parser('simulate', help='Structural Monte Carlo forecasting')
    p.add_argument('--start-date', type=date.fromisoformat, default=date.today())
    p.add_argument('--pattern', choices=['linear', 'parallel', 'complex', 'exploratory'], default='complex')
    p.add_argument('--scale', choices=['small', 'medium', 'large'], default='medium')
    p.add_argument('--uncertainty', choices=['low', 'medium', 'high'], default='medium')
    p.add_argument('--rework-rate', type=float, default=.15)
    p.add_argument('--team-size', type=int, default=2)
    p.add_argument('--iterations', type=int, default=2000)
    p.add_argument('--format', choices=['markdown', 'terminal', 'png'], default='markdown')
    p.add_argument('--output')
    p.add_argument('--seed', type=int)
    return p


def percentile(values, q):
    pos = (len(values) - 1) * q
    lo = int(pos)
    hi = min(lo + 1, len(values) - 1)
    return values[lo] + (values[hi] - values[lo]) * (pos - lo)


def distribution_chart(samples):
    """Render smoothed empirical densities using a common business-day axis."""
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
        f'    x-axis "Business days" 0 --> {upper}',
        f'    y-axis "Estimated density" 0 --> {ceiling:g}',
    ]
    for curve in curves:
        lines.append('    line [' + ', '.join(f'{value:.6f}' for value in curve) + ']')
    return lines + ['```']


def run(args, parser):
    if args.team_size < 1 or args.iterations < 1:
        parser.error('--team-size and --iterations must be positive')
    if not math.isfinite(args.rework_rate) or not 0 <= args.rework_rate <= 1:
        parser.error('--rework-rate must be between 0 and 1')
    if args.format == 'png' and not args.output:
        parser.error('--format png requires --output')
    rng = random.Random(args.seed)
    discovery = {'low': .1, 'medium': .3, 'high': .5}[args.uncertainty]
    rows, samples = [], {}
    representative = None
    for name, disc, rw, gf in [('Best', discovery * .5, min(args.rework_rate * .25, .049), .6), ('Nominal', discovery, args.rework_rate, 1), ('Worst', min(1, discovery * 1.5), min(1, max(.25, args.rework_rate * 1.5)), 1.5)]:
        results = [simulate(generate(args.pattern, args.scale), args.team_size, disc, rw, gf, rng) for _ in range(args.iterations)]
        values = sorted(result.duration for result in results)
        samples[name] = values
        if name == 'Nominal':
            median = percentile(values, .5)
            representative = min(results, key=lambda result: abs(result.duration - median))
        metrics = [percentile(values, q) for q in (.5, .8, .9)]
        cells = [f'{x:.1f} ({add_business_days(args.start_date, math.ceil(x))})' for x in metrics]
        rows.append(f'| {name} | ' + ' | '.join(cells) + f' | {statistics.mean(values):.1f} | {statistics.pstdev(values):.1f} |')
    # Independent samples for a comparative staffing estimate, with a separate reproducible RNG.
    sensitivity_rng = random.Random(args.seed)
    doubled = sorted(simulate(generate(args.pattern, args.scale), args.team_size * 2, discovery, args.rework_rate, 1, sensitivity_rng).duration for _ in range(args.iterations))
    baseline = percentile(samples['Nominal'], .8)
    change = (baseline - percentile(doubled, .8)) / baseline * 100
    if args.format == 'png':
        import matplotlib.pyplot as plt
        fig, ax = plt.subplots()
        for name, values in samples.items():
            ax.hist(values, bins=20, alpha=.45, label=name)
        ax.set(xlabel='Business days', ylabel='Samples', title='Structural simulation')
        ax.legend()
        fig.tight_layout()
        fig.savefig(args.output)
        plt.close(fig)
        return 0
    lines = ['# Structural simulation', '', f'Pattern: {args.pattern}; scale: {args.scale}; uncertainty: {args.uncertainty}; rework rate: {args.rework_rate}; team size: {args.team_size}; iterations per scenario: {args.iterations}; start: {args.start_date}; seed: {args.seed}', '', 'Durations are business days; dates round up to the next whole business day. Gates do not occupy team slots. Rework is capped at 10 attempts per gate.', '', '| Scenario | P50 | P80 | P90 | Mean | Standard deviation |', '| --- | --- | --- | --- | --- | --- |', *rows, '', f'Nominal staffing sensitivity: doubling team size to {args.team_size * 2} changes P80 by {change:+.1f}% reduction (independent Monte Carlo estimates).', '', f'Representative nominal sample: {representative.duration:.1f} days; gate wait on the displayed execution path: {representative.gate_time:.1f} days ({representative.gate_time / representative.duration * 100:.1f}% of elapsed time). Dashed edges represent resource contention; solid edges represent dependencies and rework.']
    if args.format == 'markdown':
        lines += ['', *distribution_chart(samples)]
    lines += ['', '## Nominal distribution', '']
    values = samples['Nominal']
    low, high = values[0], values[-1]
    counts = [0] * 10
    for value in values:
        counts[min(9, int((value-low)/(high-low)*10)) if high > low else 0] += 1
    for i, count in enumerate(counts):
        lines.append(f'{low+(high-low)*i/10:.1f}–{low+(high-low)*(i+1)/10:.1f}: {"#" * round(30*count/max(counts))} {count}')
    if args.format == 'markdown':
        lines += ['', '## Representative topology', '', '```mermaid', 'flowchart LR']
        for i, node in enumerate(representative.nodes):
            lines.append(f'    N{i}["{node.name}"]')
            for dep in node.deps:
                lines.append(f'    N{dep} {"-.->" if (dep, i) in representative.resource_edges else "-->"} N{i}')
            if node.kind == 'gate':
                lines.append(f'    class N{i} gate')
            if i in representative.critical_path:
                lines.append(f'    class N{i} critical')
        lines += ['    classDef gate fill:#ffe4a3,stroke:#b76e00', '    classDef critical stroke:#e74c3c,stroke-width:3px', '```']
    report = '\n'.join(lines) + '\n'
    if args.output:
        Path(args.output).write_text(report, encoding='utf-8')
    else:
        print(report, end='')
    return 0
