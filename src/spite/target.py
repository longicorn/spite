"""Shared target duration options and reporting."""
from decimal import Decimal, ROUND_HALF_UP
from .units import duration, positive_float


def configure(parser):
    group = parser.add_mutually_exclusive_group()
    group.add_argument('--target-periods', type=positive_float)
    group.add_argument('--target-days', type=positive_float)


def resolve(args, parser):
    if args.target_days is not None:
        if args.days_per_period is None:
            parser.error('--target-days requires --days-per-period')
        target = args.target_days / args.days_per_period
        import math
        if not math.isfinite(target) or target <= 0:
            parser.error('converted target duration must be finite and positive')
        return target
    return args.target_periods


def report(target, probabilities, days_per_period):
    lines = ['## Target evaluation', '', f'Target: {duration(target, days_per_period)} (total duration).', '',
             '| Scenario | Completion probability |', '| --- | --- |']
    for name, (completion, delay) in probabilities.items():
        if 0 < completion < 0.005:
            display = '<1% (delay >99%)'
        elif completion >= 0.995 and delay > 0:
            display = '>99% (delay <1%)'
        else:
            percent = int((Decimal(str(completion)) * 100).quantize(Decimal('1'), rounding=ROUND_HALF_UP))
            display = f'{percent}% (delay {100 - percent}%)'
        lines.append(f'| {name} | {display} |')
    return '\n'.join(lines) + '\n'
