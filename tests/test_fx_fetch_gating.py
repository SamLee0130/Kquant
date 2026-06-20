"""
환율 데이터 조회 게이팅 회귀 테스트

base 통화와 다른 통화 종목이 있으면(종목끼리는 같은 통화여도) FX를 받아와야 한다.
예전엔 has_mixed_currencies(종목 간 통화 비교)라서 전 종목 USD + base KRW일 때
FX를 안 받아오고 1300 고정값을 쓰던 버그 방지.
"""
from datetime import datetime
from unittest.mock import patch, MagicMock

import pandas as pd

from src.backtest.portfolio_backtest import PortfolioBacktester
from src.data.etf_classifier import ETFInfo, Market


def _stub_price(ticker, start, end):
    return pd.DataFrame({"price": [100.0]}, index=pd.DatetimeIndex(["2020-01-02"]))


def _stub_div(ticker, start, end):
    return pd.Series(dtype=float, index=pd.DatetimeIndex([]))


def _make_backtester(base_currency):
    converter = MagicMock()
    converter.base_currency = base_currency
    etf_info = {
        "QQQ": ETFInfo("QQQ", "QQQ", Market.US, "USD"),
        "BIL": ETFInfo("BIL", "BIL", Market.US, "USD"),
    }
    return PortfolioBacktester(
        allocation={"QQQ": 0.5, "BIL": 0.5},
        etf_info=etf_info,
        currency_converter=converter,
    ), converter


@patch("src.backtest.portfolio_backtest.fetch_dividend_data", side_effect=_stub_div)
@patch("src.backtest.portfolio_backtest.fetch_price_data", side_effect=_stub_price)
def test_fetches_fx_for_all_usd_with_krw_base(_mp, _md):
    """전 종목 USD + base KRW → FX 조회해야 함"""
    bt, converter = _make_backtester("KRW")
    bt._fetch_data(["QQQ", "BIL"], datetime(2020, 1, 1), datetime(2021, 1, 1))
    converter.fetch_fx_data.assert_called_once()


@patch("src.backtest.portfolio_backtest.fetch_dividend_data", side_effect=_stub_div)
@patch("src.backtest.portfolio_backtest.fetch_price_data", side_effect=_stub_price)
def test_no_fx_fetch_when_base_matches(_mp, _md):
    """전 종목 USD + base USD → FX 조회 불필요"""
    bt, converter = _make_backtester("USD")
    bt._fetch_data(["QQQ", "BIL"], datetime(2020, 1, 1), datetime(2021, 1, 1))
    converter.fetch_fx_data.assert_not_called()
