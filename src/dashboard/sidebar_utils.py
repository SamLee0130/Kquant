"""
공통 사이드바 설정 유틸리티

자산 배분 백테스트 페이지와 포트폴리오 비교 페이지에서
공통으로 사용하는 사이드바 입력 위젯을 제공합니다.
"""
import streamlit as st
from dataclasses import dataclass
from config.settings import ETF_BACKTEST_DEFAULTS


@dataclass
class BacktestSettings:
    """백테스트 설정 값"""
    initial_capital: float
    backtest_years: int
    rebalance_freq: str
    withdrawal_rate: float
    dividend_tax_rate: float
    capital_gains_tax_rate: float
    transaction_cost_rate: float


def render_common_sidebar(key_prefix: str = "") -> BacktestSettings:
    """공통 백테스트 설정 사이드바 렌더링

    Args:
        key_prefix: Streamlit 위젯 키 접두사 (페이지별 고유성 보장)

    Returns:
        BacktestSettings 데이터클래스
    """
    st.subheader("백테스트 설정" if not key_prefix else "공통 설정")

    # 초기 자본
    initial_capital = st.number_input(
        "초기 자본 (USD)",
        min_value=10_000,
        max_value=100_000_000,
        value=ETF_BACKTEST_DEFAULTS['initial_capital'],
        step=100_000,
        format="%d",
        key=f"{key_prefix}initial_capital" if key_prefix else None,
        help="백테스트 시작 시 투자할 초기 자본금"
    )

    # 백테스팅 기간
    backtest_years = st.number_input(
        "백테스팅 기간 (년)",
        min_value=1,
        max_value=30,
        value=ETF_BACKTEST_DEFAULTS['backtest_years'],
        step=1,
        key=f"{key_prefix}backtest_years" if key_prefix else None,
        help="최근 N년 동안의 백테스트 수행"
    )

    # 리밸런싱 주기
    rebalance_freq = st.selectbox(
        "리밸런싱 주기",
        options=['quarterly', 'yearly'],
        index=0 if ETF_BACKTEST_DEFAULTS['rebalance_frequency'] == 'quarterly' else 1,
        format_func=lambda x: '분기별' if x == 'quarterly' else '연간',
        key=f"{key_prefix}rebalance_freq" if key_prefix else None,
        help="포트폴리오 리밸런싱 주기"
    )

    # 연간 인출률
    withdrawal_rate = st.number_input(
        "연간 인출률 (%)",
        min_value=0.0,
        max_value=20.0,
        value=ETF_BACKTEST_DEFAULTS['withdrawal_rate'] * 100,
        step=0.5,
        key=f"{key_prefix}withdrawal_rate" if key_prefix else None,
        help="매년 포트폴리오에서 인출하는 비율"
    ) / 100

    st.markdown("---")
    st.subheader("세금 설정")

    # 배당소득세
    dividend_tax_rate = st.number_input(
        "배당소득세 (%)",
        min_value=0.0,
        max_value=50.0,
        value=ETF_BACKTEST_DEFAULTS['dividend_tax_rate'] * 100,
        step=1.0,
        key=f"{key_prefix}dividend_tax" if key_prefix else None,
        help="배당금에 부과되는 세율"
    ) / 100

    # 양도소득세
    capital_gains_tax_rate = st.number_input(
        "양도소득세 (%)",
        min_value=0.0,
        max_value=50.0,
        value=ETF_BACKTEST_DEFAULTS['capital_gains_tax_rate'] * 100,
        step=1.0,
        key=f"{key_prefix}capital_gains_tax" if key_prefix else None,
        help="양도차익에 부과되는 세율 (연말 정산, 다음해 차감)"
    ) / 100

    st.markdown("---")
    st.subheader("거래비용 설정")

    # 거래비용
    transaction_cost_rate = st.number_input(
        "거래비용 (%)",
        min_value=0.0,
        max_value=2.0,
        value=ETF_BACKTEST_DEFAULTS['transaction_cost_rate'] * 100,
        step=0.05,
        key=f"{key_prefix}transaction_cost" if key_prefix else None,
        help="거래수수료 + 슬리피지 (거래금액의 %)"
    ) / 100

    return BacktestSettings(
        initial_capital=initial_capital,
        backtest_years=backtest_years,
        rebalance_freq=rebalance_freq,
        withdrawal_rate=withdrawal_rate,
        dividend_tax_rate=dividend_tax_rate,
        capital_gains_tax_rate=capital_gains_tax_rate,
        transaction_cost_rate=transaction_cost_rate
    )
