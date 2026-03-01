"""
Kquant 프로젝트 설정 파일
"""
import numpy as np

# 백테스트 엔진 상수
BACKTEST_CONSTANTS = {
    "snapshot_threshold_day": 7,           # 월별 스냅샷 저장 기준일 (매월 N일 이전)
    "risk_free_rate": 0.03,                # 무위험수익률 (샤프비율 계산용)
    "volatility_annualization": np.sqrt(12),  # 월별 데이터 연율화 팩터
    "min_trade_value": 1.0,          # 최소 거래 금액 ($1 이상 차이 시 거래)
    "min_data_days": 252,            # 최소 데이터 일수 (약 1년)
}

# 대시보드 상수
DASHBOARD_CONSTANTS = {
    "max_comparison_portfolios": 5,   # 비교 페이지 최대 포트폴리오 수
    "max_optimization_etfs": 10,      # 최적화 최대 ETF 수
}

# 스트림릿 대시보드 설정
STREAMLIT_CONFIG = {
    "page_title": "Kquant 백테스트 대시보드",
    "page_icon": "📈",
    "layout": "wide",
    "sidebar_state": "expanded"
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

# 한국 상장 ETF 세금 설정
KOREAN_TAX_DEFAULTS = {
    "kr_dividend_tax_rate": 0.154,          # 배당소득세 15.4% (소득세 14% + 지방소득세 1.4%)
    "kr_other_capital_gains_rate": 0.154,   # 기타 ETF 매매차익 배당소득세 15.4%
    "kr_stock_capital_gains_rate": 0.0,     # 국내주식형 ETF 양도차익 비과세
}

# 한국 ETF 프리셋 포트폴리오
KOREAN_ETF_PRESETS = {
    "국내주식형": {
        "069500.KS": 0.50,    # KODEX 200
        "102110.KS": 0.50,    # TIGER 200
    },
    "글로벌 분산 (국내상장)": {
        "069500.KS": 0.30,    # KODEX 200
        "360750.KS": 0.40,    # TIGER S&P500
        "148070.KS": 0.30,    # KOSEF 국고채10년
    },
    "해외 ETF (국내상장)": {
        "360750.KS": 0.40,    # TIGER S&P500
        "261240.KS": 0.30,    # TIGER 미국나스닥100
        "305720.KS": 0.30,    # KODEX 미국S&P500TR
    },
    "한국 올웨더": {
        "069500.KS": 0.30,    # KODEX 200
        "360750.KS": 0.25,    # TIGER S&P500
        "148070.KS": 0.25,    # KOSEF 국고채10년
        "132030.KS": 0.20,    # KODEX 골드선물(H)
    },
}
