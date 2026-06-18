"""
환율 데이터 조회 및 통화 변환 모듈

yfinance를 통해 환율 데이터를 조회하고, 혼합 통화 자산의 가치를
base currency로 변환합니다.

USD↔KRW는 USDKRW=X 페어로 직접 변환하고, 그 외 통화는 USD를 피벗으로
(`{통화}USD=X`) 환산합니다.
"""
import pandas as pd
import numpy as np
import yfinance as yf
import logging
import time
from typing import Dict, Optional, Tuple

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

    혼합 통화 자산의 가치를 base currency로 변환합니다.
    USD↔KRW는 USDKRW=X로 직접, 그 외 통화는 USD 피벗(`{통화}USD=X`)으로 환산합니다.
    """

    FX_PAIR = "USDKRW=X"
    DEFAULT_USD_KRW = 1300.0

    # 소액 단위 표기(펜스/센트) → (정식 통화코드, 배율). 예: 런던 상장 ETF는 GBp(펜스).
    MINOR_UNITS: Dict[str, Tuple[str, float]] = {
        "GBp": ("GBP", 0.01),
        "GBX": ("GBP", 0.01),
        "ZAc": ("ZAR", 0.01),
        "ILA": ("ILS", 0.01),
    }

    def __init__(self, base_currency: str = "KRW"):
        """
        Args:
            base_currency: 기본 표시 통화 ("KRW" 또는 "USD")
        """
        self.base_currency = base_currency
        self._fx_data: Optional[pd.DataFrame] = None          # USDKRW=X (legacy)
        self._usd_per_unit: Dict[str, pd.DataFrame] = {}       # 통화 → USD per 1 단위 ('rate')
        self._date_range: Optional[Tuple[str, str]] = None

    def fetch_fx_data(self, start_date: str, end_date: str) -> None:
        """환율 데이터 조회 (USDKRW 사전 로드 + 일반 통화용 기간 저장)

        Args:
            start_date: 시작일
            end_date: 종료일
        """
        self._date_range = (start_date, end_date)
        self._fx_data = fetch_exchange_rate(self.FX_PAIR, start_date, end_date)

    @staticmethod
    def _lookup_rate(
        frame: Optional[pd.DataFrame],
        date: pd.Timestamp,
        fallback: float,
    ) -> float:
        """forward/backward 보간으로 특정일 환율 조회

        1. 해당일 또는 직후 거래일 우선
        2. 없으면 직전 거래일
        3. 둘 다 없으면 fallback
        """
        if frame is None or frame.empty:
            return fallback

        future_mask = frame.index >= date
        if future_mask.any():
            return frame.loc[future_mask, 'rate'].iloc[0]

        past_mask = frame.index <= date
        if past_mask.any():
            return frame.loc[past_mask, 'rate'].iloc[-1]

        return fallback

    def _get_fx_rate_on_date(self, date: pd.Timestamp) -> float:
        """특정 날짜의 USD/KRW 환율 (USDKRW=X)"""
        return self._lookup_rate(self._fx_data, date, self.DEFAULT_USD_KRW)

    def _usd_per_unit_on_date(self, currency: str, date: pd.Timestamp) -> float:
        """특정 날짜의 'USD per 1 단위 통화' 환율 (USD 피벗용)

        currency는 정식 통화코드(USD/KRW가 아닌 일반 통화)를 가정한다.
        """
        if currency not in self._usd_per_unit:
            if self._date_range is None:
                raise ValueError("fetch_fx_data()로 기간을 먼저 설정해야 합니다.")
            start, end = self._date_range
            # '{통화}USD=X' = USD per 1 단위 통화 (예: EURUSD=X ≈ 1.16)
            self._usd_per_unit[currency] = fetch_exchange_rate(
                f"{currency}USD=X", start, end
            )

        rate = self._lookup_rate(self._usd_per_unit[currency], date, fallback=0.0)
        if rate <= 0.0:
            raise ValueError(f"{currency} 환율 데이터를 사용할 수 없습니다.")
        return rate

    def get_fx_rate(self, from_currency: str, date: pd.Timestamp) -> float:
        """통화 변환 환율 조회

        Args:
            from_currency: 원본 통화 (USD/KRW 또는 임의 통화코드, GBp 등 소액단위 포함)
            date: 환율 기준일

        Returns:
            변환 배율 (from_currency → base_currency)
        """
        # 소액 단위(펜스/센트) → 정식 통화코드 + 배율 보정
        minor_factor = 1.0
        if from_currency in self.MINOR_UNITS:
            from_currency, minor_factor = self.MINOR_UNITS[from_currency]

        # 동일 통화면 변환 불필요
        if from_currency == self.base_currency:
            return minor_factor

        # USD↔KRW 직접 변환 (기존 로직 유지)
        if {from_currency, self.base_currency} <= {"USD", "KRW"}:
            usd_krw = self._get_fx_rate_on_date(date)
            direct = usd_krw if self.base_currency == "KRW" else 1.0 / usd_krw
            return direct * minor_factor

        # 그 외: USD 피벗 (USD/from ÷ USD/base)
        usd_per_from = (
            1.0 if from_currency == "USD"
            else self._usd_per_unit_on_date(from_currency, date)
        )
        usd_per_base = (
            1.0 if self.base_currency == "USD"
            else self._usd_per_unit_on_date(self.base_currency, date)
        )
        return (usd_per_from / usd_per_base) * minor_factor

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
