"""
후행(trailing) 구간 수익률 계산

total return 시계열에서 기준일 대비 1개월/3개월/6개월/YTD/1년/3년/5년 누적
수익률을 계산한다. 세전/세후는 호출측이 시계열을 만들 때 결정한다.
"""
from typing import Dict, Optional

import pandas as pd
from dateutil.relativedelta import relativedelta

TRAILING_HORIZONS = ["1M", "3M", "6M", "YTD", "1Y", "3Y", "5Y"]

_MONTH_OFFSETS = {"1M": 1, "3M": 3, "6M": 6}
_YEAR_OFFSETS = {"1Y": 1, "3Y": 3, "5Y": 5}


def horizon_start_date(as_of: pd.Timestamp, horizon: str) -> pd.Timestamp:
    """후행 구간 시작일 계산"""
    if horizon in _MONTH_OFFSETS:
        return as_of - relativedelta(months=_MONTH_OFFSETS[horizon])
    if horizon in _YEAR_OFFSETS:
        return as_of - relativedelta(years=_YEAR_OFFSETS[horizon])
    if horizon == "YTD":
        return pd.Timestamp(year=as_of.year, month=1, day=1)
    raise ValueError(f"알 수 없는 구간: {horizon}")


def compute_trailing_returns(
    prices: pd.Series,
    as_of_date: Optional[pd.Timestamp] = None,
) -> Dict[str, Optional[float]]:
    """각 후행 구간의 누적 수익률(%) 계산

    Args:
        prices: 오름차순 정렬된 일별 total return Series.
        as_of_date: 기준일(종점). None이면 prices.index[-1] 사용.

    Returns:
        {"1M": pct or None, ..., "5Y": pct or None}.
        구간 시작일이 데이터 시작보다 앞서거나 데이터가 부족하면 None.
    """
    if prices is None or len(prices) == 0:
        return {horizon: None for horizon in TRAILING_HORIZONS}

    as_of = prices.index[-1] if as_of_date is None else pd.Timestamp(as_of_date)
    first = prices.index[0]
    end_value = prices.asof(as_of)

    result: Dict[str, Optional[float]] = {}
    for horizon in TRAILING_HORIZONS:
        start = horizon_start_date(as_of, horizon)
        if pd.isna(end_value) or start < first:
            result[horizon] = None
            continue
        start_value = prices.asof(start)
        if pd.isna(start_value) or start_value == 0:
            result[horizon] = None
            continue
        result[horizon] = (end_value / start_value - 1) * 100

    return result
