"""稼働日(土日を除いた平日)に基づく日数計算・日付変換。

祝日は対象範囲外(仕様書どおり一旦考慮しない)。1週間5日稼働として扱う。
"""

from __future__ import annotations

from datetime import date, timedelta


def is_business_day(d: date) -> bool:
    """土日以外(月〜金)であれば稼働日とみなす。"""
    return d.weekday() < 5  # Mon=0 ... Sun=6


def business_days_between(start: date, end: date) -> int:
    """start(開始日)から end までの稼働日数を返す。

    start 自身は 0 日として数える(経過稼働日数)。
    end が start より後なら正、前なら負の値を返す。
    """
    if end == start:
        return 0

    step = 1 if end > start else -1
    count = 0
    current = start
    while current != end:
        current += timedelta(days=step)
        if is_business_day(current):
            count += step
    return count


def add_business_days(start: date, n: int) -> date:
    """start から稼働日ベースで n 日後(n が負なら前)の日付を返す。"""
    step = 1 if n >= 0 else -1
    remaining = abs(n)
    current = start
    while remaining > 0:
        current += timedelta(days=step)
        if is_business_day(current):
            remaining -= 1
    return current
