"""
PortfolioBacktester 단위 테스트

yfinance를 모킹하여 네트워크 호출 없이 백테스트 엔진을 검증합니다.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from datetime import datetime

from src.backtest.portfolio_backtest import PortfolioBacktester, BacktestResult, PortfolioSnapshot


# --- Helper: 테스트용 가격/배당 데이터 생성 ---

def make_price_df(dates, prices):
    """가격 DataFrame 생성 (symbol별 _price_data 형식)"""
    df = pd.DataFrame({"price": prices}, index=pd.DatetimeIndex(dates))
    return df


def make_dividend_series(dates, amounts):
    """배당 Series 생성"""
    return pd.Series(amounts, index=pd.DatetimeIndex(dates), dtype=float)


def make_empty_dividend_series():
    """빈 배당 Series 생성 (DatetimeIndex 유지)"""
    return pd.Series(dtype=float, index=pd.DatetimeIndex([], dtype="datetime64[ns]"))


def create_backtester_with_data(
    allocation=None,
    price_data=None,
    dividend_data=None,
    initial_capital=100000,
    rebalance_frequency="quarterly",
    withdrawal_rate=0.0,
    transaction_cost_rate=0.0,
):
    """테스트용 백테스터 생성 (yfinance 모킹 불필요, 직접 데이터 주입)"""
    bt = PortfolioBacktester(
        initial_capital=initial_capital,
        allocation=allocation or {"ETF_A": 0.6, "ETF_B": 0.4},
        rebalance_frequency=rebalance_frequency,
        withdrawal_rate=withdrawal_rate,
        dividend_tax_rate=0.15,
        capital_gains_tax_rate=0.22,
        capital_gains_exemption=2000.0,
        transaction_cost_rate=transaction_cost_rate,
    )

    if price_data:
        bt._price_data = price_data
    if dividend_data:
        bt._dividend_data = dividend_data
    else:
        # 배당 없음 기본값 (DatetimeIndex 유지)
        for symbol in (allocation or {"ETF_A": 0.6, "ETF_B": 0.4}):
            bt._dividend_data[symbol] = make_empty_dividend_series()

    return bt


# --- 공통 테스트 데이터 ---

TRADE_DATES = pd.bdate_range("2024-01-02", periods=20)

PRICE_DATA_A = make_price_df(TRADE_DATES, [100.0 + i * 0.5 for i in range(20)])
PRICE_DATA_B = make_price_df(TRADE_DATES, [50.0 + i * 0.25 for i in range(20)])


class TestGetPrice:
    """_get_price 메서드 테스트"""

    def test_exact_date(self):
        """정확한 날짜의 가격 조회"""
        bt = create_backtester_with_data(price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B})
        price = bt._get_price("ETF_A", TRADE_DATES[0])
        assert price == pytest.approx(100.0)

    def test_forward_lookup(self):
        """비거래일일 때 직후 거래일 가격 사용"""
        bt = create_backtester_with_data(price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B})
        # 2024-01-01 (월요일 전 일요일 등) -> 첫 거래일 가격
        price = bt._get_price("ETF_A", pd.Timestamp("2024-01-01"))
        assert price == pytest.approx(100.0)

    def test_backward_lookup(self):
        """미래 데이터가 없으면 직전 거래일 가격 사용"""
        bt = create_backtester_with_data(price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B})
        # 모든 거래일 이후 날짜
        future_date = TRADE_DATES[-1] + pd.Timedelta(days=5)
        price = bt._get_price("ETF_A", future_date)
        assert price == pytest.approx(100.0 + 19 * 0.5)

    def test_unknown_symbol(self):
        """존재하지 않는 심볼 조회 시 None"""
        bt = create_backtester_with_data(price_data={"ETF_A": PRICE_DATA_A})
        assert bt._get_price("UNKNOWN", TRADE_DATES[0]) is None


class TestGetPortfolioValue:
    """_get_portfolio_value 테스트"""

    def test_cash_only(self):
        """보유 주식 없이 현금만 있을 때"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=50000,
        )
        bt.cash = 50000.0
        bt.holdings = {}

        value = bt._get_portfolio_value(TRADE_DATES[0])
        assert value == pytest.approx(50000.0)

    def test_holdings_plus_cash(self):
        """보유 주식 + 현금"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
        )
        bt.cash = 1000.0
        bt.holdings = {"ETF_A": 100, "ETF_B": 200}

        # ETF_A: 100 * 100.0 = 10000, ETF_B: 200 * 50.0 = 10000, cash = 1000
        value = bt._get_portfolio_value(TRADE_DATES[0])
        assert value == pytest.approx(21000.0)


class TestGetRebalanceDates:
    """_get_rebalance_dates 테스트"""

    def test_quarterly(self):
        """분기별 리밸런싱 날짜"""
        bt = create_backtester_with_data(rebalance_frequency="quarterly")
        dates = bt._get_rebalance_dates(datetime(2024, 1, 1), datetime(2024, 12, 31))

        expected = [
            pd.Timestamp("2024-01-01"),
            pd.Timestamp("2024-04-01"),
            pd.Timestamp("2024-07-01"),
            pd.Timestamp("2024-10-01"),
        ]
        assert dates == expected

    def test_yearly(self):
        """연간 리밸런싱 날짜"""
        bt = create_backtester_with_data(rebalance_frequency="yearly")
        dates = bt._get_rebalance_dates(datetime(2022, 1, 1), datetime(2024, 12, 31))

        expected = [
            pd.Timestamp("2022-01-01"),
            pd.Timestamp("2023-01-01"),
            pd.Timestamp("2024-01-01"),
        ]
        assert dates == expected

    def test_quarterly_partial_year(self):
        """연 중간부터 시작하는 분기별 리밸런싱"""
        bt = create_backtester_with_data(rebalance_frequency="quarterly")
        dates = bt._get_rebalance_dates(datetime(2024, 3, 15), datetime(2024, 9, 30))

        # 3월 15일 이후이므로 4월 1일, 7월 1일이 포함
        assert pd.Timestamp("2024-04-01") in dates
        assert pd.Timestamp("2024-07-01") in dates


class TestRebalance:
    """_rebalance 테스트"""

    def test_initial_rebalance_trades(self):
        """리밸런싱 시 거래가 올바르게 계산"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=100000,
            transaction_cost_rate=0.002,
        )
        bt.cash = 100000.0
        bt.holdings = {}

        # 초기 매수 실행
        bt._execute_initial_purchase(TRADE_DATES[0])

        # 보유 확인: ETF_A 60%, ETF_B 40%
        # ETF_A: 60000 / 100.0 = 600 shares
        # ETF_B: 40000 / 50.0 = 800 shares
        assert bt.holdings["ETF_A"] == pytest.approx(600.0)
        assert bt.holdings["ETF_B"] == pytest.approx(800.0)

    def test_rebalance_with_transaction_costs(self):
        """리밸런싱 시 거래비용 차감"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=100000,
            transaction_cost_rate=0.01,  # 1% for easy calculation
        )
        # 편향된 보유량 설정 (리밸런싱 필요)
        bt.cash = 0.0
        bt.holdings = {"ETF_A": 800, "ETF_B": 400}
        bt.cost_basis = {"ETF_A": 100.0, "ETF_B": 50.0}

        initial_cost = bt.total_transaction_cost
        bt._rebalance(TRADE_DATES[0])

        assert bt.total_transaction_cost > initial_cost

    def test_rebalance_records_capital_gains(self):
        """리밸런싱 매도 시 양도차익 기록"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=100000,
            transaction_cost_rate=0.0,
        )
        # ETF_A 가격이 올랐으나 비중이 너무 높아서 매도 필요
        bt.cash = 0.0
        bt.holdings = {"ETF_A": 800, "ETF_B": 400}  # ETF_A 과다
        bt.cost_basis = {"ETF_A": 90.0, "ETF_B": 50.0}  # 매수가 90, 현재가 100

        event = bt._rebalance(TRADE_DATES[0])

        # 매도가 발생했으면 양도차익이 기록되어야 함
        assert event["capital_gain"] != 0.0 or len(event["trades"]) == 0


class TestProcessWithdrawal:
    """_process_withdrawal 테스트"""

    def test_withdrawal_from_cash_first(self):
        """현금에서 우선 인출"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=100000,
            withdrawal_rate=0.04,  # 4% yearly = 1% quarterly
            rebalance_frequency="quarterly",
        )
        bt.cash = 50000.0
        bt.holdings = {"ETF_A": 300, "ETF_B": 400}

        # 포트폴리오 가치: 50000 + 300*100 + 400*50 = 100000
        # 분기별 인출: 100000 * 0.01 = 1000
        event = bt._process_withdrawal(TRADE_DATES[0], 0.0)

        assert event["target_withdrawal"] == pytest.approx(1000.0)
        # 현금이 충분하므로 포트폴리오 매도 없음
        assert event["from_portfolio"] == pytest.approx(0.0)

    def test_withdrawal_sells_when_cash_insufficient(self):
        """현금 부족 시 포트폴리오에서 매도"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            initial_capital=100000,
            withdrawal_rate=0.20,  # 큰 인출률
            rebalance_frequency="quarterly",
        )
        bt.cash = 100.0  # 현금 적음
        bt.holdings = {"ETF_A": 600, "ETF_B": 800}
        bt.cost_basis = {"ETF_A": 100.0, "ETF_B": 50.0}

        event = bt._process_withdrawal(TRADE_DATES[0], 0.0)

        # 포트폴리오에서 매도가 발생해야 함
        assert event["from_portfolio"] > 0


class TestProcessDividends:
    """_process_dividends 테스트"""

    def test_dividend_net_added_to_cash(self):
        """세후 배당금이 현금에 추가"""
        div_data = {
            "ETF_A": make_dividend_series(
                [pd.Timestamp("2024-01-10")], [2.0]  # $2 per share
            ),
            "ETF_B": make_empty_dividend_series(),
        }
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            dividend_data=div_data,
        )
        bt.cash = 0.0
        bt.holdings = {"ETF_A": 100, "ETF_B": 200}

        net_div = bt._process_dividends(
            pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31")
        )

        # gross: 100 * 2.0 = 200, tax: 200 * 0.15 = 30, net: 170
        assert net_div == pytest.approx(170.0)
        assert bt.cash == pytest.approx(170.0)

    def test_dividend_tax_event_created(self):
        """배당세 이벤트가 생성"""
        div_data = {
            "ETF_A": make_dividend_series(
                [pd.Timestamp("2024-01-10")], [1.0]
            ),
            "ETF_B": make_empty_dividend_series(),
        }
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
            dividend_data=div_data,
        )
        bt.cash = 0.0
        bt.holdings = {"ETF_A": 50, "ETF_B": 0}

        bt._process_dividends(pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31"))

        assert len(bt.dividend_events) == 1
        event = bt.dividend_events[0]
        assert event["symbol"] == "ETF_A"
        assert event["gross_dividend"] == pytest.approx(50.0)
        assert event["tax"] == pytest.approx(7.5)
        assert event["net_dividend"] == pytest.approx(42.5)

    def test_no_dividends_in_period(self):
        """기간 내 배당 없으면 0 반환"""
        bt = create_backtester_with_data(
            price_data={"ETF_A": PRICE_DATA_A, "ETF_B": PRICE_DATA_B},
        )
        bt.cash = 1000.0
        bt.holdings = {"ETF_A": 100, "ETF_B": 200}

        net_div = bt._process_dividends(
            pd.Timestamp("2024-01-01"), pd.Timestamp("2024-01-31")
        )

        assert net_div == pytest.approx(0.0)
        assert bt.cash == pytest.approx(1000.0)


class TestCalculateMetrics:
    """_calculate_metrics 테스트"""

    def test_total_return(self):
        """총 수익률 계산"""
        bt = create_backtester_with_data(initial_capital=100000)
        snapshots = [
            PortfolioSnapshot(
                date=pd.Timestamp("2024-01-01"), holdings={}, prices={},
                cash=100000, total_value=100000, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            ),
            PortfolioSnapshot(
                date=pd.Timestamp("2024-07-01"), holdings={}, prices={},
                cash=110000, total_value=110000, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            ),
        ]

        metrics = bt._calculate_metrics(
            snapshots, pd.Timestamp("2024-01-01"), pd.Timestamp("2024-07-01"), 110000
        )

        # (110000 / 100000 - 1) * 100 = 10%
        assert metrics["total_return"] == pytest.approx(10.0)

    def test_cagr(self):
        """CAGR 계산"""
        bt = create_backtester_with_data(initial_capital=100000)
        start = pd.Timestamp("2022-01-01")
        end = pd.Timestamp("2024-01-01")  # 2 years
        final_value = 121000  # ~10% CAGR

        snapshots = [
            PortfolioSnapshot(
                date=start, holdings={}, prices={}, cash=100000,
                total_value=100000, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            ),
            PortfolioSnapshot(
                date=end, holdings={}, prices={}, cash=121000,
                total_value=121000, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            ),
        ]

        metrics = bt._calculate_metrics(snapshots, start, end, final_value)

        years = (end - start).days / 365.25
        expected_cagr = ((121000 / 100000) ** (1 / years) - 1) * 100
        assert metrics["cagr"] == pytest.approx(expected_cagr, rel=0.01)

    def test_max_drawdown(self):
        """최대 낙폭(MDD) 계산"""
        bt = create_backtester_with_data(initial_capital=100000)
        values = [100000, 120000, 90000, 110000]  # peak 120k, trough 90k
        dates = pd.date_range("2024-01-01", periods=4, freq="ME")
        snapshots = [
            PortfolioSnapshot(
                date=d, holdings={}, prices={}, cash=v,
                total_value=v, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            )
            for d, v in zip(dates, values)
        ]

        metrics = bt._calculate_metrics(snapshots, dates[0], dates[-1], values[-1])

        # MDD = (90000 - 120000) / 120000 = -25%
        assert metrics["max_drawdown"] == pytest.approx(-25.0)

    def test_sharpe_ratio_positive(self):
        """양의 수익률에서 샤프비율 > 0"""
        bt = create_backtester_with_data(initial_capital=100000)
        # 꾸준히 상승
        values = [100000 + i * 1000 for i in range(12)]
        dates = pd.date_range("2024-01-01", periods=12, freq="ME")
        snapshots = [
            PortfolioSnapshot(
                date=d, holdings={}, prices={}, cash=v,
                total_value=v, cumulative_withdrawal=0,
                cumulative_dividend=0, cumulative_tax=0,
            )
            for d, v in zip(dates, values)
        ]

        metrics = bt._calculate_metrics(snapshots, dates[0], dates[-1], values[-1])

        assert metrics["sharpe_ratio"] > 0


class TestDataFrameOutputs:
    """DataFrame 출력 테스트"""

    def test_portfolio_history_df_structure(self):
        """포트폴리오 히스토리 DataFrame 구조"""
        bt = create_backtester_with_data(allocation={"ETF_A": 0.6, "ETF_B": 0.4})

        snapshots = [
            PortfolioSnapshot(
                date=pd.Timestamp("2024-01-01"),
                holdings={"ETF_A": 600, "ETF_B": 800},
                prices={"ETF_A": 100.0, "ETF_B": 50.0},
                cash=1000,
                total_value=101000,
                cumulative_withdrawal=0,
                cumulative_dividend=0,
                cumulative_tax=0,
            ),
        ]

        result = BacktestResult(
            portfolio_history=snapshots,
            rebalance_events=[],
            withdrawal_events=[],
            dividend_events=[],
            tax_events=[],
            initial_value=100000,
            final_value=101000,
            total_return=1.0,
            cagr=1.0,
            volatility=10.0,
            sharpe_ratio=0.5,
            max_drawdown=-5.0,
            total_withdrawal=0,
            total_dividend_gross=0,
            total_dividend_net=0,
            total_tax=0,
            total_transaction_cost=0,
        )

        df = bt.get_portfolio_history_df(result)

        assert "date" in df.columns
        assert "total_value" in df.columns
        assert "cash" in df.columns
        assert "ETF_A_shares" in df.columns
        assert "ETF_A_value" in df.columns
        assert "ETF_B_shares" in df.columns
        assert "ETF_B_value" in df.columns
        assert len(df) == 1

    def test_annual_summary_df_structure(self):
        """연간 요약 DataFrame 구조"""
        bt = create_backtester_with_data(allocation={"ETF_A": 0.6, "ETF_B": 0.4})

        snapshots = [
            PortfolioSnapshot(
                date=pd.Timestamp("2024-01-02"),
                holdings={"ETF_A": 600, "ETF_B": 800},
                prices={"ETF_A": 100.0, "ETF_B": 50.0},
                cash=1000,
                total_value=101000,
                cumulative_withdrawal=0,
                cumulative_dividend=0,
                cumulative_tax=0,
            ),
            PortfolioSnapshot(
                date=pd.Timestamp("2024-12-31"),
                holdings={"ETF_A": 600, "ETF_B": 800},
                prices={"ETF_A": 110.0, "ETF_B": 55.0},
                cash=1000,
                total_value=111000,
                cumulative_withdrawal=0,
                cumulative_dividend=0,
                cumulative_tax=0,
            ),
        ]

        result = BacktestResult(
            portfolio_history=snapshots,
            rebalance_events=[],
            withdrawal_events=[],
            dividend_events=[],
            tax_events=[],
            initial_value=100000,
            final_value=111000,
            total_return=11.0,
            cagr=11.0,
            volatility=10.0,
            sharpe_ratio=0.5,
            max_drawdown=-5.0,
            total_withdrawal=0,
            total_dividend_gross=0,
            total_dividend_net=0,
            total_tax=0,
            total_transaction_cost=0,
        )

        df = bt.get_annual_summary_df(result)

        expected_cols = {
            "year", "start_value", "start_value_after_capital_tax",
            "end_value", "return_pct", "withdrawal",
            "dividend_gross", "dividend_net",
            "tax_dividend", "tax_capital_gains", "transaction_cost",
        }
        assert expected_cols.issubset(set(df.columns))
        assert len(df) >= 1


class TestRunWithMockedData:
    """데이터 캐싱 레이어 모킹을 통한 run() 통합 테스트"""

    @patch("src.backtest.portfolio_backtest.fetch_dividend_data")
    @patch("src.backtest.portfolio_backtest.fetch_price_data")
    def test_run_basic(self, mock_fetch_price, mock_fetch_div):
        """기본 run() 실행 - 결과 구조 확인"""
        dates = pd.bdate_range("2023-01-02", "2024-06-30")

        price_a = pd.DataFrame(
            {"price": [100.0 + i * 0.1 for i in range(len(dates))]},
            index=dates,
        )
        price_b = pd.DataFrame(
            {"price": [50.0 + i * 0.05 for i in range(len(dates))]},
            index=dates,
        )

        div_a = pd.Series(
            [1.0, 1.0, 1.0, 1.0],
            index=pd.DatetimeIndex([
                "2023-03-15", "2023-06-15", "2023-09-15", "2023-12-15"
            ]),
        )

        def price_side_effect(symbol, start, end):
            return price_a if symbol == "ETF_A" else price_b

        def div_side_effect(symbol, start, end):
            if symbol == "ETF_A":
                return div_a
            return make_empty_dividend_series()

        mock_fetch_price.side_effect = price_side_effect
        mock_fetch_div.side_effect = div_side_effect

        bt = PortfolioBacktester(
            initial_capital=100000,
            allocation={"ETF_A": 0.6, "ETF_B": 0.4},
            rebalance_frequency="quarterly",
            withdrawal_rate=0.0,
            transaction_cost_rate=0.0,
        )

        result = bt.run(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 7, 1),
        )

        assert isinstance(result, BacktestResult)
        assert result.initial_value == 100000
        assert result.final_value > 0
        assert len(result.portfolio_history) > 0
        assert result.total_return != 0

    @patch("src.backtest.portfolio_backtest.fetch_dividend_data")
    @patch("src.backtest.portfolio_backtest.fetch_price_data")
    def test_run_with_withdrawal(self, mock_fetch_price, mock_fetch_div):
        """인출이 있는 run() 실행"""
        dates = pd.bdate_range("2023-01-02", "2024-06-30")

        price_a = pd.DataFrame(
            {"price": [100.0] * len(dates)},
            index=dates,
        )
        price_b = pd.DataFrame(
            {"price": [50.0] * len(dates)},
            index=dates,
        )

        def price_side_effect(symbol, start, end):
            return price_a if symbol == "ETF_A" else price_b

        def div_side_effect(symbol, start, end):
            return make_empty_dividend_series()

        mock_fetch_price.side_effect = price_side_effect
        mock_fetch_div.side_effect = div_side_effect

        bt = PortfolioBacktester(
            initial_capital=100000,
            allocation={"ETF_A": 0.6, "ETF_B": 0.4},
            rebalance_frequency="quarterly",
            withdrawal_rate=0.04,
            transaction_cost_rate=0.0,
        )

        result = bt.run(
            start_date=datetime(2023, 1, 1),
            end_date=datetime(2024, 7, 1),
        )

        # 인출이 발생했어야 함
        assert result.total_withdrawal > 0
        # 인출로 인해 최종 가치가 초기보다 감소
        assert result.final_value < result.initial_value
