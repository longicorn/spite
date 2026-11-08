"""Render lognormal forecasts in terminal, Markdown, and image formats."""
import math
import numpy as np
from .lognormal import pdf, completion_probability, remaining_probability
from .units import duration

COLORS = {'Best': 'tab:green', 'Nominal': 'tab:blue', 'Worst': 'tab:red'}


def render_ascii(scenarios, *, actual_periods=None, width=48, bins=24):
    upper = max(max(p.values()) for _, p in scenarios.values()) * 1.5
    if actual_periods is not None:
        upper = max(upper, actual_periods * 1.05)
    xs = np.linspace(upper / bins, upper, bins)
    densities = {name: pdf(params, xs) for name, (params, _) in scenarios.items()}
    maximum = max(float(values.max()) for values in densities.values()) or 1
    symbols = {'Best': '#', 'Nominal': '+', 'Worst': '.'}
    actual_idx = int(np.abs(xs - actual_periods).argmin()) if actual_periods is not None else None
    lines = ['Legend: # Best  + Nominal  . Worst']
    for i, x in enumerate(xs):
        bars = [symbols[name] * round(float(values[i]) / maximum * width) for name, values in densities.items()]
        lines.append(f'{x:6.1f} periods | ' + ' | '.join(bars) + (f'  ^ Actual: {actual_periods:g} periods' if i == actual_idx else ''))
    return '\n'.join(lines)


def render_matplotlib(scenarios, *, actual_periods=None, days_per_period=None, output_path=None, show=False):
    import matplotlib
    if not show:
        matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, (ax, table_ax) = plt.subplots(2, 1, figsize=(9, 7), gridspec_kw={'height_ratios': [4, 1]}, layout='constrained')
    upper = max(max(p.values()) for _, p in scenarios.values()) * 1.5
    if actual_periods is not None:
        upper = max(upper, actual_periods * 1.05)
    xs = np.linspace(0, upper, 600)
    for name, (params, percentiles) in scenarios.items():
        ax.plot(xs, pdf(params, xs), label=name, color=COLORS[name])
        for label, value in percentiles.items():
            ax.axvline(value, linestyle='--', alpha=.45, color=COLORS[name])
            ax.text(value, .96, label.upper(), rotation=90, va='top', color=COLORS[name], transform=ax.get_xaxis_transform(), fontsize=8)
    if actual_periods is not None:
        ax.axvline(actual_periods, color='black', linestyle='-.', label=f'Actual: {actual_periods:g} periods')
    ax.set(xlim=(0, upper), xlabel='Periods', ylabel='Probability density', title='Delivery forecast (lognormal)')
    ax.legend()
    table_ax.axis('off')
    cells = [[name] + [duration(v, days_per_period) for v in percentiles.values()] for name, (_, percentiles) in scenarios.items()]
    table = table_ax.table(cellText=cells, colLabels=['Scenario', 'P50', 'P80', 'P90'], cellLoc='center', bbox=[0, 0, 1, 1])
    table.auto_set_font_size(False)
    table.set_fontsize(8)
    if output_path:
        fig.savefig(output_path)
    if show:
        plt.show()
    plt.close(fig)


def render_markdown(scenarios, *, periods, best_factor, worst_factor, actual_periods=None, days_per_period=None):
    sigma = next(iter(scenarios.values()))[0].sigma
    lines = ['# Delivery forecast', '', f'Nominal mode: {periods:g} periods; distribution: lognormal; sigma: {sigma:g}; best factor: {best_factor:g}; worst factor: {worst_factor:g}', '']
    if days_per_period is not None:
        lines += [f'Approximate conversion: 1 period = {days_per_period:g} days; conversions use unrounded values and no calendar or holidays are applied.', '']
    lines += ['| Scenario | P50 | P80 | P90 |', '| --- | --- | --- | --- |']
    for name, (_, percentiles) in scenarios.items():
        lines.append(f'| {name} | ' + ' | '.join(duration(value, days_per_period) for value in percentiles.values()) + ' |')
    upper = max(max(p.values()) for _, p in scenarios.values()) * 1.5
    if actual_periods is not None:
        upper = max(upper, actual_periods * 1.05)
    upper = max(1, math.ceil(upper))
    xs = np.linspace(0, upper, 61)
    curves = [pdf(params, xs) for params, _ in scenarios.values()]
    ceiling = max(.001, math.ceil(max(float(c.max()) for c in curves) * 1100) / 1000)
    lines += ['', '## Completion distribution', '', 'Lognormal probability density. Best: green; Nominal: blue; Worst: red.', '', '```mermaid', "%%{init: {'theme': 'base', 'themeVariables': {'xyChart': {'plotColorPalette': '#2e8b57, #3266cc, #d64b40'}}}}%%", 'xychart-beta', '    title "Completion time by scenario"', f'    x-axis "Periods" 0 --> {upper}', f'    y-axis "Probability density" 0 --> {ceiling:g}']
    for curve in curves:
        lines.append('    line [' + ', '.join(f'{v:.6f}' for v in curve) + ']')
    lines.append('```')
    if actual_periods is not None:
        params, percentiles = scenarios['Nominal']
        probability = completion_probability(params, actual_periods)
        tail = remaining_probability(params, actual_periods)
        difference = actual_periods - periods
        rank = f'> P99.9 (probability of completing later: {tail * 100:.6g}%)' if probability > .999 else f'P{probability * 100:.1f}'
        lines += ['', '## Retrospective (Nominal)', '', f'- Actual completion: {duration(actual_periods, days_per_period)}', f'- Difference from nominal mode: {difference:+.1f} periods ({difference / periods * 100:+.1f}%)', f'- Position in forecast: {rank}', f'- Difference from P90: {actual_periods - percentiles["p90"]:+.1f} periods']
    return '\n'.join(lines) + '\n'
