"""
Buy-and-hold 성과 지표 계산 테스트
"""
import numpy as np
import pandas as pd
import pytest

from src.backtest.index_metrics import compute_buy_hold_metrics


def _daily_series(values, start="2020-01-01"):
    """일별(거래일) 가격 Series 생성"""
    index = pd.bdate_range(start=start, periods=len(values))
    return pd.Series(values, index=index, dtype=float)


class TestTotalReturn:
    def test_doubling_gives_100_percent(self):
        prices = _daily_series([100.0, 150.0, 200.0])
        metrics = compute_buy_hold_metrics(prices)
        assert abs(metrics["total_return"] - 100.0) < 1e-9

    def test_flat_gives_zero(self):
        prices = _daily_series([100.0] * 5)
        metrics = compute_buy_hold_metrics(prices)
        assert abs(metrics["total_return"]) < 1e-9


class TestCAGR:
    def test_one_year_doubling(self):
        """1년에 2배 → CAGR ≈ 100%"""
        index = pd.DatetimeIndex(["2020-01-01", "2021-01-01"])
        prices = pd.Series([100.0, 200.0], index=index)
        metrics = compute_buy_hold_metrics(prices)
        # 365/365.25 년 → 거의 100%
        assert 99.0 < metrics["cagr"] < 101.0

    def test_two_year_quadrupling(self):
        """2년에 4배 → CAGR ≈ 100%"""
        index = pd.DatetimeIndex(["2020-01-01", "2022-01-01"])
        prices = pd.Series([100.0, 400.0], index=index)
        metrics = compute_buy_hold_metrics(prices)
        assert 99.0 < metrics["cagr"] < 101.0


class TestMaxDrawdown:
    def test_peak_to_trough(self):
        """100 → 200 → 100 : 고점 대비 -50%"""
        prices = _daily_series([100.0, 200.0, 100.0])
        metrics = compute_buy_hold_metrics(prices)
        assert abs(metrics["max_drawdown"] - (-50.0)) < 1e-9

    def test_monotonic_increase_no_drawdown(self):
        prices = _daily_series([100.0, 110.0, 120.0, 130.0])
        metrics = compute_buy_hold_metrics(prices)
        assert abs(metrics["max_drawdown"]) < 1e-9


class TestVolatilityAndSharpe:
    def test_zero_volatility_zero_sharpe(self):
        """변동 없는 시계열 → 변동성 0, 샤프 0"""
        prices = _daily_series([100.0] * 10)
        metrics = compute_buy_hold_metrics(prices)
        assert abs(metrics["volatility"]) < 1e-9
        assert metrics["sharpe_ratio"] == 0.0

    def test_volatility_annualized_with_252(self):
        """일별 수익률 표준편차 × √252 × 100 으로 연율화"""
        prices = _daily_series([100.0, 110.0, 100.0, 110.0, 100.0])
        metrics = compute_buy_hold_metrics(prices)
        daily_returns = prices.pct_change().dropna()
        expected = daily_returns.std() * np.sqrt(252) * 100
        assert abs(metrics["volatility"] - expected) < 1e-9

    def test_sharpe_uses_cagr_and_risk_free(self):
        prices = _daily_series([100.0, 102.0, 101.0, 103.0, 105.0])
        metrics = compute_buy_hold_metrics(prices, risk_free_rate=0.03)
        expected = (metrics["cagr"] / 100 - 0.03) / (metrics["volatility"] / 100)
        assert abs(metrics["sharpe_ratio"] - expected) < 1e-9


class TestInputValidation:
    def test_single_point_raises(self):
        prices = _daily_series([100.0])
        with pytest.raises(ValueError):
            compute_buy_hold_metrics(prices)

    def test_empty_raises(self):
        prices = pd.Series([], dtype=float)
        with pytest.raises(ValueError):
            compute_buy_hold_metrics(prices)
