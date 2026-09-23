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
from .render import render_ascii, render_matplotlib

PERCENTILE_TARGETS: tuple[tuple[str, float], ...] = (
    ("p50", 0.50),
    ("p80", 0.80),
    ("p90", 0.90),
)


def _build_parser() -> tuple[argparse.ArgumentParser, argparse.ArgumentParser]:
    parser = argparse.ArgumentParser(
        prog="spite",
        description="確率分布に基づくソフトウェア納期予測ツール",
    )
    subparsers = parser.add_subparsers(dest="command")
    predict = subparsers.add_parser(
        "predict",
        help="最善・通常・最悪の3シナリオで納期予測する",
        description="想定納期を基準に、最善・通常・最悪の3シナリオを予測する",
    )
    predict.add_argument(
        "--distribution", "-d", choices=["lognormal"], default="lognormal"
    )
    predict.add_argument("--start-date", required=True, help="開発開始日 (YYYY-MM-DD)")
    predict.add_argument(
        "--deadline",
        required=True,
        help="想定納期。通常シナリオのピークとなる日付 (YYYY-MM-DD)",
    )
    predict.add_argument(
        "--actual-end-date",
        help="実際の開発終了日 (YYYY-MM-DD)。指定すると終了済み案件として振り返る",
    )
    predict.add_argument(
        "--best-factor",
        type=float,
        default=DEFAULT_BEST_FACTOR,
        help=f"最善ピークの係数 (通常の期間に掛ける。既定値: {DEFAULT_BEST_FACTOR:g})",
    )
    predict.add_argument(
        "--worst-factor",
        type=float,
        default=DEFAULT_WORST_FACTOR,
        help=f"最悪ピークの係数 (通常の期間に掛ける。既定値: {DEFAULT_WORST_FACTOR:g})",
    )
    predict.add_argument(
        "--sigma",
        type=float,
        default=DEFAULT_SIGMA,
        help=f"各シナリオ共通の分布の幅 (既定値: {DEFAULT_SIGMA:g})",
    )
    predict.add_argument("--output", "-o", help="グラフを画像ファイルに保存するパス")
    predict.add_argument("--show", action="store_true", help="グラフをウィンドウで表示する")
    return parser, predict


def _parse_date(value: str, option_name: str, error) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        error(f"{option_name} は YYYY-MM-DD 形式で指定してください: {value!r}")
        raise


def _build_scenarios(args: argparse.Namespace, start_date: date, error):
    deadline = _parse_date(args.deadline, "--deadline", error)
    normal_days = business_days_between(start_date, deadline)
    if normal_days <= 0:
        error("--deadline は開始日より後の稼働日になる日付を指定してください")
    if not 0 < args.best_factor < 1:
        error("--best-factor は 0 より大きく 1 未満で指定してください")
    if not math.isfinite(args.worst_factor) or args.worst_factor <= 1:
        error("--worst-factor は 1 より大きい値を指定してください")

    scenarios: dict[str, tuple[LogNormalParams, dict[str, float]]] = {}
    for name, factor in (
        ("最善", args.best_factor),
        ("通常", 1.0),
        ("最悪", args.worst_factor),
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
            f"実績は想定納期より{difference}稼働日 "
            f"({difference_percent:.1f}%)遅れて完了しました。"
        )
    if difference < 0:
        return (
            f"実績は想定納期より{abs(difference)}稼働日 "
            f"({abs(difference_percent):.1f}%)早く完了しました。"
        )
    return "実績は想定納期どおりに完了しました。"


def _print_report(
    start_date: date,
    deadline: date,
    scenarios,
    actual_end_date: date | None = None,
) -> int | None:
    print(f"開始日: {start_date.isoformat()}")
    print(f"想定納期 (通常シナリオのピーク): {deadline.isoformat()}")
    for name, (params, percentiles) in scenarios.items():
        stats = summary_stats(params)
        print(f"\n{name}シナリオ (ピーク: {stats['mode']:.1f}稼働日, σ={params.sigma:g})")
        for label, _q in PERCENTILE_TARGETS:
            days = percentiles[label]
            target_date = add_business_days(start_date, round(days))
            print(f"  {label.upper()}: {days:6.1f}稼働日 -> {target_date.isoformat()}")

    if actual_end_date is None:
        return None

    actual_days = business_days_between(start_date, actual_end_date)
    normal_params, normal_percentiles = scenarios["通常"]
    planned_days = business_days_between(start_date, deadline)
    difference = actual_days - planned_days
    probability = completion_probability(normal_params, actual_days)
    tail_probability = remaining_probability(normal_params, actual_days)

    print("\n終了済み案件の振り返り (通常シナリオ基準)")
    print(f"実際の終了日: {actual_end_date.isoformat()} ({actual_days}稼働日)")
    print(_actual_deviation_sentence(difference, planned_days))
    if probability > 0.999:
        print(
            "通常シナリオでの位置: P99.9超相当 "
            f"(実績以降に完了する確率: {tail_probability * 100:.6g}%)"
        )
    else:
        print(f"通常シナリオでの位置: P{probability * 100:.1f}相当")

    p90_difference = actual_days - normal_percentiles["p90"]
    if p90_difference > 0:
        print(f"P90との差: {p90_difference:.1f}稼働日超過")
    elif p90_difference < 0:
        print(f"P90との差: {abs(p90_difference):.1f}稼働日前に完了")
    else:
        print("P90相当日に完了")
    return actual_days


def main(argv: list[str] | None = None) -> int:
    parser, predict_parser = _build_parser()
    args = parser.parse_args(argv)
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
        predict_parser.error("--actual-end-date は開始日以降の日付を指定してください")
    scenarios = _build_scenarios(args, start_date, predict_parser.error)
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
