"""Command-line interface for probabilistic forecasts."""
from __future__ import annotations

import argparse
import math
from pathlib import Path
from .lognormal import percentile_days
from .params import DEFAULT_BEST_FACTOR, DEFAULT_SIGMA, DEFAULT_WORST_FACTOR, params_from_mode_and_sigma
from .render import render_ascii, render_matplotlib, render_markdown
from .units import positive_float


def _build_parser():
    parser = argparse.ArgumentParser(prog='spite', description='Software delivery forecasting using probability distributions')
    subs = parser.add_subparsers(dest='command')
    predict = subs.add_parser('predict', help='Forecast three scenarios from an expected period')
    predict.add_argument('--distribution', '-d', choices=['lognormal'], default='lognormal')
    predict.add_argument('--periods', type=positive_float, required=True, help='Nominal scenario mode in periods')
    predict.add_argument('--actual-periods', type=float, help='Actual completion duration in periods')
    predict.add_argument('--days-per-period', type=positive_float, help='Optional approximate days per period')
    predict.add_argument('--best-factor', type=float, default=DEFAULT_BEST_FACTOR)
    predict.add_argument('--worst-factor', type=float, default=DEFAULT_WORST_FACTOR)
    predict.add_argument('--sigma', type=float, default=DEFAULT_SIGMA)
    predict.add_argument('--format', choices=['terminal', 'markdown'], default='terminal')
    predict.add_argument('--output', '-o', help='Destination for image or Markdown report')
    predict.add_argument('--show', action='store_true', help='Show the chart in a window')
    from .simulation.cli import configure
    configure(subs)
    return parser, predict


def main(argv=None):
    parser, predict_parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == 'simulate':
        from .simulation.cli import run
        return run(args, parser)
    if args.command != 'predict':
        parser.print_help()
        return 0
    if not 0 < args.best_factor < 1:
        predict_parser.error('--best-factor must be greater than 0 and less than 1')
    if not math.isfinite(args.worst_factor) or args.worst_factor <= 1:
        predict_parser.error('--worst-factor must be finite and greater than 1')
    if args.actual_periods is not None and (not math.isfinite(args.actual_periods) or args.actual_periods < 0):
        predict_parser.error('--actual-periods must be finite and non-negative')
    if args.format == 'markdown' and args.show:
        predict_parser.error('--show cannot be combined with --format markdown')
    scenarios = {}
    for name, factor in [('Best', args.best_factor), ('Nominal', 1), ('Worst', args.worst_factor)]:
        try:
            params = params_from_mode_and_sigma(args.periods * factor, args.sigma)
        except ValueError as exc:
            predict_parser.error(str(exc))
        scenarios[name] = (params, {label: percentile_days(params, q) for label, q in [('p50', .5), ('p80', .8), ('p90', .9)]})
    report = render_markdown(scenarios, periods=args.periods, best_factor=args.best_factor,
                             worst_factor=args.worst_factor, actual_periods=args.actual_periods,
                             days_per_period=args.days_per_period)
    if args.format == 'markdown':
        if args.output:
            Path(args.output).write_text(report, encoding='utf-8')
        else:
            print(report, end='')
    else:
        print(report.split('## Completion distribution')[0], end='')
        if args.actual_periods is not None:
            print('\n## Retrospective (Nominal)' + report.split('## Retrospective (Nominal)')[1], end='')
        if args.output or args.show:
            render_matplotlib(scenarios, actual_periods=args.actual_periods, days_per_period=args.days_per_period, output_path=args.output, show=args.show)
        else:
            print(render_ascii(scenarios, actual_periods=args.actual_periods))
    return 0
