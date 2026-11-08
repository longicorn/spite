"""対数正規分布のパラメータ定義・算出ロジック。"""

from __future__ import annotations

import math
from dataclasses import dataclass

# 初期版で使う共通のσとシナリオ係数。
DEFAULT_SIGMA: float = 0.5

# 初期版で使うシナリオ係数。いずれも通常シナリオのピークに対する倍率。
DEFAULT_BEST_FACTOR: float = 0.8
DEFAULT_WORST_FACTOR: float = 1.5

@dataclass(frozen=True)
class LogNormalParams:
    """対数正規分布のパラメータ (対数空間での平均 mu, 標準偏差 sigma)。"""

    mu: float
    sigma: float


def params_from_mode_and_sigma(mode_days: float, sigma: float) -> LogNormalParams:
    """分布のピーク(最頻値)とσから対数正規分布を組み立てる。

    mode = exp(mu - sigma**2) より mu = ln(mode) + sigma**2。
    """
    if not math.isfinite(mode_days) or mode_days <= 0:
        raise ValueError("mode_days must be finite and positive")
    if not math.isfinite(sigma) or sigma <= 0:
        raise ValueError("sigma must be finite and positive")
    return LogNormalParams(mu=math.log(mode_days) + sigma**2, sigma=sigma)
