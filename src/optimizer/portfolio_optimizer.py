"""
포트폴리오 최적화 엔진

PyPortfolioOpt를 활용한 Mean-Variance Optimization 구현
- Max Sharpe Ratio
- Min Volatility
- Efficient Frontier 시각화
"""
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, List, Tuple, Optional
from datetime import datetime, timedelta
import logging

from pypfopt import EfficientFrontier
from pypfopt import risk_models
from pypfopt import expected_returns

from config.settings import BACKTEST_CONSTANTS

logger = logging.getLogger(__name__)


class PortfolioOptimizer:
    """
    포트폴리오 최적화 클래스

    PyPortfolioOpt를 활용하여 Mean-Variance Optimization 수행

    Attributes:
        tickers: ETF 심볼 리스트
        period_years: 분석 기간 (년)
        risk_free_rate: 무위험수익률
    """

    def __init__(
        self,
        tickers: List[str],
        period_years: int = 5,
        risk_free_rate: float = None
    ):
        """
        Args:
            tickers: ETF 심볼 리스트 (2~10개)
            period_years: 과거 데이터 분석 기간 (년)
            risk_free_rate: 무위험수익률 (기본값: settings에서 로드)
        """
        if len(tickers) < 2:
            raise ValueError("최소 2개 이상의 티커가 필요합니다.")
        if len(tickers) > 10:
            raise ValueError("최대 10개까지 티커를 지정할 수 있습니다.")

        self.tickers = tickers
        self.period_years = period_years
        self.risk_free_rate = risk_free_rate or BACKTEST_CONSTANTS['risk_free_rate']

        self._price_data: Optional[pd.DataFrame] = None
        self._mu: Optional[pd.Series] = None  # 기대수익률
        self._S: Optional[pd.DataFrame] = None  # 공분산 행렬

    def fetch_data(self) -> pd.DataFrame:
        """
        yfinance에서 가격 데이터 조회

        Returns:
            조정 종가 DataFrame (columns: tickers)
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=self.period_years * 365)

        logger.info(f"Fetching data for {self.tickers} from {start_date} to {end_date}")

        prices = pd.DataFrame()

        for ticker in self.tickers:
            try:
                data = yf.download(
                    ticker,
                    start=start_date,
                    end=end_date,
                    progress=False
                )
                if len(data) > 0:
                    # yfinance가 MultiIndex 또는 단일 컬럼 반환 가능
                    if 'Adj Close' in data.columns:
                        prices[ticker] = data['Adj Close']
                    elif ('Adj Close', ticker) in data.columns:
                        prices[ticker] = data[('Adj Close', ticker)]
                    else:
                        # 단일 티커의 경우
                        prices[ticker] = data['Close']
            except Exception as e:
                logger.error(f"Error fetching {ticker}: {e}")
                raise ValueError(f"티커 '{ticker}' 데이터를 가져올 수 없습니다.")

        if prices.empty:
            raise ValueError("가격 데이터를 가져올 수 없습니다.")

        # 결측치 처리
        prices = prices.dropna()

        if len(prices) < 252:  # 최소 1년 데이터 필요
            raise ValueError("충분한 가격 데이터가 없습니다. (최소 1년 필요)")

        self._price_data = prices

        # 기대수익률과 공분산 행렬 계산
        self._mu = expected_returns.mean_historical_return(prices)
        self._S = risk_models.sample_cov(prices)

        logger.info(f"Loaded {len(prices)} days of price data")
        return prices

    def optimize_max_sharpe(self) -> Dict[str, float]:
        """
        Max Sharpe Ratio 최적화

        Returns:
            최적 비중 딕셔너리 {ticker: weight}
        """
        if self._mu is None or self._S is None:
            self.fetch_data()

        ef = EfficientFrontier(self._mu, self._S)
        ef.max_sharpe(risk_free_rate=self.risk_free_rate)
        weights = ef.clean_weights()

        return dict(weights)

    def optimize_min_volatility(self) -> Dict[str, float]:
        """
        Min Volatility 최적화

        Returns:
            최적 비중 딕셔너리 {ticker: weight}
        """
        if self._mu is None or self._S is None:
            self.fetch_data()

        ef = EfficientFrontier(self._mu, self._S)
        ef.min_volatility()
        weights = ef.clean_weights()

        return dict(weights)

    def get_performance_metrics(self, weights: Dict[str, float]) -> Dict[str, float]:
        """
        주어진 비중에 대한 예상 성과 지표 계산

        Args:
            weights: 포트폴리오 비중 딕셔너리

        Returns:
            성과 지표 딕셔너리 {
                'expected_return': 연간 기대수익률,
                'volatility': 연간 변동성,
                'sharpe_ratio': 샤프비율
            }
        """
        if self._mu is None or self._S is None:
            self.fetch_data()

        ef = EfficientFrontier(self._mu, self._S)

        # 비중 설정
        weight_array = np.array([weights.get(t, 0) for t in self.tickers])
        ef.set_weights({t: w for t, w in zip(self.tickers, weight_array)})

        expected_return, volatility, sharpe = ef.portfolio_performance(
            risk_free_rate=self.risk_free_rate
        )

        return {
            'expected_return': expected_return,
            'volatility': volatility,
            'sharpe_ratio': sharpe
        }

    def get_efficient_frontier(self, n_points: int = 100) -> Tuple[np.ndarray, np.ndarray, List[Dict]]:
        """
        Efficient Frontier 곡선 데이터 생성

        Args:
            n_points: 곡선 포인트 수

        Returns:
            (volatilities, returns, weights_list) 튜플
            - volatilities: 변동성 배열
            - returns: 수익률 배열
            - weights_list: 각 포인트의 비중 리스트
        """
        if self._mu is None or self._S is None:
            self.fetch_data()

        volatilities = []
        returns = []
        weights_list = []

        # 수익률 범위 결정 (min volatility ~ max return 사이)
        ef_min = EfficientFrontier(self._mu, self._S)
        ef_min.min_volatility()
        min_ret, _, _ = ef_min.portfolio_performance(risk_free_rate=self.risk_free_rate)

        ef_max = EfficientFrontier(self._mu, self._S)
        ef_max.max_sharpe(risk_free_rate=self.risk_free_rate)
        max_ret, _, _ = ef_max.portfolio_performance(risk_free_rate=self.risk_free_rate)

        # max return 포인트 추가
        max_single_ret = self._mu.max()

        target_returns = np.linspace(min_ret, max(max_ret, max_single_ret * 0.95), n_points)

        for target_ret in target_returns:
            try:
                ef = EfficientFrontier(self._mu, self._S)
                ef.efficient_return(target_ret)
                weights = ef.clean_weights()
                ret, vol, _ = ef.portfolio_performance(risk_free_rate=self.risk_free_rate)

                volatilities.append(vol)
                returns.append(ret)
                weights_list.append(dict(weights))
            except Exception:
                # 도달 불가능한 수익률은 스킵
                continue

        return np.array(volatilities), np.array(returns), weights_list

    def get_individual_assets(self) -> pd.DataFrame:
        """
        개별 자산의 수익률/변동성 정보

        Returns:
            DataFrame with columns: [ticker, expected_return, volatility]
        """
        if self._mu is None or self._S is None:
            self.fetch_data()

        data = []
        for ticker in self.tickers:
            vol = np.sqrt(self._S.loc[ticker, ticker])
            data.append({
                'ticker': ticker,
                'expected_return': self._mu[ticker],
                'volatility': vol
            })

        return pd.DataFrame(data)
