"""
Kquant 프로젝트 설정 파일
"""

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
