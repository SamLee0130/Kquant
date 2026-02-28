"""
PortfolioOptimizer 단위 테스트

yfinance를 모킹하여 네트워크 호출 없이 포트폴리오 최적화 엔진을 검증합니다.
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock

from src.optimizer.portfolio_optimizer import PortfolioOptimizer


# --- Helper: 현실적인 가격 데이터 생성 ---

def generate_realistic_prices(tickers, n_days=400, seed=42):
    """
    현실적인 주가 데이터를 생성합니다.
    GBM(기하 브라운 운동) 기반으로 각 티커별 서로 다른 수익률/변동성 제공.
    """
    rng = np.random.RandomState(seed)
    dates = pd.bdate_range("2022-01-03", periods=n_days)

    params = {
        "ETF_A": {"start": 100, "mu": 0.10, "sigma": 0.15},
        "ETF_B": {"start": 50, "mu": 0.05, "sigma": 0.10},
        "ETF_C": {"start": 200, "mu": 0.08, "sigma": 0.20},
        "ETF_D": {"start": 75, "mu": 0.12, "sigma": 0.25},
    }

    data = {}
    for ticker in tickers:
        p = params.get(ticker, {"start": 100, "mu": 0.07, "sigma": 0.15})
        daily_returns = rng.normal(p["mu"] / 252, p["sigma"] / np.sqrt(252), n_days)
        prices = p["start"] * np.cumprod(1 + daily_returns)
        data[ticker] = prices

    return pd.DataFrame(data, index=dates)


def create_optimizer_with_mock_data(tickers, n_days=400, seed=42):
    """테스트용 옵티마이저 생성 (데이터 직접 주입)"""
    opt = PortfolioOptimizer(tickers=tickers, period_years=5)

    prices = generate_realistic_prices(tickers, n_days=n_days, seed=seed)
    opt._price_data = prices

    from pypfopt import expected_returns, risk_models
    opt._mu = expected_returns.mean_historical_return(prices)
    opt._S = risk_models.sample_cov(prices)

    return opt


# --- 입력 검증 테스트 ---

class TestInputValidation:
    """입력 검증 테스트"""

    def test_less_than_2_tickers_raises_error(self):
        """티커가 2개 미만이면 ValueError"""
        with pytest.raises(ValueError, match="최소 2개"):
            PortfolioOptimizer(tickers=["SPY"])

    def test_single_ticker_raises_error(self):
        """단일 티커도 ValueError"""
        with pytest.raises(ValueError, match="최소 2개"):
            PortfolioOptimizer(tickers=["SPY"])

    def test_empty_tickers_raises_error(self):
        """빈 리스트도 ValueError"""
        with pytest.raises(ValueError, match="최소 2개"):
            PortfolioOptimizer(tickers=[])

    def test_more_than_10_tickers_raises_error(self):
        """티커가 10개 초과하면 ValueError"""
        tickers = [f"ETF_{i}" for i in range(11)]
        with pytest.raises(ValueError, match="최대 10개"):
            PortfolioOptimizer(tickers=tickers)

    def test_exactly_2_tickers_ok(self):
        """티커 2개는 정상"""
        opt = PortfolioOptimizer(tickers=["ETF_A", "ETF_B"])
        assert len(opt.tickers) == 2

    def test_exactly_10_tickers_ok(self):
        """티커 10개는 정상"""
        tickers = [f"ETF_{i}" for i in range(10)]
        opt = PortfolioOptimizer(tickers=tickers)
        assert len(opt.tickers) == 10


# --- Max Sharpe 최적화 테스트 ---

class TestOptimizeMaxSharpe:
    """Max Sharpe Ratio 최적화 테스트"""

    def test_weights_sum_to_one(self):
        """비중 합계가 ~1.0"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_max_sharpe()

        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_all_weights_non_negative(self):
        """모든 비중이 >= 0"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_max_sharpe()

        for w in weights.values():
            assert w >= -0.01  # clean_weights에 의한 미세 오차 허용

    def test_returns_dict_with_correct_tickers(self):
        """올바른 티커가 포함된 딕셔너리 반환"""
        tickers = ["ETF_A", "ETF_B"]
        opt = create_optimizer_with_mock_data(tickers)
        weights = opt.optimize_max_sharpe()

        assert set(weights.keys()) == set(tickers)

    def test_two_ticker_weights(self):
        """2개 티커 최적화도 정상 동작"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B"])
        weights = opt.optimize_max_sharpe()

        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)


# --- Min Volatility 최적화 테스트 ---

class TestOptimizeMinVolatility:
    """Min Volatility 최적화 테스트"""

    def test_weights_sum_to_one(self):
        """비중 합계가 ~1.0"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_min_volatility()

        assert sum(weights.values()) == pytest.approx(1.0, abs=0.01)

    def test_all_weights_non_negative(self):
        """모든 비중이 >= 0"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_min_volatility()

        for w in weights.values():
            assert w >= -0.01

    def test_returns_dict_with_correct_tickers(self):
        """올바른 티커 포함"""
        tickers = ["ETF_A", "ETF_B", "ETF_C"]
        opt = create_optimizer_with_mock_data(tickers)
        weights = opt.optimize_min_volatility()

        assert set(weights.keys()) == set(tickers)


# --- 성과 지표 테스트 ---

class TestGetPerformanceMetrics:
    """성과 지표 계산 테스트"""

    def test_returns_expected_keys(self):
        """expected_return, volatility, sharpe_ratio 키 반환"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_max_sharpe()
        metrics = opt.get_performance_metrics(weights)

        assert "expected_return" in metrics
        assert "volatility" in metrics
        assert "sharpe_ratio" in metrics

    def test_volatility_positive(self):
        """변동성은 항상 양수"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        weights = opt.optimize_max_sharpe()
        metrics = opt.get_performance_metrics(weights)

        assert metrics["volatility"] > 0

    def test_equal_weight_metrics(self):
        """동일 비중 포트폴리오 지표"""
        tickers = ["ETF_A", "ETF_B"]
        opt = create_optimizer_with_mock_data(tickers)
        weights = {"ETF_A": 0.5, "ETF_B": 0.5}
        metrics = opt.get_performance_metrics(weights)

        assert isinstance(metrics["expected_return"], float)
        assert isinstance(metrics["volatility"], float)
        assert isinstance(metrics["sharpe_ratio"], float)


# --- Efficient Frontier 테스트 ---

class TestGetEfficientFrontier:
    """Efficient Frontier 곡선 데이터 테스트"""

    def test_returns_correct_shapes(self):
        """volatilities, returns 배열의 shape 확인"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        vols, rets, weights_list = opt.get_efficient_frontier(n_points=20)

        assert len(vols) == len(rets)
        assert len(vols) == len(weights_list)
        assert len(vols) > 0

    def test_volatilities_are_positive(self):
        """변동성 배열의 모든 값이 양수"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        vols, _, _ = opt.get_efficient_frontier(n_points=20)

        assert (vols > 0).all()

    def test_returns_are_numpy_arrays(self):
        """반환값이 numpy 배열"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        vols, rets, _ = opt.get_efficient_frontier(n_points=10)

        assert isinstance(vols, np.ndarray)
        assert isinstance(rets, np.ndarray)

    def test_weights_list_entries_sum_to_one(self):
        """각 포인트의 비중 합이 ~1.0"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B", "ETF_C"])
        _, _, weights_list = opt.get_efficient_frontier(n_points=10)

        for weights in weights_list:
            assert sum(weights.values()) == pytest.approx(1.0, abs=0.02)


# --- 개별 자산 정보 테스트 ---

class TestGetIndividualAssets:
    """개별 자산 수익률/변동성 정보 테스트"""

    def test_returns_dataframe(self):
        """DataFrame 반환"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B"])
        df = opt.get_individual_assets()

        assert isinstance(df, pd.DataFrame)

    def test_correct_columns(self):
        """올바른 컬럼 포함"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B"])
        df = opt.get_individual_assets()

        assert set(df.columns) == {"ticker", "expected_return", "volatility"}

    def test_correct_number_of_rows(self):
        """티커 수만큼 행"""
        tickers = ["ETF_A", "ETF_B", "ETF_C"]
        opt = create_optimizer_with_mock_data(tickers)
        df = opt.get_individual_assets()

        assert len(df) == len(tickers)

    def test_volatility_positive(self):
        """개별 자산 변동성은 양수"""
        opt = create_optimizer_with_mock_data(["ETF_A", "ETF_B"])
        df = opt.get_individual_assets()

        assert (df["volatility"] > 0).all()

    def test_tickers_match(self):
        """티커가 입력과 일치"""
        tickers = ["ETF_A", "ETF_B"]
        opt = create_optimizer_with_mock_data(tickers)
        df = opt.get_individual_assets()

        assert set(df["ticker"].tolist()) == set(tickers)


# --- fetch_data 모킹 테스트 ---

class TestFetchDataMocked:
    """데이터 캐싱 레이어 모킹을 통한 fetch_data 테스트"""

    @patch("src.optimizer.portfolio_optimizer.fetch_adjusted_prices")
    def test_fetch_data_stores_price_data(self, mock_fetch):
        """fetch_data가 가격 데이터를 저장"""
        prices_df = generate_realistic_prices(["ETF_A", "ETF_B"], n_days=300)
        mock_fetch.return_value = prices_df

        opt = PortfolioOptimizer(tickers=["ETF_A", "ETF_B"], period_years=2)
        prices = opt.fetch_data()

        assert opt._price_data is not None
        assert opt._mu is not None
        assert opt._S is not None
        assert len(prices) > 0
        mock_fetch.assert_called_once()
