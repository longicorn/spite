"""Period formatting and optional approximate day conversion."""
import argparse
import math


def positive_float(value):
    try:
        number = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError('must be a finite positive number') from exc
    if not math.isfinite(number) or number <= 0:
        raise argparse.ArgumentTypeError('must be a finite positive number')
    return number


def duration(value, days_per_period=None):
    text = f'{value:.1f} periods'
    if days_per_period is not None:
        text += f' (approx. {value * days_per_period:.1f} days)'
    return text
