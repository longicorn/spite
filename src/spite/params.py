"""対数正規分布のパラメータ定義・算出ロジック。

μ (mu), σ (sigma) は手動で調整しやすいよう、このモジュール冒頭の定数として
まとめて定義している。値に問題があれば、ここだけを書き換えれば良い。
"""

from __future__ import annotations

import math
from dataclasses import dataclass

# --- 標準的(開始日のみ指定)で使うデフォルトパラメータ ------------------
#
# sigma: 対数正規分布の形状(相対的なばらつき)パラメータ。
#     無次元の値で、ソフトウェア開発の見積もりにおいて経験的に使われる
#     範囲は 0.3〜0.7 程度とされる。ここではその中間的な値を既定値とする。
DEFAULT_SIGMA: float = 0.5

# median_business_days: 対数正規分布の中央値(稼働日数、土日を除く)。
#     期間の絶対的な規模を表す値のため、数学的に「標準」と言える値は
#     存在しない。ここではデモ用の仮の値として 20稼働日(=4週間) を
#     既定値とする。実際の案件規模に応じて書き換えること。
DEFAULT_MEDIAN_BUSINESS_DAYS: float = 20.0

# 標準正規分布の90パーセンタイル点(z値)。
# lognormal の P90 = exp(mu + Z_P90 * sigma) の算出に用いる。
Z_P90: float = 1.2815515655446004


@dataclass(frozen=True)
class LogNormalParams:
    """対数正規分布のパラメータ (対数空間での平均 mu, 標準偏差 sigma)。"""

    mu: float
    sigma: float


def params_from_median_and_sigma(
    median_business_days: float, sigma: float
) -> LogNormalParams:
    """中央値(稼働日数)とσから直接パラメータを組み立てる(標準的)。

    lognormal の median = exp(mu) なので mu = ln(median) となる。
    """
    if median_business_days <= 0:
        raise ValueError("median_business_days は正の値である必要があります")
    if sigma <= 0:
        raise ValueError("sigma は正の値である必要があります")
    return LogNormalParams(mu=math.log(median_business_days), sigma=sigma)


def default_params() -> LogNormalParams:
    """標準的(開始日のみ)用のデフォルトパラメータを返す。"""
    return params_from_median_and_sigma(DEFAULT_MEDIAN_BUSINESS_DAYS, DEFAULT_SIGMA)


def params_from_mode_and_p90(mode_days: float, p90_days: float) -> LogNormalParams:
    """納期(mode, 分布のピーク)と最悪日(P90)の2点からμ, σを解析的に算出する(指定日)。

    lognormal の関係式:
        mode = exp(mu - sigma^2)
        P90  = exp(mu + Z_P90 * sigma)
    この2式から sigma についての2次方程式を導ける:
        sigma^2 + Z_P90 * sigma - ln(P90 / mode) = 0
    正の解を解の公式で求め、そこから mu を逆算する。
    """
    if mode_days <= 0 or p90_days <= 0:
        raise ValueError("mode_days, p90_days は正の値である必要があります")
    if p90_days <= mode_days:
        raise ValueError(
            "最悪日(P90相当)は納期(mode)より後の日付である必要があります"
        )

    ln_ratio = math.log(p90_days / mode_days)
    sigma = (-Z_P90 + math.sqrt(Z_P90**2 + 4 * ln_ratio)) / 2
    mu = math.log(mode_days) + sigma**2
    return LogNormalParams(mu=mu, sigma=sigma)
