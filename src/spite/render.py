"""分布の可視化。

- 引数未指定: ターミナルへのASCIIアート表示
- --output 指定: 画像ファイルへ保存
- --show 指定: matplotlibウィンドウで表示
"""

from __future__ import annotations

import numpy as np

from .lognormal import pdf
from .params import LogNormalParams


def render_ascii(
    params: LogNormalParams,
    percentiles: dict[str, float],
    *,
    comparison_params: LogNormalParams | None = None,
    comparison_percentiles: dict[str, float] | None = None,
    width: int = 50,
    bins: int = 24,
) -> str:
    """確率密度関数をターミナル上のASCIIアートとして描画した文字列を返す。

    comparison_params を指定すると、比較用の分布(指定日に対する標準的の
    標準的な分布など)を "." のバーで並べて表示する。
    """
    all_values = list(percentiles.values())
    if comparison_percentiles:
        all_values += list(comparison_percentiles.values())
    upper = max(all_values) * 1.5
    xs = np.linspace(upper / bins, upper, bins)
    ys = pdf(params, xs)
    max_y = float(ys.max()) if ys.max() > 0 else 1.0

    comparison_ys = None
    if comparison_params is not None:
        comparison_ys = pdf(comparison_params, xs)
        # 比較対象も主分布と同じ密度スケールで描画する。
        # 分布ごとに最大値を幅50へ正規化すると、標準分布を単独表示した
        # 場合と比較したときに、形状や高さが異なって見えてしまう。
        max_y = max(max_y, float(comparison_ys.max()))

    # 各binが担当する区間にどの percentile が含まれるかを調べ、行末に注記する
    labels_by_bin: list[list[str]] = [[] for _ in xs]
    bin_width = xs[1] - xs[0] if bins > 1 else upper
    for name, value in sorted(percentiles.items(), key=lambda kv: kv[1]):
        idx = min(int(value // bin_width), bins - 1)
        labels_by_bin[idx].append(name.upper())
    if comparison_percentiles:
        for name, value in sorted(
            comparison_percentiles.items(), key=lambda kv: kv[1]
        ):
            idx = min(int(value // bin_width), bins - 1)
            labels_by_bin[idx].append(f"{name.upper()}(比較)")

    lines = []
    for i, (x, y) in enumerate(zip(xs, ys)):
        bar_len = int(round((y / max_y) * width))
        bar = "#" * bar_len
        line = f"{x:6.1f}稼働日 | {bar}"
        if comparison_ys is not None:
            comp_len = int(round((comparison_ys[i] / max_y) * width))
            line += f"  | {'.' * comp_len}"
        labels = labels_by_bin[i]
        if labels:
            line += f"  <- {', '.join(labels)}"
        lines.append(line)

    if comparison_ys is not None:
        header = "凡例: # = 指定日(指定した納期), . = 標準的(標準的な分布・比較用)\n"
        return header + "\n".join(lines)
    return "\n".join(lines)


def render_matplotlib(
    params: LogNormalParams,
    percentiles: dict[str, float],
    *,
    comparison_params: LogNormalParams | None = None,
    comparison_percentiles: dict[str, float] | None = None,
    output_path: str | None = None,
    show: bool = False,
) -> None:
    """確率密度関数をmatplotlibで描画し、画像保存・ウィンドウ表示を行う。

    comparison_params を指定すると、比較用の分布(指定日に対する標準的の
    標準的な分布)を同じグラフ上に重ねて表示する。
    """
    import matplotlib

    if not show:
        # 画面表示をしない場合は非対話バックエンドを使う
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 日本語ラベルが文字欠け(tofu)にならないよう、CJK対応フォントを優先させる。
    # 環境に存在しない場合はmatplotlibが自動的に次の候補へフォールバックする。
    plt.rcParams["font.family"] = [
        "Noto Sans CJK JP",
        "IPAPGothic",
        "IPAGothic",
        "sans-serif",
    ]

    def plot_one(
        ax,
        distribution_params: LogNormalParams,
        distribution_percentiles: dict[str, float],
        *,
        title: str,
        color: str,
    ) -> None:
        # 分布ごとに横軸を決める。比較表示でも、各分布の稼働期間が
        # もう一方の分布の長さに引きずられないようにする。
        upper = max(distribution_percentiles.values()) * 1.5
        xs = np.linspace(upper / 500, upper, 500)
        ys = pdf(distribution_params, xs)
        ax.plot(xs, ys, label="確率密度", color=color)

        ymax = ax.get_ylim()[1]
        for name, value in distribution_percentiles.items():
            ax.axvline(value, linestyle="--", alpha=0.7, color=color)
            ax.text(
                value,
                ymax * 0.9,
                name.upper(),
                rotation=90,
                va="top",
                color=color,
            )

        ax.set_xlabel("稼働日数")
        ax.set_ylabel("確率密度")
        ax.set_title(title)
        ax.legend()

    if comparison_params is None:
        fig, ax = plt.subplots()
        plot_one(
            ax,
            params,
            percentiles,
            title="対数正規分布による納期予測",
            color="tab:blue",
        )
    else:
        comparison_percentiles = comparison_percentiles or {}
        standard_upper = max(comparison_percentiles.values()) * 1.5
        specified_upper = max(percentiles.values()) * 1.5
        axis_upper = max(standard_upper, specified_upper)
        standard_xs = np.linspace(standard_upper / 500, standard_upper, 500)
        specified_xs = np.linspace(specified_upper / 500, specified_upper, 500)
        fig, ax = plt.subplots()
        ax.plot(
            standard_xs,
            pdf(comparison_params, standard_xs),
            label="標準的な分布",
            color="tab:orange",
            linestyle="--",
        )
        ax.plot(
            specified_xs,
            pdf(params, specified_xs),
            label="指定日による分布",
            color="tab:blue",
        )
        ax.set_xlim(0, axis_upper)

        ymax = ax.get_ylim()[1]
        for name, value in comparison_percentiles.items():
            ax.axvline(value, linestyle=":", alpha=0.7, color="tab:orange")
            ax.text(
                value,
                ymax * 0.9,
                f"{name.upper()}(標準)",
                rotation=90,
                va="top",
                color="tab:orange",
                fontsize=8,
            )
        for name, value in percentiles.items():
            ax.axvline(value, linestyle="--", alpha=0.7, color="tab:blue")
            ax.text(
                value,
                ymax * 0.72,
                f"{name.upper()}(指定)",
                rotation=90,
                va="top",
                color="tab:blue",
                fontsize=8,
            )

        ax.set_xlabel("稼働日数")
        ax.set_ylabel("確率密度")
        ax.set_title("対数正規分布による納期予測（標準的 vs 指定日）")
        ax.legend()
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path)
    if show:
        plt.show()
    plt.close(fig)
