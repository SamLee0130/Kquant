"""
공통 사이드바 설정 유틸리티

자산 배분 백테스트 페이지와 포트폴리오 비교 페이지에서
공통으로 사용하는 사이드바 입력 위젯을 제공합니다.
"""
import streamlit as st
from dataclasses import dataclass
from config.settings import ETF_BACKTEST_DEFAULTS, KOREAN_TAX_DEFAULTS, CURRENCY_DEFAULTS


@dataclass
class BacktestSettings:
    """백테스트 설정 값"""
    initial_capital: float
    base_currency: str
    backtest_years: int
    rebalance_freq: str
    withdrawal_rate: float
    dividend_tax_rate: float
    capital_gains_tax_rate: float
    transaction_cost_rate: float
    kr_dividend_tax_rate: float = 0.154
    kr_capital_gains_rate: float = 0.154


def render_common_sidebar(key_prefix: str = "") -> BacktestSettings:
    """공통 백테스트 설정 사이드바 렌더링

    Args:
        key_prefix: Streamlit 위젯 키 접두사 (페이지별 고유성 보장)

    Returns:
        BacktestSettings 데이터클래스
    """
    st.subheader("백테스트 설정" if not key_prefix else "공통 설정")

    # 기준 통화
    base_currency = st.selectbox(
        "기준 통화",
        options=CURRENCY_DEFAULTS["base_currencies"],
        index=0,  # KRW 기본값
        key=f"{key_prefix}base_currency" if key_prefix else "base_currency",
        help="포트폴리오 가치를 표시할 기준 통화. 혼합 포트폴리오는 이 통화로 환산됩니다."
    )

    # 초기 자본 (기준 통화에 따라 동적 변경)
    is_krw = base_currency == "KRW"
    capital_label = f"초기 자본 ({base_currency})"
    capital_default = CURRENCY_DEFAULTS["default_capital_krw"] if is_krw else CURRENCY_DEFAULTS["default_capital_usd"]
    capital_max = 100_000_000_000 if is_krw else 100_000_000
    capital_step = 100_000_000 if is_krw else 100_000

    initial_capital = st.number_input(
        capital_label,
        min_value=10_000,
        max_value=capital_max,
        value=capital_default,
        step=capital_step,
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

    st.caption("해외 상장 ETF")

    # 배당소득세
    dividend_tax_rate = st.number_input(
        "배당소득세 (%)",
        min_value=0.0,
        max_value=50.0,
        value=ETF_BACKTEST_DEFAULTS['dividend_tax_rate'] * 100,
        step=1.0,
        key=f"{key_prefix}dividend_tax" if key_prefix else None,
        help="해외 ETF 배당금에 부과되는 세율"
    ) / 100

    # 양도소득세
    capital_gains_tax_rate = st.number_input(
        "양도소득세 (%)",
        min_value=0.0,
        max_value=50.0,
        value=ETF_BACKTEST_DEFAULTS['capital_gains_tax_rate'] * 100,
        step=1.0,
        key=f"{key_prefix}capital_gains_tax" if key_prefix else None,
        help="해외 ETF 양도차익 세율 (연말 정산, 다음해 차감)"
    ) / 100

    with st.expander("국내 상장 ETF 세금", expanded=False):
        kr_dividend_tax_rate = st.number_input(
            "국내 배당소득세 (%)",
            min_value=0.0,
            max_value=50.0,
            value=KOREAN_TAX_DEFAULTS['kr_dividend_tax_rate'] * 100,
            step=0.1,
            key=f"{key_prefix}kr_dividend_tax" if key_prefix else None,
            help="국내 ETF 배당소득세 (소득세 14% + 지방소득세 1.4%)"
        ) / 100

        kr_capital_gains_rate = st.number_input(
            "국내 기타 ETF 매매차익 세율 (%)",
            min_value=0.0,
            max_value=50.0,
            value=KOREAN_TAX_DEFAULTS['kr_other_capital_gains_rate'] * 100,
            step=0.1,
            key=f"{key_prefix}kr_capital_gains_tax" if key_prefix else None,
            help="국내 기타 ETF (해외/채권/원자재) 매매차익 배당소득세"
        ) / 100

        st.caption("국내 주식형 ETF 양도차익은 비과세")

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
        base_currency=base_currency,
        backtest_years=backtest_years,
        rebalance_freq=rebalance_freq,
        withdrawal_rate=withdrawal_rate,
        dividend_tax_rate=dividend_tax_rate,
        capital_gains_tax_rate=capital_gains_tax_rate,
        transaction_cost_rate=transaction_cost_rate,
        kr_dividend_tax_rate=kr_dividend_tax_rate,
        kr_capital_gains_rate=kr_capital_gains_rate
    )
