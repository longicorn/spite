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

    comparison_params を指定すると、比較用の分布(選択肢1に対する選択肢2の
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
    comparison_max_y = 1.0
    if comparison_params is not None:
        comparison_ys = pdf(comparison_params, xs)
        comparison_max_y = (
            float(comparison_ys.max()) if comparison_ys.max() > 0 else 1.0
        )

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
            comp_len = int(round((comparison_ys[i] / comparison_max_y) * width))
            line += f"  | {'.' * comp_len}"
        labels = labels_by_bin[i]
        if labels:
            line += f"  <- {', '.join(labels)}"
        lines.append(line)

    if comparison_ys is not None:
        header = "凡例: # = 選択肢1(指定した納期), . = 選択肢2(標準的な分布・比較用)\n"
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

    comparison_params を指定すると、比較用の分布(選択肢1に対する選択肢2の
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

    all_values = list(percentiles.values())
    if comparison_percentiles:
        all_values += list(comparison_percentiles.values())
    upper = max(all_values) * 1.5
    xs = np.linspace(upper / 500, upper, 500)
    ys = pdf(params, xs)

    fig, ax = plt.subplots()
    main_label = "確率密度" if comparison_params is None else "選択肢1: 指定した納期による分布"
    ax.plot(xs, ys, label=main_label, color="tab:blue")

    comparison_ys = None
    if comparison_params is not None:
        comparison_ys = pdf(comparison_params, xs)
        ax.plot(
            xs,
            comparison_ys,
            label="選択肢2: 標準的な分布(比較用)",
            color="tab:orange",
            linestyle="--",
        )

    ymax = ax.get_ylim()[1]
    for name, value in percentiles.items():
        ax.axvline(value, linestyle="--", alpha=0.7, color="tab:blue")
        ax.text(
            value, ymax * 0.9, name.upper(), rotation=90, va="top", color="tab:blue"
        )

    if comparison_percentiles:
        for name, value in comparison_percentiles.items():
            ax.axvline(value, linestyle=":", alpha=0.5, color="tab:orange")
            ax.text(
                value,
                ymax * 0.75,
                f"{name.upper()}'",
                rotation=90,
                va="top",
                color="tab:orange",
                fontsize=8,
            )

    ax.set_xlabel("稼働日数")
    ax.set_ylabel("確率密度")
    title = "対数正規分布による納期予測"
    if comparison_params is not None:
        title += "(選択肢1 vs 選択肢2)"
    ax.set_title(title)
    ax.legend()
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path)
    if show:
        plt.show()
    plt.close(fig)
