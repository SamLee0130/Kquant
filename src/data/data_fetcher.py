"""
yfinance 데이터 캐싱 레이어

Streamlit 세션 내 캐싱과 재시도 로직을 제공합니다.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import streamlit as st
import logging
import time
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 1.0  # seconds


def _normalize_timezone(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """타임존 제거 (tz-naive로 변환)"""
    if index.tz is not None:
        return index.tz_convert(None)
    return index


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_price_data(
    ticker: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """
    가격 데이터 조회 (캐싱)

    Args:
        ticker: ETF 심볼
        start_date: 시작일 (ISO format string for cache key)
        end_date: 종료일 (ISO format string for cache key)

    Returns:
        DataFrame with 'price' column, tz-naive DatetimeIndex

    Raises:
        ValueError: 데이터를 가져올 수 없는 경우
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            t = yf.Ticker(ticker)
            hist = t.history(start=start_date, end=end_date, auto_adjust=False)

            if hist.empty:
                raise ValueError(f"{ticker} 가격 데이터를 찾을 수 없습니다.")

            hist.index = pd.DatetimeIndex(hist.index)
            hist.index = _normalize_timezone(hist.index)

            result = hist[['Close']].copy()
            result.columns = ['price']

            # NaN 처리
            if result['price'].isna().all():
                raise ValueError(f"{ticker} 가격 데이터가 모두 NaN입니다.")
            result = result.dropna()

            logger.info(f"{ticker}: {len(result)} 거래일 로드됨")
            return result

        except ValueError:
            raise
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"{ticker} 데이터 조회 재시도 ({attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(delay)

    raise ValueError(f"{ticker} 데이터 조회 실패 (재시도 {MAX_RETRIES}회): {last_error}")


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_dividend_data(
    ticker: str,
    start_date: str,
    end_date: str
) -> pd.Series:
    """
    배당금 데이터 조회 (캐싱)

    Args:
        ticker: ETF 심볼
        start_date: 시작일 (ISO format string for cache key)
        end_date: 종료일 (ISO format string for cache key)

    Returns:
        Series of dividends, tz-naive DatetimeIndex
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            t = yf.Ticker(ticker)
            dividends = t.dividends

            if dividends.empty:
                return pd.Series(dtype=float)

            dividends.index = pd.DatetimeIndex(dividends.index)
            dividends.index = _normalize_timezone(dividends.index)

            start_ts = pd.Timestamp(start_date).tz_localize(None)
            end_ts = pd.Timestamp(end_date).tz_localize(None)
            mask = (dividends.index >= start_ts) & (dividends.index <= end_ts)

            result = dividends[mask]
            logger.info(f"{ticker}: {len(result)} 배당 이벤트 로드됨")
            return result

        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"{ticker} 배당 데이터 조회 재시도 ({attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(delay)

    logger.error(f"{ticker} 배당 데이터 조회 실패: {last_error}")
    return pd.Series(dtype=float)


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_adjusted_prices(
    tickers: tuple,
    start_date: str,
    end_date: str,
    min_days: int = 252
) -> pd.DataFrame:
    """
    복수 티커의 조정 종가 조회 (최적화용, 캐싱)

    Args:
        tickers: ETF 심볼 튜플 (cache key용 immutable)
        start_date: 시작일
        end_date: 종료일
        min_days: 최소 데이터 일수

    Returns:
        DataFrame with ticker columns, tz-naive DatetimeIndex
    """
    prices = pd.DataFrame()

    for ticker in tickers:
        try:
            data = yf.download(ticker, start=start_date, end=end_date, progress=False)
            if len(data) > 0:
                if 'Adj Close' in data.columns:
                    prices[ticker] = data['Adj Close']
                elif ('Adj Close', ticker) in data.columns:
                    prices[ticker] = data[('Adj Close', ticker)]
                else:
                    prices[ticker] = data['Close']
        except Exception as e:
            logger.error(f"Error fetching {ticker}: {e}")
            raise ValueError(f"티커 '{ticker}' 데이터를 가져올 수 없습니다.")

    if prices.empty:
        raise ValueError("가격 데이터를 가져올 수 없습니다.")

    prices = prices.dropna()

    if len(prices) < min_days:
        raise ValueError(f"충분한 가격 데이터가 없습니다. (최소 {min_days}일 필요, 현재 {len(prices)}일)")

    return prices
