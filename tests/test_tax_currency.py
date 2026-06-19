"""
세금의 base 통화 환산 회귀 테스트

base=KRW인데 세금이 native(USD) 금액으로 보고돼 ~1300배 작게 표시되던 버그 방지.
"""
import pandas as pd
import pytest

from src.backtest.tax_calculator import TaxCalculator, TaxEvent
from src.backtest.backtest_utils import summarize_tax_events
from src.backtest.portfolio_backtest import PortfolioBacktester
from src.data.etf_classifier import ETFInfo, Market


class StubConverter:
    """고정 환율 변환기 (USD→base = rate)"""
    def __init__(self, rate):
        self.rate = rate

    def get_fx_rate(self, currency, date):
        return self.rate

    def fetch_fx_data(self, start, end):
        pass


def test_reported_tax_falls_back_to_native():
    event = TaxEvent(pd.Timestamp("2024-01-02"), "dividend", 100.0, 15.0, 85.0)
    assert event.reported_tax == 15.0  # base 미설정 → native
    event.tax_amount_base = 19_500.0
    assert event.reported_tax == 19_500.0  # base 설정 시 base


def test_get_total_tax_base_sums_reported():
    calc = TaxCalculator()
    e1 = calc.calculate_dividend_tax(100.0, pd.Timestamp("2024-01-02"))  # native 15
    e1.tax_amount_base = 19_500.0
    # native 폴백(미설정) 이벤트도 합산에 포함
    e2 = calc.calculate_dividend_tax(100.0, pd.Timestamp("2024-02-02"))  # native 15
    assert calc.get_total_tax_base() == pytest.approx(19_500.0 + 15.0)


def test_summarize_uses_base_amount():
    event = TaxEvent(pd.Timestamp("2024-01-02"), "dividend", 100.0, 15.0, 85.0,
                     tax_amount_base=19_500.0)
    summary = summarize_tax_events([event])
    assert summary["dividend_tax"] == pytest.approx(19_500.0)


def test_dividend_tax_reported_in_base_currency():
    """KRW base + USD 종목: 배당세가 base(원)로 환산돼 보고돼야 한다"""
    dates = pd.DatetimeIndex(["2024-03-15"])
    bt = PortfolioBacktester(
        allocation={"ETF_A": 1.0}, initial_capital=1_300_000,
        dividend_tax_rate=0.15, withdrawal_rate=0.0,
        etf_info={"ETF_A": ETFInfo("ETF_A", "ETF A", Market.US, "USD")},
        currency_converter=StubConverter(1300.0),
    )
    bt._dividend_data = {"ETF_A": pd.Series([2.0], index=dates)}  # 주당 $2 배당
    bt.holdings = {"ETF_A": 100}  # 100주 → gross $200, native 세금 $30

    bt._process_dividends(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-12-31"))

    div_event = bt.tax_calculator.tax_history[0]
    assert div_event.tax_amount == pytest.approx(30.0)            # native USD
    assert div_event.tax_amount_base == pytest.approx(30.0 * 1300.0)  # base KRW
    assert bt.tax_calculator.get_total_tax_base() == pytest.approx(39_000.0)
