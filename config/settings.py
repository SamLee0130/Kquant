"""
Kquant 프로젝트 설정 파일
"""
import os
from pathlib import Path
from dotenv import load_dotenv

# 환경변수 로드
load_dotenv()

# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
SQL_DIR = PROJECT_ROOT / "sql"
CONFIG_DIR = PROJECT_ROOT / "config"

# 데이터베이스 설정
DATABASE_PATH = DATA_DIR / "kquant.db"

# API 설정
ALPHA_VANTAGE_API_KEY = os.getenv("ALPHA_VANTAGE_API_KEY", "")
POLYGON_API_KEY = os.getenv("POLYGON_API_KEY", "")

# 기본 백테스트 설정
DEFAULT_SETTINGS = {
    "initial_capital": 1_000_000,  # 초기 자본금 (원)
    "commission": 0.003,           # 거래 수수료 (0.3%)
    "slippage": 0.001,            # 슬리피지 (0.1%)
    "currency": "KRW"
}

# 데이터 수집 설정
DATA_COLLECTION = {
    "default_period": "1y",        # 기본 데이터 수집 기간
    "retry_count": 3,              # API 재시도 횟수
    "timeout": 30,                 # API 타임아웃 (초)
    "delay_between_requests": 1    # 요청 간 딜레이 (초)
}

# 스트림릿 대시보드 설정
STREAMLIT_CONFIG = {
    "page_title": "Kquant 백테스트 대시보드",
    "page_icon": "📈",
    "layout": "wide",
    "sidebar_state": "expanded"
}

# 로깅 설정
LOGGING_CONFIG = {
    "level": "INFO",
    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    "handlers": ["console", "file"]
}

# 주요 주식 종목 리스트 (예시)
KOREAN_STOCKS = [
    "005930",  # 삼성전자
    "000660",  # SK하이닉스  
    "035420",  # NAVER
    "005380",  # 현대차
    "051910",  # LG화학
    "068270",  # 셀트리온
    "006400",  # 삼성SDI
    "035720",  # 카카오
    "207940",  # 삼성바이오로직스
    "005490"   # POSCO홀딩스
]

# 주요 암호화폐 리스트 (예시)
CRYPTOCURRENCIES = [
    "BTC-KRW",   # 비트코인
    "ETH-KRW",   # 이더리움
    "XRP-KRW",   # 리플
    "ADA-KRW",   # 에이다
    "DOT-KRW",   # 폴카닷
    "LINK-KRW",  # 체인링크
    "BCH-KRW",   # 비트코인캐시
    "LTC-KRW",   # 라이트코인
    "EOS-KRW",   # 이오스
    "TRX-KRW"    # 트론
]

# 기술지표 설정
TECHNICAL_INDICATORS = {
    "sma_periods": [5, 10, 20, 50, 100, 200],
    "ema_periods": [12, 26],
    "rsi_period": 14,
    "bollinger_period": 20,
    "bollinger_std": 2,
    "macd_fast": 12,
    "macd_slow": 26,
    "macd_signal": 9
}

# ETF 자산 배분 백테스트 기본 설정
ETF_BACKTEST_DEFAULTS = {
    "initial_capital": 1_000_000,     # 초기 자본금 (USD)
    "backtest_years": 10,             # 백테스팅 기간 (년)
    "rebalance_frequency": "quarterly",  # 리밸런싱 주기 ('quarterly' 또는 'yearly')
    "withdrawal_rate": 0.05,          # 연간 인출률 (5%)
    "dividend_tax_rate": 0.15,        # 배당소득세율 (15%)
    "capital_gains_tax_rate": 0.22,   # 양도소득세율 (22%)
    "capital_gains_exemption": 2000.0,  # 양도소득세 기본공제 ($2,000)
    "transaction_cost_rate": 0.002,   # 거래비용 - 수수료+슬리피지 (0.2%)
    "default_allocation": {           # 기본 자산 배분
        "SPY": 0.60,                  # S&P 500 ETF (60%)
        "QQQ": 0.30,                  # Nasdaq 100 ETF (30%)
        "BIL": 0.10                   # 단기 국채 ETF (10%)
    }
}

# 대표 미국 ETF 리스트
US_ETFS = [
    "SPY",   # SPDR S&P 500 ETF
    "QQQ",   # Invesco QQQ Trust (Nasdaq 100)
    "BIL",   # SPDR Bloomberg 1-3 Month T-Bill ETF
    "VTI",   # Vanguard Total Stock Market ETF
    "VOO",   # Vanguard S&P 500 ETF
    "IWM",   # iShares Russell 2000 ETF
    "TLT",   # iShares 20+ Year Treasury Bond ETF
    "GLD",   # SPDR Gold Shares
    "VNQ",   # Vanguard Real Estate ETF
    "SCHD",  # Schwab US Dividend Equity ETF
]
