"""
환율 변환 모듈 테스트
"""
import pytest
import pandas as pd
import numpy as np
from unittest.mock import patch, MagicMock
from src.data.fx_fetcher import CurrencyConverter, fetch_exchange_rate


def make_fx_df(dates, rates):
    """테스트용 환율 DataFrame 생성"""
    index = pd.DatetimeIndex(dates)
    return pd.DataFrame({'rate': rates}, index=index)


class TestCurrencyConverterBasic:
    """CurrencyConverter 기본 동작 테스트"""

    def test_same_currency_returns_one(self):
        """동일 통화 변환 시 1.0 반환"""
        converter = CurrencyConverter(base_currency="KRW")
        date = pd.Timestamp("2024-01-15")
        assert converter.get_fx_rate("KRW", date) == 1.0

    def test_same_currency_usd(self):
        converter = CurrencyConverter(base_currency="USD")
        date = pd.Timestamp("2024-01-15")
        assert converter.get_fx_rate("USD", date) == 1.0

    def test_convert_same_currency(self):
        converter = CurrencyConverter(base_currency="KRW")
        date = pd.Timestamp("2024-01-15")
        assert converter.convert(1000.0, "KRW", date) == 1000.0


class TestCurrencyConverterWithData:
    """환율 데이터가 있을 때 변환 테스트"""

    @pytest.fixture
    def converter_krw(self):
        """KRW 기준 컨버터 (환율 데이터 주입)"""
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = make_fx_df(
            ["2024-01-15", "2024-01-16", "2024-01-17", "2024-01-18", "2024-01-19"],
            [1300.0, 1310.0, 1320.0, 1315.0, 1305.0]
        )
        return converter

    @pytest.fixture
    def converter_usd(self):
        """USD 기준 컨버터 (환율 데이터 주입)"""
        converter = CurrencyConverter(base_currency="USD")
        converter._fx_data = make_fx_df(
            ["2024-01-15", "2024-01-16", "2024-01-17"],
            [1300.0, 1310.0, 1320.0]
        )
        return converter

    def test_usd_to_krw_conversion(self, converter_krw):
        date = pd.Timestamp("2024-01-15")
        result = converter_krw.convert(100.0, "USD", date)
        assert result == 100.0 * 1300.0

    def test_usd_to_krw_different_date(self, converter_krw):
        date = pd.Timestamp("2024-01-17")
        result = converter_krw.convert(100.0, "USD", date)
        assert result == 100.0 * 1320.0

    def test_krw_to_usd_conversion(self, converter_usd):
        date = pd.Timestamp("2024-01-15")
        result = converter_usd.convert(1_300_000.0, "KRW", date)
        expected = 1_300_000.0 / 1300.0
        assert abs(result - expected) < 0.01

    def test_forward_lookup_on_non_trading_day(self, converter_krw):
        """거래일이 아닌 날짜 → 직후 거래일 환율 사용"""
        date = pd.Timestamp("2024-01-14")  # 데이터 시작 전
        rate = converter_krw.get_fx_rate("USD", date)
        assert rate == 1300.0  # 첫 거래일 환율

    def test_backward_lookup_after_last_date(self, converter_krw):
        """마지막 거래일 이후 → 직전 거래일 환율 사용"""
        date = pd.Timestamp("2024-01-25")  # 데이터 끝 이후
        rate = converter_krw.get_fx_rate("USD", date)
        assert rate == 1305.0  # 마지막 거래일 환율

    def test_exact_date_match(self, converter_krw):
        date = pd.Timestamp("2024-01-16")
        rate = converter_krw.get_fx_rate("USD", date)
        assert rate == 1310.0


class TestCurrencyConverterFallback:
    """환율 데이터 없을 때 fallback 테스트"""

    def test_no_fx_data_uses_default(self):
        converter = CurrencyConverter(base_currency="KRW")
        # _fx_data가 None인 상태
        date = pd.Timestamp("2024-01-15")
        rate = converter.get_fx_rate("USD", date)
        assert rate == 1300.0  # 기본 fallback

    def test_empty_fx_data_uses_default(self):
        converter = CurrencyConverter(base_currency="KRW")
        converter._fx_data = pd.DataFrame(columns=['rate'])
        date = pd.Timestamp("2024-01-15")
        rate = converter.get_fx_rate("USD", date)
        assert rate == 1300.0


class TestFetchExchangeRate:
    """fetch_exchange_rate 함수 테스트 (mocked)"""

    @patch('src.data.fx_fetcher.yf.Ticker')
    def test_successful_fetch(self, mock_ticker_class):
        """정상 환율 조회"""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker

        dates = pd.DatetimeIndex(["2024-01-15", "2024-01-16"])
        mock_ticker.history.return_value = pd.DataFrame(
            {'Close': [1300.0, 1310.0], 'Open': [1295.0, 1305.0]},
            index=dates
        )

        result = fetch_exchange_rate("USDKRW=X", "2024-01-15", "2024-01-16")
        assert 'rate' in result.columns
        assert len(result) == 2
        assert result['rate'].iloc[0] == 1300.0

    @patch('src.data.fx_fetcher.yf.Ticker')
    def test_empty_data_raises_error(self, mock_ticker_class):
        """빈 데이터 → ValueError"""
        mock_ticker = MagicMock()
        mock_ticker_class.return_value = mock_ticker
        mock_ticker.history.return_value = pd.DataFrame()

        with pytest.raises(ValueError, match="환율 데이터를 찾을 수 없습니다"):
            fetch_exchange_rate("USDKRW=X", "2024-01-15", "2024-01-16")
