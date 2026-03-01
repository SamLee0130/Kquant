"""
ETF 분류 모듈

ETF를 시장/유형별로 분류하여 세금 규칙과 통화를 결정합니다.
- US: 해외 상장 ETF (SPY, QQQ 등)
- KR_STOCK: 국내 주식형 ETF (KODEX 200 등) - 양도차익 비과세
- KR_OTHER: 국내 기타 ETF (해외/채권/원자재) - 매매차익 배당소득세 15.4%
"""
import re
from enum import Enum
from dataclasses import dataclass
from typing import Dict, Optional


class Market(Enum):
    """ETF 상장 시장 및 유형"""
    US = "US"
    KR_STOCK = "KR_STOCK"
    KR_OTHER = "KR_OTHER"


@dataclass
class ETFInfo:
    """ETF 분류 정보"""
    ticker: str           # yfinance 형식 (예: "069500.KS")
    display_name: str     # 표시명 (예: "KODEX 200")
    market: Market
    currency: str         # "USD" 또는 "KRW"


# 대표 한국 ETF 레지스트리
# ticker -> (display_name, market)
KOREAN_ETF_REGISTRY: Dict[str, tuple] = {
    # 국내 주식형 ETF (양도차익 비과세)
    "069500.KS": ("KODEX 200", Market.KR_STOCK),
    "102110.KS": ("TIGER 200", Market.KR_STOCK),
    "226490.KS": ("KODEX KOSPI", Market.KR_STOCK),
    "252710.KS": ("TIGER 200 IT", Market.KR_STOCK),
    "091160.KS": ("KODEX 반도체", Market.KR_STOCK),
    "091170.KS": ("KODEX 은행", Market.KR_STOCK),
    "139260.KS": ("TIGER 200 에너지화학", Market.KR_STOCK),
    "228790.KS": ("TIGER 화장품", Market.KR_STOCK),
    "091180.KS": ("KODEX 자동차", Market.KR_STOCK),
    "266370.KS": ("KODEX 200 ESG", Market.KR_STOCK),

    # 국내 기타 ETF - 해외주식형 (매매차익 배당소득세 15.4%)
    "360750.KS": ("TIGER S&P500", Market.KR_OTHER),
    "305720.KS": ("KODEX 미국S&P500TR", Market.KR_OTHER),
    "261240.KS": ("TIGER 미국나스닥100", Market.KR_OTHER),
    "379800.KS": ("KODEX 미국나스닥100TR", Market.KR_OTHER),
    "381180.KS": ("TIGER 미국필라델피아반도체나스닥", Market.KR_OTHER),
    "371460.KS": ("TIGER 차이나전기차SOLACTIVE", Market.KR_OTHER),
    "195930.KS": ("TIGER 유로스탁스50", Market.KR_OTHER),

    # 국내 기타 ETF - 채권형
    "148070.KS": ("KOSEF 국고채10년", Market.KR_OTHER),
    "114820.KS": ("KODEX 국고채3년", Market.KR_OTHER),
    "152380.KS": ("KODEX 국채선물10년", Market.KR_OTHER),
    "304660.KS": ("KODEX 미국채울트라30년선물(H)", Market.KR_OTHER),

    # 국내 기타 ETF - 원자재/기타
    "132030.KS": ("KODEX 골드선물(H)", Market.KR_OTHER),
    "130680.KS": ("TIGER 원유선물Enhanced(H)", Market.KR_OTHER),
    "252670.KS": ("KODEX 200선물인버스2X", Market.KR_OTHER),
    "122630.KS": ("KODEX 레버리지", Market.KR_OTHER),
}


def is_korean_ticker(ticker: str) -> bool:
    """한국 티커 여부 판별

    .KS (KRX 유가증권시장) 또는 .KQ (KOSDAQ) 접미사 확인
    """
    upper = ticker.upper()
    return upper.endswith(".KS") or upper.endswith(".KQ")


def normalize_ticker(user_input: str) -> str:
    """사용자 입력을 yfinance 형식으로 변환

    - 6자리 숫자 → 6자리.KS
    - 이미 .KS/.KQ 접미사 있으면 그대로
    - 그 외 → 대문자로 변환 (US 티커)

    Args:
        user_input: 사용자 입력 문자열

    Returns:
        yfinance 호환 티커 문자열
    """
    stripped = user_input.strip()

    # 6자리 숫자 → .KS 접미사 추가
    if re.match(r'^\d{6}$', stripped):
        return f"{stripped}.KS"

    # 이미 .KS/.KQ 접미사가 있으면 대문자로 정규화
    if is_korean_ticker(stripped):
        base, suffix = stripped.rsplit('.', 1)
        return f"{base}.{suffix.upper()}"

    # US 티커: 대문자로 변환
    return stripped.upper()


def classify_etf(ticker: str) -> ETFInfo:
    """ETF 분류 정보 반환

    Args:
        ticker: yfinance 형식 티커 (예: "069500.KS", "SPY")

    Returns:
        ETFInfo with market, currency, display_name
    """
    normalized = normalize_ticker(ticker)

    # 레지스트리에서 조회
    if normalized in KOREAN_ETF_REGISTRY:
        display_name, market = KOREAN_ETF_REGISTRY[normalized]
        return ETFInfo(
            ticker=normalized,
            display_name=display_name,
            market=market,
            currency="KRW"
        )

    # 한국 티커이지만 레지스트리에 없는 경우 → KR_OTHER (보수적)
    if is_korean_ticker(normalized):
        base = normalized.split('.')[0]
        return ETFInfo(
            ticker=normalized,
            display_name=base,
            market=Market.KR_OTHER,
            currency="KRW"
        )

    # US 티커
    return ETFInfo(
        ticker=normalized,
        display_name=normalized,
        market=Market.US,
        currency="USD"
    )


def classify_portfolio(allocation: Dict[str, float]) -> Dict[str, ETFInfo]:
    """포트폴리오 전체 ETF 분류

    Args:
        allocation: {ticker: weight} 딕셔너리

    Returns:
        {normalized_ticker: ETFInfo} 딕셔너리
    """
    return {normalize_ticker(ticker): classify_etf(ticker) for ticker in allocation}


def has_mixed_currencies(etf_info: Dict[str, ETFInfo]) -> bool:
    """혼합 통화 포트폴리오 여부"""
    currencies = {info.currency for info in etf_info.values()}
    return len(currencies) > 1


def get_tax_label(market: Market) -> str:
    """세금 유형 레이블 반환 (UI 표시용)"""
    labels = {
        Market.US: "양도소득세 22%",
        Market.KR_STOCK: "비과세",
        Market.KR_OTHER: "배당소득세 15.4%",
    }
    return labels[market]
