"""
환율 데이터 조회 및 통화 변환 모듈

yfinance를 통해 USD/KRW 환율 데이터를 조회하고,
혼합 통화 포트폴리오의 가치를 base currency로 변환합니다.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import logging
import time
from typing import Optional

logger = logging.getLogger(__name__)

MAX_RETRIES = 5
RETRY_BASE_DELAY = 1.0


def _normalize_timezone(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    """타임존 제거 (tz-naive로 변환)"""
    if index.tz is not None:
        return index.tz_convert(None)
    return index


def fetch_exchange_rate(
    pair: str,
    start_date: str,
    end_date: str
) -> pd.DataFrame:
    """환율 데이터 조회

    Args:
        pair: 환율 페어 (예: "USDKRW=X")
        start_date: 시작일 (ISO format string)
        end_date: 종료일 (ISO format string)

    Returns:
        DataFrame with 'rate' column, tz-naive DatetimeIndex

    Raises:
        ValueError: 데이터를 가져올 수 없는 경우
    """
    last_error = None

    for attempt in range(MAX_RETRIES):
        try:
            t = yf.Ticker(pair)
            hist = t.history(start=start_date, end=end_date, auto_adjust=False)

            if hist.empty:
                raise ValueError(f"{pair} 환율 데이터를 찾을 수 없습니다.")

            hist.index = pd.DatetimeIndex(hist.index)
            hist.index = _normalize_timezone(hist.index)

            result = hist[['Close']].copy()
            result.columns = ['rate']

            if result['rate'].isna().all():
                raise ValueError(f"{pair} 환율 데이터가 모두 NaN입니다.")
            result = result.dropna()

            logger.info(f"{pair}: {len(result)} 거래일 환율 로드됨")
            return result

        except ValueError:
            raise
        except Exception as e:
            last_error = e
            if attempt < MAX_RETRIES - 1:
                delay = RETRY_BASE_DELAY * (2 ** attempt)
                logger.warning(f"{pair} 환율 조회 재시도 ({attempt + 1}/{MAX_RETRIES}): {e}")
                time.sleep(delay)

    raise ValueError(f"{pair} 환율 조회 실패 (재시도 {MAX_RETRIES}회): {last_error}")


class CurrencyConverter:
    """통화 변환기

    혼합 통화 포트폴리오의 가치를 base currency로 변환합니다.
    """

    FX_PAIR = "USDKRW=X"

    def __init__(self, base_currency: str = "KRW"):
        """
        Args:
            base_currency: 기본 표시 통화 ("KRW" 또는 "USD")
        """
        self.base_currency = base_currency
        self._fx_data: Optional[pd.DataFrame] = None

    def fetch_fx_data(self, start_date: str, end_date: str) -> None:
        """환율 데이터 조회

        Args:
            start_date: 시작일
            end_date: 종료일
        """
        self._fx_data = fetch_exchange_rate(self.FX_PAIR, start_date, end_date)

    def _get_fx_rate_on_date(self, date: pd.Timestamp) -> float:
        """특정 날짜의 USD/KRW 환율 조회 (forward/backward lookup)

        _get_price()와 동일한 보간 로직:
        1. 해당일 또는 직후 거래일 우선
        2. 없으면 직전 거래일

        Returns:
            USD/KRW 환율 (예: 1350.0)
        """
        if self._fx_data is None or self._fx_data.empty:
            return 1300.0  # fallback 기본값

        df = self._fx_data

        # 직후(해당일 포함) 첫 거래일 우선
        future_mask = df.index >= date
        if future_mask.any():
            return df.loc[future_mask, 'rate'].iloc[0]

        # 미래에 없으면 직전 거래일
        past_mask = df.index <= date
        if past_mask.any():
            return df.loc[past_mask, 'rate'].iloc[-1]

        return 1300.0  # fallback

    def get_fx_rate(self, from_currency: str, date: pd.Timestamp) -> float:
        """통화 변환 환율 조회

        Args:
            from_currency: 원본 통화 ("USD" 또는 "KRW")
            date: 환율 기준일

        Returns:
            변환 배율 (from_currency → base_currency)
        """
        # 동일 통화면 변환 불필요
        if from_currency == self.base_currency:
            return 1.0

        usd_krw = self._get_fx_rate_on_date(date)

        if self.base_currency == "KRW" and from_currency == "USD":
            return usd_krw  # USD → KRW
        elif self.base_currency == "USD" and from_currency == "KRW":
            return 1.0 / usd_krw  # KRW → USD

        return 1.0  # 알 수 없는 통화 조합

    def convert(self, amount: float, from_currency: str, date: pd.Timestamp) -> float:
        """금액을 base currency로 변환

        Args:
            amount: 변환할 금액
            from_currency: 원본 통화
            date: 환율 기준일

        Returns:
            base currency로 변환된 금액
        """
        rate = self.get_fx_rate(from_currency, date)
        return amount * rate
