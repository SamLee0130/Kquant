"""
배당세 반영 net total return 재구성 테스트 (fetch_total_return_prices)
"""
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from src.data.data_fetcher import fetch_total_return_prices


def _mock_history():
    """가격 변동 없이 배당만 발생하는 3일치 데이터

    Close 일정(100), day1에 $2 배당이 gross 재투자되어 Adj Close가 +2%.
    → gross 누적 +2%, price-only 0%.
    """
    index = pd.DatetimeIndex(["2024-01-02", "2024-01-03", "2024-01-04"])
    return pd.DataFrame(
        {"Close": [100.0, 100.0, 100.0], "Adj Close": [100.0, 102.0, 102.0]},
        index=index,
    )


@pytest.fixture(autouse=True)
def _clear_cache():
    fetch_total_return_prices.clear()
    yield


def _cumret(series):
    return (series.iloc[-1] / series.iloc[0] - 1) * 100


@patch("src.data.data_fetcher.yf.Ticker")
def test_zero_tax_equals_gross(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    mock_ticker.history.return_value = _mock_history()

    series = fetch_total_return_prices("TEST", "2024-01-01", "2024-01-05", 0.0)
    assert abs(_cumret(series) - 2.0) < 1e-9


@patch("src.data.data_fetcher.yf.Ticker")
def test_dividend_tax_reduces_only_dividend_portion(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    mock_ticker.history.return_value = _mock_history()

    # 배당 기여분(+2%)에만 15% 과세 → 1.02 - 0.15*0.02 = 1.017 → +1.7%
    series = fetch_total_return_prices("TEST", "2024-01-01", "2024-01-05", 0.15)
    assert abs(_cumret(series) - 1.7) < 1e-9


@patch("src.data.data_fetcher.yf.Ticker")
def test_full_tax_leaves_price_return_only(mock_ticker_class):
    mock_ticker = MagicMock()
    mock_ticker_class.return_value = mock_ticker
    mock_ticker.history.return_value = _mock_history()

    # 100% 과세 → 배당 기여분 전부 제거 → price-only 0%
    series = fetch_total_return_prices("TEST", "2024-01-01", "2024-01-05", 1.0)
    assert abs(_cumret(series)) < 1e-9
