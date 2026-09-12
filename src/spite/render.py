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
    width: int = 50,
    bins: int = 24,
) -> str:
    """確率密度関数をターミナル上のASCIIアートとして描画した文字列を返す。"""
    upper = max(percentiles.values()) * 1.5
    xs = np.linspace(upper / bins, upper, bins)
    ys = pdf(params, xs)
    max_y = float(ys.max()) if ys.max() > 0 else 1.0

    # 各binが担当する区間にどの percentile が含まれるかを調べ、行末に注記する
    labels_by_bin: list[list[str]] = [[] for _ in xs]
    bin_width = xs[1] - xs[0] if bins > 1 else upper
    for name, value in sorted(percentiles.items(), key=lambda kv: kv[1]):
        idx = min(int(value // bin_width), bins - 1)
        labels_by_bin[idx].append(name.upper())

    lines = []
    for x, y, labels in zip(xs, ys, labels_by_bin):
        bar_len = int(round((y / max_y) * width))
        bar = "#" * bar_len
        mark = f"  <- {', '.join(labels)}" if labels else ""
        lines.append(f"{x:6.1f}稼働日 | {bar}{mark}")
    return "\n".join(lines)


def render_matplotlib(
    params: LogNormalParams,
    percentiles: dict[str, float],
    *,
    output_path: str | None = None,
    show: bool = False,
) -> None:
    """確率密度関数をmatplotlibで描画し、画像保存・ウィンドウ表示を行う。"""
    import matplotlib

    if not show:
        # 画面表示をしない場合は非対話バックエンドを使う
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    # 日本語ラベルが文字欠け(tofu)にならないよう、CJK対応フォントを優先させる。
    # 環境に存在しない場合はmatplotlibが自動的に次の候補へフォールバックする。
    plt.rcParams["font.family"] = [
        "Noto Sans CJK JP",
        "IPAexGothic",
        "sans-serif",
    ]

    upper = max(percentiles.values()) * 1.5
    xs = np.linspace(upper / 500, upper, 500)
    ys = pdf(params, xs)

    fig, ax = plt.subplots()
    ax.plot(xs, ys, label="確率密度")
    for name, value in percentiles.items():
        ax.axvline(value, linestyle="--", alpha=0.7)
        ax.text(value, ax.get_ylim()[1] * 0.9, name.upper(), rotation=90, va="top")
    ax.set_xlabel("稼働日数")
    ax.set_ylabel("確率密度")
    ax.set_title("対数正規分布による納期予測")
    ax.legend()
    fig.tight_layout()

    if output_path:
        fig.savefig(output_path)
    if show:
        plt.show()
    plt.close(fig)
