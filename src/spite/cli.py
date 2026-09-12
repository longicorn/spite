"""spite predict のコマンドラインインターフェース。"""

from __future__ import annotations

import argparse
from datetime import date, datetime

from .businessdays import add_business_days, business_days_between
from .lognormal import summary_stats, percentile_days
from .params import (
    DEFAULT_MEDIAN_BUSINESS_DAYS,
    DEFAULT_SIGMA,
    LogNormalParams,
    default_params,
    params_from_median_and_sigma,
    params_from_mode_and_p90,
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
        help="確率分布を選択してP50/P80/P90の納期予測を行う",
        description=(
            "確率分布を選択してP50/P80/P90の納期予測を行う。\n"
            "--distribution と --start-date は必須。\n"
            "納期(mode)と最悪日(P90)の両方を指定すればその2点から分布を算出し、\n"
            "指定しない場合は既定のmedian/sigmaから標準的な分布を計算する。"
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    predict.add_argument(
        "--distribution",
        "-d",
        choices=["lognormal"],
        default=None,
        help="使用する確率分布 (現在は lognormal のみ対応。今後スプライス分布/Weibull分布を追加予定)",
    )
    predict.add_argument(
        "--start-date",
        default=None,
        help="開発開始日 (YYYY-MM-DD)",
    )
    predict.add_argument(
        "--deadline",
        default=None,
        help="納期=分布のピーク(mode)となる日付 (YYYY-MM-DD)。--worst-caseと併用必須",
    )
    predict.add_argument(
        "--worst-case",
        default=None,
        help="最悪でもこの日までには終えたい日付 (P90相当, YYYY-MM-DD)。--deadlineと併用必須",
    )
    predict.add_argument(
        "--median-days",
        type=float,
        default=None,
        help=(
            "開始日のみで計算する場合の中央値(稼働日数)。"
            f"既定値は{DEFAULT_MEDIAN_BUSINESS_DAYS:g}。--deadline/--worst-caseとは併用不可"
        ),
    )
    predict.add_argument(
        "--sigma",
        type=float,
        default=None,
        help=(
            "開始日のみで計算する場合のばらつき(sigma)。"
            f"既定値は{DEFAULT_SIGMA:g}。--deadline/--worst-caseとは併用不可"
        ),
    )
    predict.add_argument(
        "--output",
        "-o",
        default=None,
        help="グラフを画像ファイルに保存するパス (例: out.png)",
    )
    predict.add_argument(
        "--show",
        action="store_true",
        help="matplotlibのウィンドウでグラフを表示する",
    )
    return parser, predict


def _parse_date(value: str, option_name: str, error) -> date:
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        error(f"{option_name} は YYYY-MM-DD 形式で指定してください: {value!r}")
        raise  # error() は終了するが型チェッカー向けに明示


def _resolve_params(args: argparse.Namespace, start_date: date, error) -> LogNormalParams:
    has_deadline = args.deadline is not None
    has_worst_case = args.worst_case is not None

    if has_deadline != has_worst_case:
        error("--deadline と --worst-case は両方指定してください(どちらか一方のみは不可)")

    if has_deadline and has_worst_case:
        if args.median_days is not None or args.sigma is not None:
            error(
                "--deadline/--worst-case 指定時は --median-days / --sigma は使用できません"
            )
        deadline = _parse_date(args.deadline, "--deadline", error)
        worst_case = _parse_date(args.worst_case, "--worst-case", error)
        mode_days = business_days_between(start_date, deadline)
        p90_days = business_days_between(start_date, worst_case)
        try:
            return params_from_mode_and_p90(mode_days, p90_days)
        except ValueError as exc:
            error(str(exc))
            raise

    median_days = (
        args.median_days if args.median_days is not None else DEFAULT_MEDIAN_BUSINESS_DAYS
    )
    sigma = args.sigma if args.sigma is not None else DEFAULT_SIGMA
    try:
        return params_from_median_and_sigma(median_days, sigma)
    except ValueError as exc:
        error(str(exc))
        raise


def _print_report(
    start_date: date,
    params: LogNormalParams,
    stats: dict[str, float],
    percentiles: dict[str, float],
) -> None:
    print(f"開始日: {start_date.isoformat()}")
    print(f"分布パラメータ: mu={params.mu:.4f}, sigma={params.sigma:.4f}")
    print(f"  中央値 (median, 稼働日数): {stats['median']:.1f}")
    print(f"  最頻値 (mode,   稼働日数): {stats['mode']:.1f}")
    print(f"  平均値 (mean,   稼働日数): {stats['mean']:.1f}")
    print(f"  標準偏差 (stddev): {stats['stddev']:.2f}")
    print(f"  歪度 (skewness): {stats['skewness']:.3f}")
    print(f"  尖度 (excess kurtosis): {stats['kurtosis']:.3f}")
    print()
    print("パーセンタイル予測 (稼働日数 / 日付):")
    for label, _q in PERCENTILE_TARGETS:
        days = percentiles[label]
        target_date = add_business_days(start_date, round(days))
        print(f"  {label.upper()}: {days:6.1f}稼働日 -> {target_date.isoformat()}")


def main(argv: list[str] | None = None) -> int:
    parser, predict_parser = _build_parser()
    args = parser.parse_args(argv)

    if args.command != "predict":
        parser.print_help()
        return 0

    if args.distribution is None or args.start_date is None:
        predict_parser.print_help()
        return 0

    start_date = _parse_date(args.start_date, "--start-date", predict_parser.error)
    params = _resolve_params(args, start_date, predict_parser.error)

    stats = summary_stats(params)
    percentiles = {name: percentile_days(params, q) for name, q in PERCENTILE_TARGETS}

    _print_report(start_date, params, stats, percentiles)

    # 選択肢1(--deadline/--worst-case指定)の場合は、比較しやすいように
    # 選択肢2の標準的な分布(既定のmedian/sigma)も同時にグラフ表示する。
    is_choice1 = args.deadline is not None and args.worst_case is not None
    comparison_params: LogNormalParams | None = None
    comparison_percentiles: dict[str, float] | None = None
    if is_choice1:
        comparison_params = default_params()
        comparison_percentiles = {
            name: percentile_days(comparison_params, q) for name, q in PERCENTILE_TARGETS
        }

    if args.output or args.show:
        render_matplotlib(
            params,
            percentiles,
            comparison_params=comparison_params,
            comparison_percentiles=comparison_percentiles,
            output_path=args.output,
            show=args.show,
        )
    else:
        print()
        print(
            render_ascii(
                params,
                percentiles,
                comparison_params=comparison_params,
                comparison_percentiles=comparison_percentiles,
            )
        )

    return 0
