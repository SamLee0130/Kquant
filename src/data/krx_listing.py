"""
KRX 상장목록(이름↔코드) 수집 및 검색

FinanceDataReader로 KRX 주식 + 국내 ETF 상장목록을 가져와 한국어 종목명/코드로
검색할 수 있게 한다. 가격/수익률은 yfinance(fetch_total_return_prices)가 담당하고,
이 모듈은 이름↔코드↔yfinance 티커 매핑(메타데이터)만 제공한다.
"""
import logging
from dataclasses import dataclass
from enum import Enum
from typing import List, Optional

import pandas as pd
import streamlit as st

from src.data.etf_classifier import KOREAN_ETF_REGISTRY

logger = logging.getLogger(__name__)

try:
    import FinanceDataReader as fdr
except ImportError:
    fdr = None

# 오프라인/FDR 실패 시 최소 검색을 보장할 대표 종목 (모두 KOSPI → .KS)
_FALLBACK_STOCKS = {
    "005930": "삼성전자",
    "000660": "SK하이닉스",
    "035420": "NAVER",
    "035720": "카카오",
    "005380": "현대차",
    "051910": "LG화학",
    "006400": "삼성SDI",
    "207940": "삼성바이오로직스",
    "005490": "POSCO홀딩스",
    "105560": "KB금융",
}

_LISTING_COLUMNS = ["code", "name", "yf_ticker", "security_type", "market"]


class SecurityType(Enum):
    STOCK = "STOCK"
    ETF = "ETF"


@dataclass(frozen=True)
class KrxSecurity:
    """KRX 상장 종목 (검색·선택 단위)"""
    code: str               # 6자리 종목코드 ("005930")
    name: str               # 한국어 종목명 ("삼성전자")
    yf_ticker: str          # yfinance 티커 ("005930.KS" / "035720.KQ")
    security_type: SecurityType
    market: str             # "KOSPI" | "KOSDAQ" | "KONEX" | "ETF"


def _suffix_for_market(market: str) -> str:
    """KRX 시장명 → yfinance 접미사. KOSDAQ 계열은 .KQ, 그 외(KOSPI/KONEX)는 .KS"""
    if market and market.upper().startswith("KOSDAQ"):
        return "KQ"
    return "KS"


def _pick_column(frame: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    """후보 컬럼명 중 frame에 존재하는 첫 번째를 반환 (FDR 버전별 스키마 차이 흡수)"""
    for name in candidates:
        if name in frame.columns:
            return name
    return None


def _build_listing(stocks: pd.DataFrame, etfs: pd.DataFrame) -> pd.DataFrame:
    """FDR 원본 프레임을 정규화된 상장목록으로 변환"""
    rows = []

    stock_code_col = _pick_column(stocks, ["Code", "Symbol"])
    stock_name_col = _pick_column(stocks, ["Name"])
    stock_market_col = _pick_column(stocks, ["Market"])
    if stock_code_col and stock_name_col:
        for row in stocks.itertuples(index=False):
            code = str(getattr(row, stock_code_col)).zfill(6)
            name = getattr(row, stock_name_col)
            market = getattr(row, stock_market_col) if stock_market_col else "KOSPI"
            if not name or pd.isna(name):
                continue
            rows.append({
                "code": code,
                "name": str(name),
                "yf_ticker": f"{code}.{_suffix_for_market(str(market))}",
                "security_type": SecurityType.STOCK.value,
                "market": str(market),
            })

    etf_code_col = _pick_column(etfs, ["Symbol", "Code"])
    etf_name_col = _pick_column(etfs, ["Name"])
    if etf_code_col and etf_name_col:
        for row in etfs.itertuples(index=False):
            code = str(getattr(row, etf_code_col)).zfill(6)
            name = getattr(row, etf_name_col)
            if not name or pd.isna(name):
                continue
            rows.append({
                "code": code,
                "name": str(name),
                "yf_ticker": f"{code}.KS",  # 국내 ETF는 모두 유가증권시장
                "security_type": SecurityType.ETF.value,
                "market": "ETF",
            })

    frame = pd.DataFrame(rows, columns=_LISTING_COLUMNS)
    # 코드 중복 시 먼저 등장한 행(주식) 유지
    frame = frame.drop_duplicates(subset="code", keep="first").reset_index(drop=True)
    return frame


def _fallback_listing() -> pd.DataFrame:
    """FDR 실패 시 KOREAN_ETF_REGISTRY + 대표주로 최소 검색 보장"""
    rows = []
    for yf_ticker, (name, _market) in KOREAN_ETF_REGISTRY.items():
        code = yf_ticker.split(".")[0]
        rows.append({
            "code": code,
            "name": name,
            "yf_ticker": yf_ticker,
            "security_type": SecurityType.ETF.value,
            "market": "ETF",
        })
    for code, name in _FALLBACK_STOCKS.items():
        rows.append({
            "code": code,
            "name": name,
            "yf_ticker": f"{code}.KS",
            "security_type": SecurityType.STOCK.value,
            "market": "KOSPI",
        })
    frame = pd.DataFrame(rows, columns=_LISTING_COLUMNS)
    return frame.drop_duplicates(subset="code", keep="first").reset_index(drop=True)


@st.cache_data(ttl=86400, show_spinner=False)
def load_krx_listing() -> pd.DataFrame:
    """KRX 주식 + 국내 ETF 상장목록 (컬럼: code, name, yf_ticker, security_type, market)

    네트워크/스키마 실패 시 fallback 목록을 반환하며 예외를 던지지 않는다.
    """
    if fdr is None:
        logger.warning("FinanceDataReader 미설치 — fallback 상장목록 사용")
        return _fallback_listing()

    try:
        stocks = fdr.StockListing("KRX")
        etfs = fdr.StockListing("ETF/KR")
        listing = _build_listing(stocks, etfs)
        if listing.empty:
            logger.warning("KRX 상장목록이 비어 fallback 사용")
            return _fallback_listing()
        logger.info(f"KRX 상장목록 {len(listing)}종목 로드됨")
        return listing
    except Exception as e:
        logger.warning(f"KRX 상장목록 조회 실패 ({e}) — fallback 사용")
        return _fallback_listing()


def _row_to_security(row) -> KrxSecurity:
    return KrxSecurity(
        code=row.code,
        name=row.name,
        yf_ticker=row.yf_ticker,
        security_type=SecurityType(row.security_type),
        market=row.market,
    )


def search_korean_securities(
    query: str,
    limit: int = 30,
    types: Optional[List[SecurityType]] = None,
) -> List[KrxSecurity]:
    """한국어 종목명(부분일치) 또는 6자리 코드(접두일치)로 검색

    정렬: 정확일치 > 접두일치 > 부분일치, 동순위는 이름 길이 오름차순. 빈 query → [].
    """
    query = (query or "").strip()
    if not query:
        return []

    listing = load_krx_listing()
    if types:
        type_values = {t.value for t in types}
        listing = listing[listing["security_type"].isin(type_values)]
    if listing.empty:
        return []

    if query.isdigit():
        matched = listing[listing["code"].str.startswith(query)].copy()
        matched["_rank"] = (matched["code"] != query).astype(int)
        matched = matched.sort_values(["_rank", "code"])
    else:
        needle = query.replace(" ", "").lower()
        normalized_name = (
            listing["name"].str.replace(" ", "", regex=False).str.lower()
        )
        mask = normalized_name.str.contains(needle, regex=False, na=False)
        matched = listing[mask].copy()
        names = normalized_name[mask]
        rank = pd.Series(2, index=matched.index)
        rank[names.str.startswith(needle)] = 1
        rank[names == needle] = 0
        matched["_rank"] = rank
        matched["_name_len"] = matched["name"].str.len()
        matched = matched.sort_values(["_rank", "_name_len", "name"])

    matched = matched.head(limit)
    return [_row_to_security(row) for row in matched.itertuples(index=False)]


@st.cache_data(ttl=86400, show_spinner=False)
def all_securities() -> List[KrxSecurity]:
    """전체 상장목록을 KrxSecurity 리스트로 반환 (검색형 multiselect 옵션용).

    주식(시가총액 순) → ETF 순서를 유지한다.
    """
    listing = load_krx_listing()
    return [_row_to_security(row) for row in listing.itertuples(index=False)]


def resolve_security(yf_ticker: str) -> Optional[KrxSecurity]:
    """yfinance 티커로 KrxSecurity 역조회 (없으면 None)"""
    listing = load_krx_listing()
    matched = listing[listing["yf_ticker"] == yf_ticker]
    if matched.empty:
        return None
    return _row_to_security(next(matched.itertuples(index=False)))


def format_option_label(security: KrxSecurity) -> str:
    """multiselect 라벨: '삼성전자 (005930)'"""
    return f"{security.name} ({security.code})"
