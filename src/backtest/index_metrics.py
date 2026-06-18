"""
Buy-and-hold 성과 지표 계산

리밸런싱 없이 매수 후 보유한 단일 가격 시계열의 성과 지표를 계산한다.
PortfolioBacktester._calculate_metrics()와 동일한 정의(CAGR 기반 샤프비율)를
따르되, 일별 가격 데이터를 입력받으므로 연율화 팩터는 √252(거래일 기준)를 사용한다.

입력 가격은 이미 기준 통화로 환산되고 배당이 반영된 total return 시계열을 가정한다.
지표는 모두 비율(수익률/낙폭)이라 통화 단위와 무관하다.
"""
import numpy as np
import pandas as pd
from typing import Dict

from config.settings import BACKTEST_CONSTANTS

RISK_FREE_RATE = BACKTEST_CONSTANTS["risk_free_rate"]
TRADING_DAYS_PER_YEAR = 252
DAILY_VOLATILITY_ANNUALIZATION = np.sqrt(TRADING_DAYS_PER_YEAR)


def compute_buy_hold_metrics(
    prices: pd.Series,
    risk_free_rate: float = RISK_FREE_RATE,
) -> Dict[str, float]:
    """일별 가격 시계열의 buy-and-hold 성과 지표 계산

    Args:
        prices: 날짜 인덱스를 가진 일별 가격 Series (기준 통화, total return).
            오름차순 정렬을 가정한다.
        risk_free_rate: 무위험수익률 (샤프비율 계산용)

    Returns:
        total_return, cagr, volatility, sharpe_ratio, max_drawdown (모두 %)를 담은 dict.
        sharpe_ratio는 배율(unitless).

    Raises:
        ValueError: 데이터 포인트가 2개 미만인 경우
    """
    if len(prices) < 2:
        raise ValueError("성과 지표 계산에는 최소 2개의 가격 데이터가 필요합니다.")

    start_value = prices.iloc[0]
    end_value = prices.iloc[-1]

    total_return = (end_value / start_value - 1) * 100

    years_elapsed = (prices.index[-1] - prices.index[0]).days / 365.25
    cagr = (
        ((end_value / start_value) ** (1 / years_elapsed) - 1) * 100
        if years_elapsed > 0
        else 0.0
    )

    daily_returns = prices.pct_change().dropna()
    volatility = daily_returns.std() * DAILY_VOLATILITY_ANNUALIZATION * 100

    excess_return = (cagr / 100) - risk_free_rate
    sharpe_ratio = excess_return / (volatility / 100) if volatility > 0 else 0.0

    cummax = prices.cummax()
    drawdown = (prices - cummax) / cummax
    max_drawdown = drawdown.min() * 100

    return {
        "total_return": total_return,
        "cagr": cagr,
        "volatility": volatility,
        "sharpe_ratio": sharpe_ratio,
        "max_drawdown": max_drawdown,
    }
