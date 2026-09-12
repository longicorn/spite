"""対数正規分布の統計量計算。

scipy.stats.lognorm のパラメータ化は shape=sigma, scale=exp(mu) に対応する。
"""

from __future__ import annotations

import math

import numpy as np
from scipy import stats

from .params import LogNormalParams


def scipy_dist(params: LogNormalParams):
    return stats.lognorm(s=params.sigma, scale=math.exp(params.mu))


def percentile_days(params: LogNormalParams, q: float) -> float:
    """累積確率 q (0-1) に対応する稼働日数を返す。"""
    return float(scipy_dist(params).ppf(q))


def pdf(params: LogNormalParams, x: np.ndarray) -> np.ndarray:
    """稼働日数 x における確率密度を返す。"""
    return scipy_dist(params).pdf(x)


def summary_stats(params: LogNormalParams) -> dict[str, float]:
    """分布の代表値(中央値・最頻値・平均・歪度・尖度等)をまとめて返す。"""
    dist = scipy_dist(params)
    mean, var, skew, kurtosis = dist.stats(moments="mvsk")
    mode = math.exp(params.mu - params.sigma**2)
    return {
        "median": math.exp(params.mu),
        "mode": mode,
        "mean": float(mean),
        "variance": float(var),
        "stddev": float(np.sqrt(var)),
        "skewness": float(skew),
        "kurtosis": float(kurtosis),  # 超過尖度 (excess kurtosis)
    }
