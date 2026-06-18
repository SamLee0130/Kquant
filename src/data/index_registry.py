"""
주요국 증시 비교용 레지스트리

각 시장을 추종 ETF에 매핑한다. 야후의 원시 지수(^GSPC, ^N225 등)는 배당이 빠진
price return이고 현지 통화 기준이라, 배당 재투자가 반영되고 USD로 거래되는
추종 ETF의 total return을 사용한다.

- 미국 지수(S&P500/Nasdaq100/Dow/Russell2000)는 실제 지수를 추종하는 ETF.
- 그 외 주요국은 해당 국가 증시를 대표하는 USD 상장 ETF(주로 iShares MSCI 시리즈).
- 한국은 실제 KOSPI 200을 추종하는 국내 상장 KODEX 200(KRW)을 기준 통화로 환산.

통화 변환은 CurrencyConverter(USD↔KRW)만 지원하므로 추종 ETF는 USD 또는 KRW
상장으로 한정한다.
"""
from dataclasses import dataclass
from typing import Dict, List


@dataclass(frozen=True)
class IndexInfo:
    """비교 대상 시장 정보"""
    key: str            # 내부 식별자
    display_name: str   # UI 표시명 (국기 + 시장명)
    etf_ticker: str     # 배당 재투자(total return) 추종 ETF 심볼
    currency: str       # ETF 거래 통화 ("USD" 또는 "KRW")
    description: str     # 추종 ETF/지수 설명


# 비교 가능한 시장 목록 (추종 ETF total return 기준, 지역별 정렬)
INDEX_REGISTRY: Dict[str, IndexInfo] = {
    # 미국 (실제 지수 추종)
    "sp500": IndexInfo("sp500", "🇺🇸 S&P 500", "SPY", "USD", "미국 대형주 500"),
    "nasdaq100": IndexInfo("nasdaq100", "🇺🇸 Nasdaq 100", "QQQ", "USD", "미국 기술주 100"),
    "dowjones": IndexInfo("dowjones", "🇺🇸 Dow Jones", "DIA", "USD", "미국 우량주 30"),
    "russell2000": IndexInfo("russell2000", "🇺🇸 Russell 2000", "IWM", "USD", "미국 소형주 2000"),
    # 북미 기타
    "canada": IndexInfo("canada", "🇨🇦 캐나다", "EWC", "USD", "MSCI Canada"),
    # 아시아·태평양
    "kospi200": IndexInfo("kospi200", "🇰🇷 KOSPI 200", "069500.KS", "KRW", "한국 대형주 (KODEX 200)"),
    "japan": IndexInfo("japan", "🇯🇵 일본", "EWJ", "USD", "MSCI Japan"),
    "china": IndexInfo("china", "🇨🇳 중국", "MCHI", "USD", "MSCI China"),
    "hongkong": IndexInfo("hongkong", "🇭🇰 홍콩", "EWH", "USD", "MSCI Hong Kong"),
    "taiwan": IndexInfo("taiwan", "🇹🇼 대만", "EWT", "USD", "MSCI Taiwan"),
    "india": IndexInfo("india", "🇮🇳 인도", "INDA", "USD", "MSCI India"),
    "australia": IndexInfo("australia", "🇦🇺 호주", "EWA", "USD", "MSCI Australia"),
    # 유럽
    "europe": IndexInfo("europe", "🇪🇺 유럽 (전체)", "VGK", "USD", "FTSE Developed Europe"),
    "eurozone": IndexInfo("eurozone", "🇪🇺 유로존", "EZU", "USD", "MSCI EMU"),
    "germany": IndexInfo("germany", "🇩🇪 독일", "EWG", "USD", "MSCI Germany"),
    "uk": IndexInfo("uk", "🇬🇧 영국", "EWU", "USD", "MSCI United Kingdom"),
    "france": IndexInfo("france", "🇫🇷 프랑스", "EWQ", "USD", "MSCI France"),
    # 신흥국·중남미
    "brazil": IndexInfo("brazil", "🇧🇷 브라질", "EWZ", "USD", "MSCI Brazil"),
    # 글로벌·테마
    "emerging": IndexInfo("emerging", "🌏 신흥국 전체", "EEM", "USD", "MSCI Emerging Markets"),
    "world": IndexInfo("world", "🌐 전세계", "VT", "USD", "FTSE Global All Cap"),
}

# 페이지 진입 시 기본 선택 시장
DEFAULT_INDEX_KEYS: List[str] = ["sp500", "nasdaq100", "kospi200"]

# 동시 비교 대상 최대 개수
MAX_COMPARISON_INDICES = 5


def get_index(key: str) -> IndexInfo:
    """키로 시장 정보 조회"""
    return INDEX_REGISTRY[key]
