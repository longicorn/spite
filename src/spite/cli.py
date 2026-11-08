"""spite predict のコマンドラインインターフェース。"""

from __future__ import annotations

import argparse
import math
from datetime import date, datetime

from .businessdays import add_business_days, business_days_between
from .lognormal import (
    completion_probability,
    percentile_days,
    remaining_probability,
    summary_stats,
)
from .params import (
    DEFAULT_BEST_FACTOR,
    DEFAULT_SIGMA,
    DEFAULT_WORST_FACTOR,
    LogNormalParams,
    params_from_mode_and_sigma,
)
from .render import render_ascii, render_matplotlib, render_markdown

PERCENTILE_TARGETS: tuple[tuple[str, float], ...] = (
    ("p50", 0.50),
    ("p80", 0.80),
    ("p90", 0.90),
)


def _build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        prog="spite",
        description="Software delivery forecasting using probability distributions",
    )
    subparsers = parser.add_subparsers(dest="command")
    predict = subparsers.add_parser(
        "predict",
        help="Forecast delivery using Best, Nominal, and Worst scenarios",
        description="Forecast three scenarios from a target deadline",
    )
    predict.add_argument(
        "--distribution", "-d", choices=["lognormal"], default="lognormal"
    )
    predict.add_argument("--start-date", required=True, help="Project start date (YYYY-MM-DD)")
    predict.add_argument(
        "--deadline",
        required=True,
        help="Target deadline, the Nominal scenario mode (YYYY-MM-DD)",
    )
    predict.add_argument(
        "--actual-end-date",
        help="Actual completion date (YYYY-MM-DD) for retrospective evaluation",
    )
    predict.add_argument(
        "--best-factor",
        type=float,
        default=DEFAULT_BEST_FACTOR,
        help=f"Best mode multiplier (default: {DEFAULT_BEST_FACTOR:g})",
    )
    predict.add_argument(
        "--worst-factor",
        type=float,
        default=DEFAULT_WORST_FACTOR,
        help=f"Worst mode multiplier (default: {DEFAULT_WORST_FACTOR:g})",
    )
    predict.add_argument(
        "--sigma",
        type=float,
        default=DEFAULT_SIGMA,
        help=f"Distribution width for all scenarios (default: {DEFAULT_SIGMA:g})",
    )
    predict.add_argument("--format", choices=["terminal", "markdown"], default="terminal", help="Output format (default: terminal)")
    predict.add_argument("--output", "-o", help="Destination for the image or Markdown report")
    predict.add_argument("--show", action="store_true", help="Show the chart in a window")
    from .simulation.cli import configure
    configure(subparsers)
    return parser, predict


def _parse_date(value: str, option_name: str, error) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        error(f"{option_name} must be in YYYY-MM-DD format: {value!r}")
        raise


def _build_scenarios(args: argparse.Namespace, start_date: date, error):
    deadline = _parse_date(args.deadline, "--deadline", error)
    normal_days = business_days_between(start_date, deadline)
    if normal_days <= 0:
        error("--deadline must be after the start date with at least one business day")
    if not 0 < args.best_factor < 1:
        error("--best-factor must be greater than 0 and less than 1")
    if not math.isfinite(args.worst_factor) or args.worst_factor <= 1:
        error("--worst-factor must be finite and greater than 1")

    scenarios: dict[str, tuple[LogNormalParams, dict[str, float]]] = {}
    for name, factor in (
        ("Best", args.best_factor),
        ("Nominal", 1.0),
        ("Worst", args.worst_factor),
    ):
        mode_days = normal_days * factor
        try:
            params = params_from_mode_and_sigma(mode_days, args.sigma)
        except ValueError as exc:
            error(str(exc))
            raise
        percentiles = {
            label: percentile_days(params, q) for label, q in PERCENTILE_TARGETS
        }
        scenarios[name] = (params, percentiles)
    return scenarios


def _actual_deviation_sentence(difference: int, planned_days: int) -> str:
    difference_percent = difference / planned_days * 100
    if difference > 0:
        return (
            f"Completed {difference} business days "
            f"({difference_percent:.1f}%) after the deadline."
        )
    if difference < 0:
        return (
            f"Completed {abs(difference)} business days "
            f"({abs(difference_percent):.1f}%) before the deadline."
        )
    return "Completed on the deadline."


def _print_report(
    start_date: date,
    deadline: date,
    scenarios,
    actual_end_date: date | None = None,
) -> int | None:
    print(f"Start date: {start_date.isoformat()}")
    print(f"Deadline (Nominal scenario mode): {deadline.isoformat()}")
    for name, (params, percentiles) in scenarios.items():
        stats = summary_stats(params)
        print(f"\n{name} scenario (mode: {stats['mode']:.1f} business days, σ={params.sigma:g})")
        for label, _q in PERCENTILE_TARGETS:
            days = percentiles[label]
            target_date = add_business_days(start_date, round(days))
            print(f"  {label.upper()}: {days:6.1f} business days -> {target_date.isoformat()}")

    if actual_end_date is None:
        return None

    actual_days = business_days_between(start_date, actual_end_date)
    normal_params, normal_percentiles = scenarios["Nominal"]
    planned_days = business_days_between(start_date, deadline)
    difference = actual_days - planned_days
    probability = completion_probability(normal_params, actual_days)
    tail_probability = remaining_probability(normal_params, actual_days)

    print("\nRetrospective (Nominal scenario)")
    print(f"Actual completion: {actual_end_date.isoformat()} ({actual_days} business days)")
    print(_actual_deviation_sentence(difference, planned_days))
    if probability > 0.999:
        print(
            "Position in Nominal scenario: > P99.9 "
            f"(probability of completing later: {tail_probability * 100:.6g}%)"
        )
    else:
        print(f"Position in Nominal scenario: P{probability * 100:.1f}")

    p90_difference = actual_days - normal_percentiles["p90"]
    if p90_difference > 0:
        print(f"Difference from P90: {p90_difference:.1f} business days late")
    elif p90_difference < 0:
        print(f"Difference from P90: {abs(p90_difference):.1f} business days early")
    else:
        print("Completed at P90")
    return actual_days


def main(argv: list[str] | None = None) -> int:
    parser, predict_parser = _build_parser()
    args = parser.parse_args(argv)
    if args.command == "simulate":
        from .simulation.cli import run
        return run(args, parser)
    if args.command != "predict":
        parser.print_help()
        return 0
    start_date = _parse_date(args.start_date, "--start-date", predict_parser.error)
    deadline = _parse_date(args.deadline, "--deadline", predict_parser.error)
    actual_end_date = (
        _parse_date(args.actual_end_date, "--actual-end-date", predict_parser.error)
        if args.actual_end_date is not None
        else None
    )
    if actual_end_date is not None and actual_end_date < start_date:
        predict_parser.error("--actual-end-date must be on or after the start date")
    scenarios = _build_scenarios(args, start_date, predict_parser.error)
    if args.format == "markdown":
        if args.show:
            predict_parser.error("--show cannot be combined with --format markdown")
        report = render_markdown(scenarios, start_date=start_date, deadline=deadline,
                                 best_factor=args.best_factor, worst_factor=args.worst_factor,
                                 actual_end_date=actual_end_date)
        if args.output:
            from pathlib import Path
            Path(args.output).write_text(report, encoding="utf-8")
        else:
            print(report, end="")
        return 0
    actual_days = _print_report(start_date, deadline, scenarios, actual_end_date)
    actual_summary = None
    if actual_days is not None:
        planned_days = business_days_between(start_date, deadline)
        actual_summary = _actual_deviation_sentence(
            actual_days - planned_days, planned_days
        )

    if args.output or args.show:
        render_matplotlib(
            scenarios,
            start_date=start_date,
            actual_days=actual_days,
            actual_summary=actual_summary,
            output_path=args.output,
            show=args.show,
        )
    else:
        print()
        print(render_ascii(scenarios, actual_days=actual_days))
    return 0
