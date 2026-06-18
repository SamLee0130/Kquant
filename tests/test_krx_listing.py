"""
KRX 상장목록 로드·검색 테스트 (FinanceDataReader mock)
"""
import pandas as pd
import pytest
from unittest.mock import patch

from src.data.krx_listing import (
    SecurityType,
    load_krx_listing,
    search_korean_securities,
    resolve_security,
    format_option_label,
)


def _mock_stocks():
    """KRX StockListing('KRX') 형태 (Code/Name/Market)"""
    return pd.DataFrame({
        "Code": ["005930", "000660", "035720", "950130"],
        "Name": ["삼성전자", "SK하이닉스", "카카오게임즈", "엑세스바이오"],
        "Market": ["KOSPI", "KOSPI", "KOSDAQ", "KOSDAQ GLOBAL"],
    })


def _mock_etfs():
    """KRX StockListing('ETF/KR') 형태 (Symbol/Name)"""
    return pd.DataFrame({
        "Symbol": ["069500", "360750"],
        "Name": ["KODEX 200", "TIGER 미국S&P500"],
    })


def _stocklisting_side_effect(market):
    if market == "KRX":
        return _mock_stocks()
    if market == "ETF/KR":
        return _mock_etfs()
    raise ValueError(f"unexpected market {market}")


@pytest.fixture(autouse=True)
def _clear_cache():
    load_krx_listing.clear()
    yield
    load_krx_listing.clear()


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_market_suffix_mapping(_mock):
    listing = load_krx_listing()
    by_code = dict(zip(listing["code"], listing["yf_ticker"]))
    assert by_code["005930"] == "005930.KS"        # KOSPI → .KS
    assert by_code["035720"] == "035720.KQ"        # KOSDAQ → .KQ
    assert by_code["950130"] == "950130.KQ"        # KOSDAQ GLOBAL → .KQ
    assert by_code["069500"] == "069500.KS"        # ETF → .KS


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_search_by_korean_name(_mock):
    results = search_korean_securities("삼성")
    names = [s.name for s in results]
    assert "삼성전자" in names
    assert all(isinstance(s, SecurityType) is False for s in results)  # KrxSecurity 반환


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_search_exact_name_ranks_first(_mock):
    results = search_korean_securities("KODEX 200")
    assert results[0].name == "KODEX 200"


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_search_by_code_prefix(_mock):
    results = search_korean_securities("0059")
    assert results[0].code == "005930"
    assert results[0].security_type == SecurityType.STOCK


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_search_filter_by_type(_mock):
    etf_only = search_korean_securities("KODEX", types=[SecurityType.ETF], limit=50)
    assert etf_only
    assert all(s.security_type == SecurityType.ETF for s in etf_only)
    # 주식(삼성전자)은 ETF 필터에서 제외
    assert search_korean_securities("삼성전자", types=[SecurityType.ETF]) == []


def test_empty_query_returns_empty():
    assert search_korean_securities("") == []
    assert search_korean_securities("   ") == []


@patch("src.data.krx_listing.fdr.StockListing", side_effect=_stocklisting_side_effect)
def test_resolve_and_label(_mock):
    security = resolve_security("005930.KS")
    assert security is not None
    assert security.name == "삼성전자"
    assert format_option_label(security) == "삼성전자 (005930)"
    assert resolve_security("999999.KS") is None


@patch("src.data.krx_listing.fdr.StockListing", side_effect=RuntimeError("network down"))
def test_fallback_on_fdr_failure(_mock):
    """FDR 실패 시 fallback 목록으로 검색 가능 (예외 전파 안 함)"""
    listing = load_krx_listing()
    assert not listing.empty
    results = search_korean_securities("삼성전자")
    assert any(s.code == "005930" for s in results)
