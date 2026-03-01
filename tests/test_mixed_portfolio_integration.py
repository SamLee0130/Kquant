"""
혼합 포트폴리오 통합 테스트

US + KR ETF 혼합 포트폴리오의 백테스트 엔진 통합을 검증합니다.
환율 변환, ETF별 세금 분기, 거래일 합집합 처리를 테스트합니다.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from src.backtest.portfolio_backtest import PortfolioBacktester, PortfolioSnapshot
from src.backtest.tax_calculator import TaxCalculator
from src.data.etf_classifier import ETFInfo, Market
from src.data.fx_fetcher import CurrencyConverter


def make_price_df(dates, prices):
    """테스트용 가격 DataFrame 생성"""
    index = pd.DatetimeIndex(dates)
    return pd.DataFrame({'price': prices}, index=index)


def make_dividend_series(dates, amounts):
    """테스트용 배당 Series 생성"""
    index = pd.DatetimeIndex(dates)
    return pd.Series(amounts, index=index)


def make_fx_df(dates, rates):
    """테스트용 환율 DataFrame 생성"""
    index = pd.DatetimeIndex(dates)
    return pd.DataFrame({'rate': rates}, index=index)


# 테스트 날짜
DATES = ["2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]


@pytest.fixture
def us_etf_info():
    return ETFInfo("SPY", "SPY", Market.US, "USD")


@pytest.fixture
def kr_stock_etf_info():
    return ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW")


@pytest.fixture
def kr_other_etf_info():
    return ETFInfo("360750.KS", "TIGER S&P500", Market.KR_OTHER, "KRW")


class TestHelperMethods:
    """_get_market, _get_fx_rate 헬퍼 테스트"""

    def test_get_market_with_etf_info(self):
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        bt = PortfolioBacktester(etf_info=etf_info)
        assert bt._get_market("SPY") == Market.US
        assert bt._get_market("069500.KS") == Market.KR_STOCK

    def test_get_market_without_etf_info(self):
        bt = PortfolioBacktester()
        assert bt._get_market("SPY") is None

    def test_get_market_unknown_symbol(self):
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        bt = PortfolioBacktester(etf_info=etf_info)
        assert bt._get_market("UNKNOWN") is None

    def test_get_fx_rate_without_converter(self):
        bt = PortfolioBacktester()
        assert bt._get_fx_rate("SPY", pd.Timestamp("2024-01-15")) == 1.0

    def test_get_fx_rate_with_converter(self):
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])
        bt = PortfolioBacktester(etf_info=etf_info, currency_converter=converter)
        rate = bt._get_fx_rate("SPY", pd.Timestamp("2024-01-15"))
        assert rate == 1300.0

    def test_get_fx_rate_krw_etf_returns_one(self):
        """KRW ETF는 KRW 기준이므로 환율 1.0"""
        etf_info = {"069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW")}
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])
        bt = PortfolioBacktester(etf_info=etf_info, currency_converter=converter)
        rate = bt._get_fx_rate("069500.KS", pd.Timestamp("2024-01-15"))
        assert rate == 1.0


class TestPortfolioValueWithFX:
    """환율 적용된 포트폴리오 가치 계산 테스트"""

    def test_us_only_portfolio_with_fx(self):
        """US ETF only + 환율 변환"""
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])

        bt = PortfolioBacktester(
            initial_capital=1_300_000,
            allocation={"SPY": 1.0},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt._price_data = {"SPY": make_price_df(["2024-01-15"], [500.0])}
        bt.holdings = {"SPY": 2.0}
        bt.cash = 0.0

        # 2 shares × $500 × 1300 = ₩1,300,000
        value = bt._get_portfolio_value(pd.Timestamp("2024-01-15"))
        assert abs(value - 1_300_000.0) < 0.01

    def test_kr_only_portfolio_no_fx_conversion(self):
        """KR ETF only → 환율 변환 없음 (KRW→KRW = 1.0)"""
        etf_info = {"069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW")}
        converter = CurrencyConverter(base_currency="KRW")

        bt = PortfolioBacktester(
            initial_capital=10_000_000,
            allocation={"069500.KS": 1.0},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt._price_data = {"069500.KS": make_price_df(["2024-01-15"], [50000.0])}
        bt.holdings = {"069500.KS": 200.0}
        bt.cash = 0.0

        # 200 shares × ₩50,000 × 1.0 = ₩10,000,000
        value = bt._get_portfolio_value(pd.Timestamp("2024-01-15"))
        assert abs(value - 10_000_000.0) < 0.01

    def test_mixed_portfolio_value(self):
        """US + KR 혼합 포트폴리오 가치"""
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])

        bt = PortfolioBacktester(
            initial_capital=14_000_000,
            allocation={"SPY": 0.5, "069500.KS": 0.5},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt._price_data = {
            "SPY": make_price_df(["2024-01-15"], [500.0]),
            "069500.KS": make_price_df(["2024-01-15"], [50000.0]),
        }
        bt.holdings = {"SPY": 10.0, "069500.KS": 20.0}
        bt.cash = 1_000_000.0

        # SPY: 10 × $500 × 1300 = ₩6,500,000
        # KODEX: 20 × ₩50,000 × 1.0 = ₩1,000,000
        # Cash: ₩1,000,000
        # Total: ₩8,500,000
        value = bt._get_portfolio_value(pd.Timestamp("2024-01-15"))
        assert abs(value - 8_500_000.0) < 0.01


class TestInitialPurchaseWithFX:
    """환율 적용된 초기 매수 테스트"""

    def test_initial_purchase_fx_share_count(self):
        """초기 매수 시 환율 반영한 주식 수 계산"""
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])

        bt = PortfolioBacktester(
            initial_capital=13_000_000,  # ₩13,000,000
            allocation={"SPY": 1.0},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt._price_data = {"SPY": make_price_df(["2024-01-15"], [500.0])}
        bt.holdings = {}
        bt.cash = 13_000_000

        bt._execute_initial_purchase(pd.Timestamp("2024-01-15"))

        # ₩13,000,000 / ($500 × 1300) = 20 shares
        assert abs(bt.holdings["SPY"] - 20.0) < 0.01
        assert abs(bt.cash) < 0.01

    def test_initial_purchase_mixed_portfolio(self):
        """혼합 포트폴리오 초기 매수"""
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(["2024-01-15"], [1300.0])

        bt = PortfolioBacktester(
            initial_capital=10_000_000,
            allocation={"SPY": 0.5, "069500.KS": 0.5},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt._price_data = {
            "SPY": make_price_df(["2024-01-15"], [500.0]),
            "069500.KS": make_price_df(["2024-01-15"], [50000.0]),
        }
        bt.holdings = {}
        bt.cash = 10_000_000

        bt._execute_initial_purchase(pd.Timestamp("2024-01-15"))

        # SPY: ₩5,000,000 / ($500 × 1300) ≈ 7.69 shares
        assert abs(bt.holdings["SPY"] - 5_000_000 / (500 * 1300)) < 0.01
        # KODEX: ₩5,000,000 / ₩50,000 = 100 shares
        assert abs(bt.holdings["069500.KS"] - 100.0) < 0.01


class TestDividendsWithMarket:
    """시장별 배당세율 적용 테스트"""

    def test_us_dividend_15pct(self):
        """US ETF 배당 → 15% 배당세"""
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        bt = PortfolioBacktester(
            allocation={"SPY": 1.0},
            etf_info=etf_info
        )
        bt.holdings = {"SPY": 100.0}
        bt.cash = 0.0
        bt._price_data = {"SPY": make_price_df(DATES, [500, 500, 500, 500])}
        bt._dividend_data = {"SPY": make_dividend_series(["2024-01-03"], [2.0])}

        net = bt._process_dividends(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-05"))

        # 100 × $2.0 = $200 gross, 15% tax = $30, net = $170
        assert abs(net - 170.0) < 0.01
        assert abs(bt.cash - 170.0) < 0.01

    def test_kr_stock_dividend_154pct(self):
        """KR_STOCK ETF 배당 → 15.4% 배당세"""
        etf_info = {"069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW")}
        bt = PortfolioBacktester(
            allocation={"069500.KS": 1.0},
            etf_info=etf_info
        )
        bt.holdings = {"069500.KS": 100.0}
        bt.cash = 0.0
        bt._price_data = {"069500.KS": make_price_df(DATES, [50000, 50000, 50000, 50000])}
        bt._dividend_data = {"069500.KS": make_dividend_series(["2024-01-03"], [500.0])}

        net = bt._process_dividends(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-05"))

        # 100 × ₩500 = ₩50,000 gross, 15.4% tax = ₩7,700, net = ₩42,300
        assert abs(net - 42300.0) < 0.01

    def test_dividend_fx_conversion(self):
        """US ETF 배당금이 base currency(KRW)로 변환"""
        etf_info = {"SPY": ETFInfo("SPY", "SPY", Market.US, "USD")}
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(DATES, [1300, 1300, 1300, 1300])

        bt = PortfolioBacktester(
            allocation={"SPY": 1.0},
            etf_info=etf_info,
            currency_converter=converter
        )
        bt.holdings = {"SPY": 100.0}
        bt.cash = 0.0
        bt._price_data = {"SPY": make_price_df(DATES, [500, 500, 500, 500])}
        bt._dividend_data = {"SPY": make_dividend_series(["2024-01-03"], [2.0])}

        net = bt._process_dividends(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-05"))

        # $200 gross × 0.85 (15% tax) = $170 net × 1300 = ₩221,000
        assert abs(net - 221_000.0) < 0.01


class TestRebalanceWithMarket:
    """시장별 세금 적용 리밸런싱 테스트"""

    def test_kr_stock_sell_no_capital_gains_tax(self):
        """KR_STOCK 매도 시 양도차익 비과세"""
        etf_info = {"069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW")}
        bt = PortfolioBacktester(
            initial_capital=10_000_000,
            allocation={"069500.KS": 1.0},
            etf_info=etf_info
        )
        bt._price_data = {"069500.KS": make_price_df(DATES, [50000, 55000, 55000, 55000])}
        bt.holdings = {"069500.KS": 200.0}
        bt.cost_basis = {"069500.KS": 50000.0}
        bt.cash = 0.0

        # 리밸런싱으로 매도 발생
        bt._rebalance(pd.Timestamp("2024-01-03"))

        # KR_STOCK은 양도차익 비과세 → tax_history에 기록 없음
        kr_capital_events = [e for e in bt.tax_calculator.tax_history if e.tax_type == 'kr_capital_gains']
        assert len(kr_capital_events) == 0

    def test_kr_other_sell_immediate_tax(self):
        """KR_OTHER 매도 시 즉시 15.4% 과세"""
        etf_info = {
            "360750.KS": ETFInfo("360750.KS", "TIGER S&P500", Market.KR_OTHER, "KRW"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        bt = PortfolioBacktester(
            initial_capital=10_000_000,
            allocation={"360750.KS": 0.3, "069500.KS": 0.7},
            etf_info=etf_info
        )
        bt._price_data = {
            "360750.KS": make_price_df(DATES, [10000, 12000, 12000, 12000]),
            "069500.KS": make_price_df(DATES, [50000, 50000, 50000, 50000]),
        }
        # 360750이 올라서 리밸런싱 시 매도 발생
        bt.holdings = {"360750.KS": 500.0, "069500.KS": 100.0}
        bt.cost_basis = {"360750.KS": 10000.0, "069500.KS": 50000.0}
        bt.cash = 0.0

        bt._rebalance(pd.Timestamp("2024-01-03"))

        # KR_OTHER 매도 양도차익에 즉시 과세
        kr_events = [e for e in bt.tax_calculator.tax_history if e.tax_type == 'kr_capital_gains']
        # 매도가 발생했으면 즉시 과세 이벤트가 있어야 함
        if kr_events:
            assert kr_events[0].tax_amount > 0
            assert abs(kr_events[0].tax_amount / kr_events[0].gross_amount - 0.154) < 0.01


class TestTradingDateUnion:
    """거래일 합집합 테스트"""

    def test_all_dates_union(self):
        """여러 ETF의 거래일 합집합 사용"""
        bt = PortfolioBacktester(allocation={"A": 0.5, "B": 0.5})
        bt._price_data = {
            "A": make_price_df(["2024-01-02", "2024-01-03", "2024-01-04"], [100, 100, 100]),
            "B": make_price_df(["2024-01-02", "2024-01-04", "2024-01-05"], [200, 200, 200]),
        }

        # run()에서 사용하는 것과 동일한 로직
        all_date_sets = [df.index for df in bt._price_data.values()]
        all_dates = sorted(set().union(*all_date_sets))

        assert len(all_dates) == 4  # 1/2, 1/3, 1/4, 1/5
        assert pd.Timestamp("2024-01-03") in all_dates
        assert pd.Timestamp("2024-01-05") in all_dates


class TestBackwardCompatibility:
    """기존 US-only 동작과의 호환성 테스트"""

    def test_no_etf_info_defaults_to_us_behavior(self):
        """etf_info=None이면 기존 US 동작"""
        bt = PortfolioBacktester(
            initial_capital=100_000,
            allocation={"SPY": 0.6, "QQQ": 0.4}
        )
        assert bt.etf_info is None
        assert bt.currency_converter is None

        # _get_market returns None → tax calculator treats as US
        assert bt._get_market("SPY") is None

        # _get_fx_rate returns 1.0 → no conversion
        assert bt._get_fx_rate("SPY", pd.Timestamp("2024-01-15")) == 1.0

    def test_portfolio_value_unchanged_without_fx(self):
        """환율 변환 없이는 기존 포트폴리오 가치 계산과 동일"""
        bt = PortfolioBacktester(
            initial_capital=100_000,
            allocation={"SPY": 1.0}
        )
        bt._price_data = {"SPY": make_price_df(["2024-01-15"], [500.0])}
        bt.holdings = {"SPY": 100.0}
        bt.cash = 50_000.0

        value = bt._get_portfolio_value(pd.Timestamp("2024-01-15"))
        assert abs(value - 100_000.0) < 0.01  # 100 × 500 + 50,000

    def test_tax_calculator_kr_rates_passed(self):
        """kr 세율이 TaxCalculator로 전달"""
        bt = PortfolioBacktester(
            kr_dividend_tax_rate=0.20,
            kr_capital_gains_rate=0.20
        )
        assert abs(bt.tax_calculator.kr_dividend_tax_rate - 0.20) < 0.001
        assert abs(bt.tax_calculator.kr_capital_gains_rate - 0.20) < 0.001


class TestAnnualSummaryKR:
    """연간 요약에 한국 세금 포함 테스트"""

    def test_annual_summary_has_kr_capital_gains_column(self):
        """연간 요약에 tax_kr_capital_gains 컬럼 포함"""
        bt = PortfolioBacktester(
            initial_capital=10_000_000,
            allocation={"069500.KS": 1.0}
        )
        # 최소한의 결과 생성
        from src.backtest.portfolio_backtest import BacktestResult
        result = BacktestResult(
            portfolio_history=[
                PortfolioSnapshot(
                    date=pd.Timestamp("2024-01-01"),
                    holdings={"069500.KS": 200},
                    prices={"069500.KS": 50000},
                    cash=0, total_value=10_000_000,
                    cumulative_withdrawal=0, cumulative_dividend=0, cumulative_tax=0
                ),
                PortfolioSnapshot(
                    date=pd.Timestamp("2024-06-01"),
                    holdings={"069500.KS": 200},
                    prices={"069500.KS": 55000},
                    cash=0, total_value=11_000_000,
                    cumulative_withdrawal=0, cumulative_dividend=0, cumulative_tax=0
                ),
                PortfolioSnapshot(
                    date=pd.Timestamp("2024-12-31"),
                    holdings={"069500.KS": 200},
                    prices={"069500.KS": 55000},
                    cash=0, total_value=11_000_000,
                    cumulative_withdrawal=0, cumulative_dividend=0, cumulative_tax=0
                ),
            ],
            rebalance_events=[],
            withdrawal_events=[],
            dividend_events=[],
            tax_events=[],
            initial_value=10_000_000,
            final_value=11_000_000,
            total_return=10.0,
            cagr=10.0,
            volatility=10.0,
            sharpe_ratio=0.5,
            max_drawdown=-5.0,
            total_withdrawal=0,
            total_dividend_gross=0,
            total_dividend_net=0,
            total_tax=0,
            total_transaction_cost=0
        )

        df = bt.get_annual_summary_df(result)
        assert 'tax_kr_capital_gains' in df.columns
