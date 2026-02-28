"""
최적 포트폴리오 배분 페이지

Mean-Variance Optimization을 통한 최적 자산 배분 계산
- Max Sharpe Ratio / Min Volatility 알고리즘
- Efficient Frontier 시각화
- 백테스트 연동
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.express as px
import plotly.graph_objects as go
import logging

from src.optimizer.portfolio_optimizer import PortfolioOptimizer
from src.backtest.portfolio_backtest import PortfolioBacktester
from src.dashboard.sidebar_utils import render_common_sidebar
from config.settings import ETF_BACKTEST_DEFAULTS, BACKTEST_CONSTANTS

logger = logging.getLogger(__name__)

# 프리셋 포트폴리오
PRESET_PORTFOLIOS = {
    "60/40 (주식/채권)": ["SPY", "BND"],
    "3 Fund (US/국제/채권)": ["VTI", "VXUS", "BND"],
    "Tech Heavy": ["QQQ", "VGT", "ARKK", "BND"],
    "배당 성장": ["VIG", "SCHD", "DGRO", "BND"],
    "올웨더 (Ray Dalio)": ["VTI", "TLT", "IEF", "GLD", "DBC"],
    "Custom": []
}


def show_optimization_page():
    """최적 포트폴리오 배분 페이지"""

    st.header("최적 포트폴리오 배분")
    st.markdown("Mean-Variance Optimization으로 최적의 자산 배분 비율을 계산합니다.")

    # 사이드바 설정
    with st.sidebar:
        st.subheader("포트폴리오 설정")

        # 프리셋 선택
        preset = st.selectbox(
            "프리셋 선택",
            options=list(PRESET_PORTFOLIOS.keys()),
            index=0,
            help="미리 정의된 포트폴리오 구성을 선택하세요"
        )

        # 프리셋에 따른 기본 티커 설정
        default_tickers = PRESET_PORTFOLIOS[preset]

        # 티커 입력
        tickers_input = st.text_input(
            "ETF 티커 (쉼표로 구분)",
            value=", ".join(default_tickers) if default_tickers else "SPY, QQQ, BND",
            help="2~10개의 ETF 티커를 입력하세요"
        )

        # 티커 파싱
        tickers = [t.strip().upper() for t in tickers_input.split(",") if t.strip()]

        if len(tickers) < 2:
            st.error("최소 2개 이상의 티커를 입력하세요.")
            return
        if len(tickers) > 10:
            st.error("최대 10개까지 입력 가능합니다.")
            return

        st.markdown("---")

        # 최적화 알고리즘 선택
        algorithm = st.radio(
            "최적화 알고리즘",
            options=["max_sharpe", "min_volatility"],
            format_func=lambda x: "Max Sharpe Ratio" if x == "max_sharpe" else "Min Volatility",
            help="Max Sharpe: 위험 대비 수익 최대화 | Min Volatility: 변동성 최소화"
        )

        st.markdown("---")

        # 분석 기간
        period_years = st.slider(
            "분석 기간 (년)",
            min_value=1,
            max_value=10,
            value=5,
            help="과거 N년 데이터를 사용하여 최적화 수행"
        )

        st.markdown("---")

        # 최적화 실행 버튼
        optimize_btn = st.button("최적화 실행", type="primary", use_container_width=True)

        st.markdown("---")

        # 백테스트 설정 (접기 가능)
        with st.expander("백테스트 설정", expanded=False):
            settings = render_common_sidebar(key_prefix="opt_")

    # 메인 영역
    if optimize_btn:
        try:
            with st.spinner("데이터 로딩 및 최적화 중..."):
                optimizer = PortfolioOptimizer(
                    tickers=tickers,
                    period_years=period_years,
                    risk_free_rate=BACKTEST_CONSTANTS['risk_free_rate']
                )
                optimizer.fetch_data()

                # 최적화 수행
                if algorithm == "max_sharpe":
                    optimal_weights = optimizer.optimize_max_sharpe()
                    algo_name = "Max Sharpe Ratio"
                else:
                    optimal_weights = optimizer.optimize_min_volatility()
                    algo_name = "Min Volatility"

                # 성과 지표 계산
                metrics = optimizer.get_performance_metrics(optimal_weights)

                # Efficient Frontier 계산
                ef_vol, ef_ret, ef_weights = optimizer.get_efficient_frontier(n_points=50)

                # 개별 자산 정보
                individual_assets = optimizer.get_individual_assets()

            # 결과를 세션 상태에 저장
            st.session_state['opt_weights'] = optimal_weights
            st.session_state['opt_metrics'] = metrics
            st.session_state['opt_algo'] = algo_name
            st.session_state['opt_ef'] = (ef_vol, ef_ret)
            st.session_state['opt_assets'] = individual_assets
            st.session_state['opt_tickers'] = tickers

        except ValueError as e:
            st.error(str(e))
            return
        except Exception as e:
            logger.error(f"Optimization error: {e}")
            st.error(f"최적화 중 오류가 발생했습니다: {e}")
            return

    # 결과 표시
    if 'opt_weights' in st.session_state:
        optimal_weights = st.session_state['opt_weights']
        metrics = st.session_state['opt_metrics']
        algo_name = st.session_state['opt_algo']
        ef_vol, ef_ret = st.session_state['opt_ef']
        individual_assets = st.session_state['opt_assets']
        tickers = st.session_state['opt_tickers']

        # 탭 구성
        tab1, tab2, tab3, tab4 = st.tabs([
            "최적 배분",
            "Efficient Frontier",
            "성과 지표",
            "백테스트"
        ])

        with tab1:
            _display_optimal_allocation(optimal_weights, algo_name)

        with tab2:
            _display_efficient_frontier(
                ef_vol, ef_ret,
                metrics['volatility'], metrics['expected_return'],
                individual_assets, algo_name
            )

        with tab3:
            _display_performance_metrics(metrics, algo_name)

        with tab4:
            _display_backtest_section(optimal_weights, settings)

    else:
        st.info("사이드바에서 티커를 입력하고 '최적화 실행' 버튼을 클릭하세요.")


def _display_optimal_allocation(weights: dict, algo_name: str):
    """최적 배분 결과 표시"""
    st.subheader(f"최적 자산 배분 ({algo_name})")

    col1, col2 = st.columns([1, 1])

    with col1:
        # 파이 차트
        df = pd.DataFrame([
            {'ETF': ticker, '비중': weight}
            for ticker, weight in weights.items()
            if weight > 0.001  # 0.1% 이상만 표시
        ])

        if not df.empty:
            fig = px.pie(
                df,
                values='비중',
                names='ETF',
                title='최적 포트폴리오 구성',
                hole=0.4
            )
            fig.update_traces(textinfo='label+percent', textposition='outside')
            fig.update_layout(height=400, showlegend=True)
            st.plotly_chart(fig, use_container_width=True)

    with col2:
        # 비중 테이블
        st.markdown("**배분 비율**")

        table_data = []
        for ticker, weight in sorted(weights.items(), key=lambda x: -x[1]):
            if weight > 0.001:
                table_data.append({
                    'ETF': ticker,
                    '비중 (%)': f"{weight * 100:.1f}%"
                })

        st.dataframe(
            pd.DataFrame(table_data),
            hide_index=True,
            use_container_width=True
        )


def _display_efficient_frontier(
    ef_vol: np.ndarray,
    ef_ret: np.ndarray,
    opt_vol: float,
    opt_ret: float,
    individual_assets: pd.DataFrame,
    algo_name: str
):
    """Efficient Frontier 시각화"""
    st.subheader("Efficient Frontier")

    fig = go.Figure()

    # Efficient Frontier 곡선
    fig.add_trace(go.Scatter(
        x=ef_vol * 100,
        y=ef_ret * 100,
        mode='lines',
        name='Efficient Frontier',
        line=dict(color='blue', width=2)
    ))

    # 최적 포트폴리오 포인트
    fig.add_trace(go.Scatter(
        x=[opt_vol * 100],
        y=[opt_ret * 100],
        mode='markers',
        name=f'최적 ({algo_name})',
        marker=dict(color='red', size=15, symbol='star')
    ))

    # 개별 자산 포인트
    fig.add_trace(go.Scatter(
        x=individual_assets['volatility'] * 100,
        y=individual_assets['expected_return'] * 100,
        mode='markers+text',
        name='개별 자산',
        marker=dict(color='green', size=10),
        text=individual_assets['ticker'],
        textposition='top center'
    ))

    fig.update_layout(
        title='Efficient Frontier',
        xaxis_title='연간 변동성 (%)',
        yaxis_title='연간 기대수익률 (%)',
        height=500,
        showlegend=True,
        hovermode='closest'
    )

    st.plotly_chart(fig, use_container_width=True)

    st.caption(
        "💡 Efficient Frontier는 주어진 위험 수준에서 달성 가능한 최대 수익률을 나타냅니다. "
        "빨간 별은 선택한 알고리즘의 최적 포트폴리오입니다."
    )


def _display_performance_metrics(metrics: dict, algo_name: str):
    """성과 지표 표시"""
    st.subheader(f"예상 성과 지표 ({algo_name})")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="연간 기대수익률",
            value=f"{metrics['expected_return'] * 100:.1f}%",
            help="과거 데이터 기반 연간 기대수익률"
        )

    with col2:
        st.metric(
            label="연간 변동성",
            value=f"{metrics['volatility'] * 100:.1f}%",
            help="연간 표준편차 (위험 지표)"
        )

    with col3:
        st.metric(
            label="샤프 비율",
            value=f"{metrics['sharpe_ratio']:.2f}",
            help="위험 대비 초과수익 (무위험수익률 3% 기준)"
        )

    st.markdown("---")

    st.warning(
        "⚠️ **주의사항**: 위 지표는 과거 데이터 기반 추정치입니다. "
        "실제 투자 성과는 다를 수 있으며, 과거 성과가 미래 수익을 보장하지 않습니다."
    )


def _display_backtest_section(weights: dict, settings):
    """백테스트 섹션"""
    st.subheader("백테스트")

    st.markdown(
        "최적화된 배분 비율로 과거 성과를 시뮬레이션합니다. "
        "한국 세금 (배당소득세 15%, 양도소득세 22%)이 반영됩니다."
    )

    # 현재 배분 비율 표시
    st.markdown("**적용될 배분 비율:**")
    weight_str = " | ".join([f"{t}: {w*100:.1f}%" for t, w in weights.items() if w > 0.001])
    st.code(weight_str)

    # 백테스트 실행 버튼
    if st.button("백테스트 실행", key="run_backtest"):
        # 0 비중 제거
        allocation = {t: w for t, w in weights.items() if w > 0.001}

        try:
            with st.spinner("백테스트 실행 중..."):
                backtester = PortfolioBacktester(
                    initial_capital=settings.initial_capital,
                    allocation=allocation,
                    rebalance_frequency=settings.rebalance_freq,
                    withdrawal_rate=settings.withdrawal_rate,
                    dividend_tax_rate=settings.dividend_tax_rate,
                    capital_gains_tax_rate=settings.capital_gains_tax_rate,
                    transaction_cost_rate=settings.transaction_cost_rate
                )

                result = backtester.run(years=settings.backtest_years)

            # 결과 표시
            _display_backtest_results(result, backtester)

        except Exception as e:
            logger.error(f"Backtest error: {e}")
            st.error(f"백테스트 중 오류가 발생했습니다: {e}")


def _display_backtest_results(result, backtester):
    """백테스트 결과 표시"""
    st.markdown("---")
    st.subheader("백테스트 결과")

    # 성과 지표
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("CAGR", f"{result.cagr:.1f}%")
    with col2:
        st.metric("샤프 비율", f"{result.sharpe_ratio:.2f}")
    with col3:
        st.metric("최대 낙폭", f"{result.max_drawdown:.1f}%")
    with col4:
        st.metric("변동성", f"{result.volatility:.1f}%")

    # 포트폴리오 가치 차트
    st.markdown("**포트폴리오 가치 추이**")

    df = backtester.get_portfolio_history_df(result)

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df['date'],
        y=df['total_value'],
        mode='lines',
        name='포트폴리오 가치',
        fill='tozeroy',
        line=dict(color='#1f77b4', width=2)
    ))

    fig.update_layout(
        xaxis_title='날짜',
        yaxis_title='가치 (USD)',
        height=400,
        hovermode='x unified'
    )

    st.plotly_chart(fig, use_container_width=True)

    # 연간 요약
    st.markdown("**연간 성과 요약**")
    annual_df = backtester.get_annual_summary_df(result)

    if not annual_df.empty:
        # 컬럼 포맷팅
        display_df = annual_df.copy()
        for col in display_df.columns:
            if col == '연도':
                continue
            elif '%' in col or '수익률' in col:
                display_df[col] = display_df[col].apply(lambda x: f"{x:.1f}%")
            else:
                display_df[col] = display_df[col].apply(lambda x: f"${x:,.0f}")

        st.dataframe(display_df, hide_index=True, use_container_width=True)

    # 총계
    st.markdown("**총계**")
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric("총 인출금", f"${result.total_withdrawal:,.0f}")
    with col2:
        st.metric("총 배당금", f"${result.total_dividend_net:,.0f}")
    with col3:
        st.metric("총 세금", f"${result.total_tax:,.0f}")
    with col4:
        st.metric("총 거래비용", f"${result.total_transaction_cost:,.0f}")


# 페이지 함수 (main_app에서 호출)
def show_portfolio_optimization_page():
    """포트폴리오 최적화 페이지 (외부 호출용)"""
    show_optimization_page()
