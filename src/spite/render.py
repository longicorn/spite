"""最善・通常・最悪シナリオの確率分布を可視化する。"""

from __future__ import annotations

from datetime import date

import numpy as np

from .businessdays import add_business_days
from .lognormal import pdf
from .params import LogNormalParams

ScenarioMap = dict[str, tuple[LogNormalParams, dict[str, float]]]
COLORS = {"最善": "tab:green", "通常": "tab:blue", "最悪": "tab:red"}


def render_ascii(
    scenarios: ScenarioMap,
    *,
    actual_days: int | None = None,
    width: int = 48,
    bins: int = 24,
) -> str:
    """3シナリオの密度を同じ尺度のASCIIアートで返す。"""
    upper = max(max(values.values()) for _, values in scenarios.values()) * 1.5
    if actual_days is not None:
        upper = max(upper, actual_days * 1.05, 1.0)
    xs = np.linspace(upper / bins, upper, bins)
    densities = {name: pdf(params, xs) for name, (params, _) in scenarios.items()}
    max_y = max(float(ys.max()) for ys in densities.values()) or 1.0
    lines = ["凡例: # 最善  + 通常  . 最悪"]
    symbols = {"最善": "#", "通常": "+", "最悪": "."}
    actual_idx = (
        int(np.abs(xs - actual_days).argmin()) if actual_days is not None else None
    )
    for idx, x in enumerate(xs):
        bars = [
            symbols[name] * int(round(float(ys[idx]) / max_y * width))
            for name, ys in densities.items()
        ]
        line = f"{x:6.1f}稼働日 | " + " | ".join(bars)
        if idx == actual_idx:
            line += f"  ^ 実績 {actual_days}稼働日"
        lines.append(line)
    return "\n".join(lines)


def render_matplotlib(
    scenarios: ScenarioMap,
    *,
    start_date: date | None = None,
    actual_days: int | None = None,
    output_path: str | None = None,
    show: bool = False,
) -> None:
    """3シナリオを重ねて描画し、必要なら保存または表示する。"""
    import matplotlib

    if not show:
        matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.family"] = [
        "Noto Sans CJK JP", "IPAPGothic", "IPAGothic", "sans-serif"
    ]

    if start_date is not None:
        fig = plt.figure(figsize=(9, 7), layout="constrained")
        grid = fig.add_gridspec(2, 1, height_ratios=[4, 1.2])
        ax = fig.add_subplot(grid[0])
        table_ax = fig.add_subplot(grid[1])
        table_ax.axis("off")
    else:
        fig, ax = plt.subplots()

    max_days = max(max(values.values()) for _, values in scenarios.values())
    upper = max_days * 1.5
    if actual_days is not None:
        upper = max(upper, actual_days * 1.05, 1.0)
    xs = np.linspace(upper / 600, upper, 600)
    for name, (params, percentiles) in scenarios.items():
        color = COLORS.get(name, "tab:gray")
        ax.plot(xs, pdf(params, xs), label=f"{name}シナリオ", color=color)
        for label, value in percentiles.items():
            ax.axvline(value, linestyle="--", alpha=0.45, color=color)
            ax.text(value, 0.96, label.upper(), rotation=90, va="top",
                    color=color, transform=ax.get_xaxis_transform(), fontsize=8)

    ax.set_xlim(0, upper)
    ax.set_xlabel("稼働日数")
    ax.set_ylabel("確率密度")
    ax.set_title("対数正規分布による納期予測")
    if actual_days is not None:
        ax.axvline(actual_days, color="black", linestyle="-.", linewidth=1.5,
                   label=f"実績 {actual_days}稼働日")
    ax.legend()

    if start_date is not None:
        names = list(next(iter(scenarios.values()))[1])
        cells = []
        for scenario, (_, percentiles) in scenarios.items():
            cells.append([scenario] + [
                f"{percentiles[name]:.1f}稼働日\n"
                f"{add_business_days(start_date, round(percentiles[name])).isoformat()}"
                for name in names
            ])
        table = table_ax.table(
            cellText=cells,
            colLabels=["シナリオ"] + [name.upper() for name in names],
            cellLoc="center",
            colWidths=[0.16] + [0.84 / len(names)] * len(names),
            bbox=[0, 0, 1, 1],
        )
        table.auto_set_font_size(False)
        table.set_fontsize(9)
        for row, scenario in enumerate(scenarios, start=1):
            for col in range(len(names) + 1):
                table[row, col].get_text().set_color(COLORS.get(scenario, "black"))

    if output_path:
        fig.savefig(output_path)
    if show:
        plt.show()
    plt.close(fig)
