"""
ETF 분류 모듈 테스트
"""
import pytest
from src.data.etf_classifier import (
    Market, ETFInfo, classify_etf, normalize_ticker,
    is_korean_ticker, classify_portfolio, has_mixed_currencies,
    needs_currency_conversion, get_tax_label, KOREAN_ETF_REGISTRY,
)


class TestNormalizeTicker:
    """normalize_ticker 함수 테스트"""

    def test_six_digit_number_adds_ks_suffix(self):
        assert normalize_ticker("069500") == "069500.KS"

    def test_six_digit_number_with_spaces(self):
        assert normalize_ticker("  069500  ") == "069500.KS"

    def test_already_has_ks_suffix(self):
        assert normalize_ticker("069500.KS") == "069500.KS"

    def test_lowercase_ks_suffix(self):
        assert normalize_ticker("069500.ks") == "069500.KS"

    def test_kq_suffix(self):
        assert normalize_ticker("035720.KQ") == "035720.KQ"

    def test_lowercase_kq_suffix(self):
        assert normalize_ticker("035720.kq") == "035720.KQ"

    def test_us_ticker_uppercase(self):
        assert normalize_ticker("spy") == "SPY"

    def test_us_ticker_already_uppercase(self):
        assert normalize_ticker("SPY") == "SPY"

    def test_us_ticker_with_spaces(self):
        assert normalize_ticker("  qqq  ") == "QQQ"

    def test_five_digit_number_not_auto_suffix(self):
        """5자리 숫자는 .KS 자동 추가 안 함"""
        result = normalize_ticker("12345")
        assert not result.endswith(".KS")

    def test_seven_digit_number_not_auto_suffix(self):
        """7자리 숫자는 .KS 자동 추가 안 함"""
        result = normalize_ticker("1234567")
        assert not result.endswith(".KS")


class TestIsKoreanTicker:
    """is_korean_ticker 함수 테스트"""

    def test_ks_suffix(self):
        assert is_korean_ticker("069500.KS") is True

    def test_kq_suffix(self):
        assert is_korean_ticker("035720.KQ") is True

    def test_us_ticker(self):
        assert is_korean_ticker("SPY") is False

    def test_case_insensitive(self):
        assert is_korean_ticker("069500.ks") is True

    def test_empty_string(self):
        assert is_korean_ticker("") is False


class TestClassifyETF:
    """classify_etf 함수 테스트"""

    def test_us_ticker(self):
        info = classify_etf("SPY")
        assert info.market == Market.US
        assert info.currency == "USD"
        assert info.ticker == "SPY"
        assert info.display_name == "SPY"

    def test_us_ticker_lowercase(self):
        info = classify_etf("spy")
        assert info.market == Market.US
        assert info.ticker == "SPY"

    def test_kr_stock_etf_from_registry(self):
        info = classify_etf("069500.KS")
        assert info.market == Market.KR_STOCK
        assert info.currency == "KRW"
        assert info.display_name == "KODEX 200"

    def test_kr_other_etf_from_registry(self):
        info = classify_etf("360750.KS")
        assert info.market == Market.KR_OTHER
        assert info.currency == "KRW"
        assert info.display_name == "TIGER S&P500"

    def test_kr_bond_etf(self):
        info = classify_etf("148070.KS")
        assert info.market == Market.KR_OTHER
        assert info.display_name == "KOSEF 국고채10년"

    def test_kr_commodity_etf(self):
        info = classify_etf("132030.KS")
        assert info.market == Market.KR_OTHER
        assert info.display_name == "KODEX 골드선물(H)"

    def test_six_digit_input_auto_classified(self):
        """6자리 숫자 입력 시 .KS 접미사 자동 추가 후 분류"""
        info = classify_etf("069500")
        assert info.market == Market.KR_STOCK
        assert info.ticker == "069500.KS"

    def test_unregistered_korean_ticker_defaults_to_kr_other(self):
        """미등록 한국 티커는 KR_OTHER (보수적 과세)"""
        info = classify_etf("999999.KS")
        assert info.market == Market.KR_OTHER
        assert info.currency == "KRW"
        assert info.display_name == "999999"

    def test_unregistered_kosdaq_ticker(self):
        info = classify_etf("035720.KQ")
        assert info.market == Market.KR_OTHER
        assert info.currency == "KRW"

    def test_all_registry_entries_are_valid(self):
        """레지스트리의 모든 항목이 올바른 형식"""
        for ticker, (name, market) in KOREAN_ETF_REGISTRY.items():
            assert ticker.endswith(".KS") or ticker.endswith(".KQ")
            assert isinstance(name, str) and len(name) > 0
            assert isinstance(market, Market)
            assert market in (Market.KR_STOCK, Market.KR_OTHER)


class TestClassifyPortfolio:
    """classify_portfolio 함수 테스트"""

    def test_us_only_portfolio(self):
        allocation = {"SPY": 0.6, "QQQ": 0.3, "BIL": 0.1}
        result = classify_portfolio(allocation)
        assert all(info.market == Market.US for info in result.values())
        assert all(info.currency == "USD" for info in result.values())

    def test_kr_only_portfolio(self):
        allocation = {"069500.KS": 0.5, "360750.KS": 0.5}
        result = classify_portfolio(allocation)
        assert all(info.currency == "KRW" for info in result.values())

    def test_mixed_portfolio(self):
        allocation = {"SPY": 0.5, "069500.KS": 0.5}
        result = classify_portfolio(allocation)
        currencies = {info.currency for info in result.values()}
        assert currencies == {"USD", "KRW"}

    def test_normalizes_tickers(self):
        allocation = {"spy": 0.5, "069500": 0.5}
        result = classify_portfolio(allocation)
        assert "SPY" in result
        assert "069500.KS" in result


class TestHasMixedCurrencies:
    """has_mixed_currencies 함수 테스트"""

    def test_single_currency(self):
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "QQQ": ETFInfo("QQQ", "QQQ", Market.US, "USD"),
        }
        assert has_mixed_currencies(etf_info) is False

    def test_mixed_currencies(self):
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        assert has_mixed_currencies(etf_info) is True

    def test_kr_only(self):
        etf_info = {
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
            "360750.KS": ETFInfo("360750.KS", "TIGER S&P500", Market.KR_OTHER, "KRW"),
        }
        assert has_mixed_currencies(etf_info) is False


class TestNeedsCurrencyConversion:
    """needs_currency_conversion 함수 테스트"""

    def test_usd_base_with_usd_etfs(self):
        """USD 기준 + USD ETF만 → 변환 불필요"""
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "QQQ": ETFInfo("QQQ", "QQQ", Market.US, "USD"),
        }
        assert needs_currency_conversion(etf_info, "USD") is False

    def test_krw_base_with_krw_etfs(self):
        """KRW 기준 + KRW ETF만 → 변환 불필요"""
        etf_info = {
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
            "360750.KS": ETFInfo("360750.KS", "TIGER S&P500", Market.KR_OTHER, "KRW"),
        }
        assert needs_currency_conversion(etf_info, "KRW") is False

    def test_krw_base_with_usd_etfs(self):
        """KRW 기준 + USD ETF → 변환 필요"""
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
        }
        assert needs_currency_conversion(etf_info, "KRW") is True

    def test_usd_base_with_krw_etfs(self):
        """USD 기준 + KRW ETF → 변환 필요"""
        etf_info = {
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        assert needs_currency_conversion(etf_info, "USD") is True

    def test_mixed_portfolio_any_base(self):
        """혼합 포트폴리오 → 어떤 기준 통화든 변환 필요"""
        etf_info = {
            "SPY": ETFInfo("SPY", "SPY", Market.US, "USD"),
            "069500.KS": ETFInfo("069500.KS", "KODEX 200", Market.KR_STOCK, "KRW"),
        }
        assert needs_currency_conversion(etf_info, "KRW") is True
        assert needs_currency_conversion(etf_info, "USD") is True


class TestGetTaxLabel:
    """get_tax_label 함수 테스트"""

    def test_us_label(self):
        assert get_tax_label(Market.US) == "양도소득세 22%"

    def test_kr_stock_label(self):
        assert get_tax_label(Market.KR_STOCK) == "비과세"

    def test_kr_other_label(self):
        assert get_tax_label(Market.KR_OTHER) == "배당소득세 15.4%"
