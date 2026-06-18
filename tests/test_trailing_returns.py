"""
후행 구간 수익률 계산 테스트 (순수 함수, mock 불필요)
"""
import pandas as pd
import pytest

from src.backtest.trailing_returns import compute_trailing_returns, TRAILING_HORIZONS


def _daily_series(start, end, base=100.0):
    """매일(달력일) 1씩 증가하는 시계열 — 날짜별 값이 명확해 검증 용이"""
    index = pd.date_range(start, end, freq="D")
    values = [base + i for i in range(len(index))]
    return pd.Series(values, index=index)


def test_precise_horizon_returns():
    prices = _daily_series("2019-06-01", "2024-06-01")  # as_of = 2024-06-01
    result = compute_trailing_returns(prices)

    end = prices.loc["2024-06-01"]
    for horizon, start_label in [
        ("1M", "2024-05-01"),
        ("3M", "2024-03-01"),
        ("6M", "2023-12-01"),
        ("YTD", "2024-01-01"),
        ("1Y", "2023-06-01"),
        ("3Y", "2021-06-01"),
        ("5Y", "2019-06-01"),
    ]:
        expected = (end / prices.loc[start_label] - 1) * 100
        assert result[horizon] == pytest.approx(expected), horizon


def test_insufficient_history_returns_none():
    prices = _daily_series("2023-06-01", "2024-06-01")  # 1년치
    result = compute_trailing_returns(prices)
    assert result["5Y"] is None
    assert result["3Y"] is None
    assert result["6M"] is not None
    assert result["1Y"] is not None


def test_ytd_none_when_listed_mid_year():
    prices = _daily_series("2024-03-01", "2024-06-01")  # 연초 데이터 없음
    result = compute_trailing_returns(prices)
    assert result["YTD"] is None       # 시작일(1/1)이 데이터 시작보다 앞섬
    assert result["1M"] is not None


def test_as_of_date_with_weekend_gap():
    """거래일이 아닌 기준일 → asof가 직전 거래일을 잡아 None이 아님"""
    prices = _daily_series("2020-01-01", "2024-01-05")
    # 일부러 주말을 제거해 갭을 만든 뒤, 갭 날짜를 as_of로 사용
    prices = prices[prices.index.dayofweek < 5]
    sunday = pd.Timestamp("2023-06-25")  # 일요일
    assert sunday not in prices.index
    result = compute_trailing_returns(prices, as_of_date=sunday)
    assert result["1Y"] is not None
    assert result["1M"] is not None


def test_empty_series_all_none():
    result = compute_trailing_returns(pd.Series(dtype=float))
    assert set(result.keys()) == set(TRAILING_HORIZONS)
    assert all(v is None for v in result.values())


def test_as_of_before_data_all_none():
    prices = _daily_series("2023-01-01", "2024-01-01")
    result = compute_trailing_returns(prices, as_of_date="2020-01-01")
    assert all(v is None for v in result.values())
