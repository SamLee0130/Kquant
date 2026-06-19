"""
배당이 없는 종목(예: GLD) 회귀 테스트

fetch_dividend_data가 빈 배당을 RangeIndex로 반환하면, 백테스트 엔진에서
'dividends.index >= Timestamp' 비교가 깨졌던 버그를 방지한다.
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.data.data_fetcher import fetch_dividend_data
from tests.test_portfolio_backtest import create_backtester_with_data, PRICE_DATA_A


@pytest.fixture(autouse=True)
def _clear_cache():
    fetch_dividend_data.clear()
    yield


@patch("src.data.data_fetcher.yf.Ticker")
def test_empty_dividends_returns_datetime_index(mock_ticker_class):
    """배당 없는 종목 → 빈 Series지만 인덱스는 DatetimeIndex여야 한다"""
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    mock_ticker.dividends = pd.Series(dtype=float)  # yfinance 빈 배당

    result = fetch_dividend_data("GLD", "2020-01-01", "2023-01-01")

    assert result.empty
    assert isinstance(result.index, pd.DatetimeIndex)
    # Timestamp 비교가 깨지지 않아야 한다
    _ = result.index >= pd.Timestamp("2020-01-01")


def test_get_dividends_handles_rangeindex_empty():
    """예전 방식의 RangeIndex 빈 Series가 주입돼도 엔진이 죽지 않아야 한다"""
    bt = create_backtester_with_data(
        allocation={"GLD": 1.0},
        price_data={"GLD": PRICE_DATA_A},
        dividend_data={"GLD": pd.Series(dtype=float)},  # RangeIndex(빈)
    )

    result = bt._get_dividends(
        "GLD", pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31")
    )
    assert result.empty
