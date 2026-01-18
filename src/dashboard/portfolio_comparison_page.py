"""
포트폴리오 비교 페이지

최대 5개의 자산 배분 포트폴리오 성과를 비교합니다.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import logging

from src.backtest.portfolio_backtest import PortfolioBacktester, BacktestResult
from config.settings import ETF_BACKTEST_DEFAULTS

logger = logging.getLogger(__name__)

# 포트폴리오별 색상
PORTFOLIO_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']


def show_portfolio_comparison_page():
    """포트폴리오 비교 페이지 표시"""
    st.header("포트폴리오 비교")
    st.markdown("최대 5개의 자산 배분 포트폴리오 성과를 비교합니다.")
    st.markdown("---")
    
    # 사이드바 - 공통 설정
    with st.sidebar:
        st.subheader("공통 설정")
        
        initial_capital = st.number_input(
            "초기 자본 (USD)",
            min_value=10_000,
            max_value=100_000_000,
            value=ETF_BACKTEST_DEFAULTS['initial_capital'],
            step=100_000,
            format="%d",
            key="compare_initial_capital"
        )
        
        backtest_years = st.number_input(
            "백테스팅 기간 (년)",
            min_value=1,
            max_value=30,
            value=ETF_BACKTEST_DEFAULTS['backtest_years'],
            step=1,
            key="compare_backtest_years"
        )
        
        rebalance_freq = st.selectbox(
            "리밸런싱 주기",
            options=['quarterly', 'yearly'],
            index=0 if ETF_BACKTEST_DEFAULTS['rebalance_frequency'] == 'quarterly' else 1,
            format_func=lambda x: '분기별' if x == 'quarterly' else '연간',
            key="compare_rebalance_freq"
        )
        
        withdrawal_rate = st.number_input(
            "연간 인출률 (%)",
            min_value=0.0,
            max_value=20.0,
            value=ETF_BACKTEST_DEFAULTS['withdrawal_rate'] * 100,
            step=0.5,
            key="compare_withdrawal_rate"
        ) / 100
        
        st.markdown("---")
        st.subheader("세금 설정")
        
        dividend_tax_rate = st.number_input(
            "배당소득세 (%)",
            min_value=0.0,
            max_value=50.0,
            value=ETF_BACKTEST_DEFAULTS['dividend_tax_rate'] * 100,
            step=1.0,
            key="compare_dividend_tax"
        ) / 100
        
        capital_gains_tax_rate = st.number_input(
            "양도소득세 (%)",
            min_value=0.0,
            max_value=50.0,
            value=ETF_BACKTEST_DEFAULTS['capital_gains_tax_rate'] * 100,
            step=1.0,
            key="compare_capital_gains_tax"
        ) / 100
        
        st.markdown("---")
        st.subheader("거래비용 설정")
        
        transaction_cost_rate = st.number_input(
            "거래비용 (%)",
            min_value=0.0,
            max_value=2.0,
            value=ETF_BACKTEST_DEFAULTS['transaction_cost_rate'] * 100,
            step=0.05,
            key="compare_transaction_cost",
            help="거래수수료 + 슬리피지 (거래금액의 %)"
        ) / 100
    
    # 포트폴리오 추가 활성화 여부 (메인 영역 상단)
    col_check1, col_check2, col_check3 = st.columns(3)

    with col_check1:
        enable_portfolio_3 = st.checkbox(
            "포트폴리오 3 추가",
            value=False,
            key="enable_portfolio_3"
        )

    with col_check2:
        enable_portfolio_4 = st.checkbox(
            "포트폴리오 4 추가",
            value=False,
            key="enable_portfolio_4"
        )

    with col_check3:
        enable_portfolio_5 = st.checkbox(
            "포트폴리오 5 추가",
            value=False,
            key="enable_portfolio_5"
        )

    # 세션 상태 초기화 - 포트폴리오 1, 2, 3, 4, 5
    if 'portfolio_1' not in st.session_state:
        st.session_state.portfolio_1 = {'SPY': 0.60, 'QQQ': 0.30, 'BIL': 0.10}

    if 'portfolio_2' not in st.session_state:
        st.session_state.portfolio_2 = {'SPY': 0.40, 'QQQ': 0.40, 'BND': 0.20}

    if 'portfolio_3' not in st.session_state:
        st.session_state.portfolio_3 = {'VTI': 0.50, 'VXUS': 0.30, 'BND': 0.20}

    if 'portfolio_4' not in st.session_state:
        st.session_state.portfolio_4 = {'SPY': 0.30, 'QQQ': 0.30, 'VTI': 0.20, 'BND': 0.20}

    if 'portfolio_5' not in st.session_state:
        st.session_state.portfolio_5 = {'SPY': 0.25, 'QQQ': 0.25, 'VTI': 0.25, 'BND': 0.25}
    
    # 메인 영역 - 포트폴리오 설정
    # 활성화된 포트폴리오 목록 생성
    portfolios = [
        ('포트폴리오 1', st.session_state.portfolio_1, 'p1'),
        ('포트폴리오 2', st.session_state.portfolio_2, 'p2'),
    ]

    if enable_portfolio_3:
        portfolios.append(('포트폴리오 3', st.session_state.portfolio_3, 'p3'))
    if enable_portfolio_4:
        portfolios.append(('포트폴리오 4', st.session_state.portfolio_4, 'p4'))
    if enable_portfolio_5:
        portfolios.append(('포트폴리오 5', st.session_state.portfolio_5, 'p5'))

    num_portfolios = len(portfolios)

    # 컬럼 생성 및 포트폴리오 할당 UI 렌더링
    cols = st.columns(num_portfolios)
    allocations = []

    for col, (name, default_allocation, key_prefix) in zip(cols, portfolios):
        with col:
            st.subheader(name)
            allocation = _render_portfolio_allocation(default_allocation, key_prefix)
            allocations.append(allocation)

    # 개별 변수에 할당 (하위 호환성 유지)
    allocation_1 = allocations[0]
    allocation_2 = allocations[1]
    allocation_3 = allocations[2] if num_portfolios >= 3 else None
    allocation_4 = allocations[3] if num_portfolios >= 4 else None
    allocation_5 = allocations[4] if num_portfolios >= 5 else None
    
    st.markdown("---")
    
    # 비교 실행 버튼 - 유효성 검사
    valid_1 = abs(sum(allocation_1.values()) - 1.0) <= 0.01
    valid_2 = abs(sum(allocation_2.values()) - 1.0) <= 0.01
    valid_3 = True if not enable_portfolio_3 else abs(sum(allocation_3.values()) - 1.0) <= 0.01
    valid_4 = True if not enable_portfolio_4 else abs(sum(allocation_4.values()) - 1.0) <= 0.01
    valid_5 = True if not enable_portfolio_5 else abs(sum(allocation_5.values()) - 1.0) <= 0.01

    all_valid = valid_1 and valid_2 and valid_3 and valid_4 and valid_5

    if st.button("비교 실행", type="primary", disabled=not all_valid):
        if not valid_1:
            st.error("포트폴리오 1의 비중 합계가 100%가 아닙니다.")
            return
        if not valid_2:
            st.error("포트폴리오 2의 비중 합계가 100%가 아닙니다.")
            return
        if enable_portfolio_3 and not valid_3:
            st.error("포트폴리오 3의 비중 합계가 100%가 아닙니다.")
            return
        if enable_portfolio_4 and not valid_4:
            st.error("포트폴리오 4의 비중 합계가 100%가 아닙니다.")
            return
        if enable_portfolio_5 and not valid_5:
            st.error("포트폴리오 5의 비중 합계가 100%가 아닙니다.")
            return
        
        with st.spinner("백테스트 실행 중..."):
            # 백테스트 기간 계산: 종료일 기준 과거 N년의 1월 1일로 고정
            end_date = datetime.now()
            start_year = end_date.year - backtest_years
            start_date = datetime(start_year, 1, 1)
            
            # 공통 설정
            common_params = {
                'initial_capital': initial_capital,
                'rebalance_frequency': rebalance_freq,
                'withdrawal_rate': withdrawal_rate,
                'dividend_tax_rate': dividend_tax_rate,
                'capital_gains_tax_rate': capital_gains_tax_rate,
                'transaction_cost_rate': transaction_cost_rate
            }
            
            # 포트폴리오 1 백테스트
            backtester_1 = PortfolioBacktester(allocation=allocation_1, **common_params)
            result_1 = backtester_1.run(start_date, end_date)

            # 포트폴리오 2 백테스트
            backtester_2 = PortfolioBacktester(allocation=allocation_2, **common_params)
            result_2 = backtester_2.run(start_date, end_date)

            # 포트폴리오 3 백테스트 (활성화된 경우)
            backtester_3 = None
            result_3 = None
            if enable_portfolio_3:
                backtester_3 = PortfolioBacktester(allocation=allocation_3, **common_params)
                result_3 = backtester_3.run(start_date, end_date)

            # 포트폴리오 4 백테스트 (활성화된 경우)
            backtester_4 = None
            result_4 = None
            if enable_portfolio_4:
                backtester_4 = PortfolioBacktester(allocation=allocation_4, **common_params)
                result_4 = backtester_4.run(start_date, end_date)

            # 포트폴리오 5 백테스트 (활성화된 경우)
            backtester_5 = None
            result_5 = None
            if enable_portfolio_5:
                backtester_5 = PortfolioBacktester(allocation=allocation_5, **common_params)
                result_5 = backtester_5.run(start_date, end_date)
        
        st.success("비교 완료!")

        # 결과 수집
        backtesters = [backtester_1, backtester_2]
        results = [result_1, result_2]
        allocations = [allocation_1, allocation_2]

        if enable_portfolio_3:
            backtesters.append(backtester_3)
            results.append(result_3)
            allocations.append(allocation_3)

        if enable_portfolio_4:
            backtesters.append(backtester_4)
            results.append(result_4)
            allocations.append(allocation_4)

        if enable_portfolio_5:
            backtesters.append(backtester_5)
            results.append(result_5)
            allocations.append(allocation_5)
        
        # 결과 표시
        _display_comparison_results(
            backtesters=backtesters,
            results=results,
            allocations=allocations,
            initial_capital=initial_capital
        )


def _render_portfolio_allocation(portfolio: dict, key_prefix: str) -> dict:
    """포트폴리오 자산 배분 UI 렌더링"""
    
    # ETF 추가
    col_add1, col_add2 = st.columns([3, 1])
    
    with col_add1:
        new_etf = st.text_input(
            "ETF 추가",
            placeholder="예: VOO, TLT",
            key=f"{key_prefix}_new_etf"
        ).upper().strip()
    
    with col_add2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("추가", key=f"{key_prefix}_add_btn", type="secondary"):
            if new_etf and new_etf not in portfolio:
                portfolio[new_etf] = 0.0
                st.rerun()
    
    # 배분 입력
    allocation = {}
    
    for symbol in list(portfolio.keys()):
        col_weight, col_del = st.columns([4, 1])
        
        with col_weight:
            weight = st.number_input(
                f"{symbol} (%)",
                min_value=0.0,
                max_value=100.0,
                value=portfolio[symbol] * 100,
                step=5.0,
                key=f"{key_prefix}_weight_{symbol}"
            )
            allocation[symbol] = weight / 100
        
        with col_del:
            st.markdown("<br>", unsafe_allow_html=True)
            if st.button("삭제", key=f"{key_prefix}_del_{symbol}", type="secondary"):
                del portfolio[symbol]
                st.rerun()
    
    # 합계 표시
    total = sum(allocation.values())
    if abs(total - 1.0) <= 0.01:
        st.success(f"합계: {total * 100:.1f}%")
    else:
        st.error(f"합계: {total * 100:.1f}% (100% 필요)")
    
    return allocation


def _display_comparison_results(
    backtesters: List[PortfolioBacktester],
    results: List[BacktestResult],
    allocations: List[Dict[str, float]],
    initial_capital: float
):
    """비교 결과 표시 (2~5개 포트폴리오 지원)"""
    
    num_portfolios = len(results)
    
    st.markdown("---")
    st.subheader("비교 결과")
    
    # 포트폴리오 이름 생성
    names = [
        " / ".join([f"{s} {w*100:.0f}%" for s, w in alloc.items()])
        for alloc in allocations
    ]
    
    # 1. 성과 요약 테이블
    st.markdown("### 성과 요약")

    summary_data = {
        "지표": [
            "최종 자산 ($)",
            "총 수익률 (%)",
            "CAGR (%)",
            "변동성 (%)",
            "샤프비율",
            "최대 낙폭 (%)",
            "총 인출금 ($)",
            "총 배당금(세후) ($)",
            "총 세금 ($)",
            "총 세금(배당) ($)",
            "총 세금(양도) ($)",
            "총 거래비용 ($)"
        ]
    }

    # 각 포트폴리오 결과 추가
    for i, result in enumerate(results):
        dividend_tax = sum(
            e.tax_amount for e in result.tax_events
            if e.tax_type == 'dividend'
        )
        capital_gains_tax = sum(
            e.tax_amount for e in result.tax_events
            if e.tax_type == 'capital_gains'
        )

        summary_data[f"포트폴리오 {i+1}"] = [
            int(round(result.final_value)),
            round(result.total_return, 1),
            round(result.cagr, 1),
            round(result.volatility, 1),
            round(result.sharpe_ratio, 2),
            round(result.max_drawdown, 1),
            int(round(result.total_withdrawal)),
            int(round(result.total_dividend_net)),
            int(round(result.total_tax)),
            int(round(dividend_tax)),
            int(round(capital_gains_tax)),
            int(round(result.total_transaction_cost))
        ]

    # 차이 컬럼 추가 (포트폴리오 1 기준)
    result_1 = results[0]
    dividend_tax_1 = sum(e.tax_amount for e in result_1.tax_events if e.tax_type == 'dividend')
    capital_tax_1 = sum(e.tax_amount for e in result_1.tax_events if e.tax_type == 'capital_gains')

    # 포트폴리오 2~5에 대한 비교 컬럼 추가 (루프로 처리)
    for idx in range(1, num_portfolios):
        result_n = results[idx]
        dividend_tax_n = sum(e.tax_amount for e in result_n.tax_events if e.tax_type == 'dividend')
        capital_tax_n = sum(e.tax_amount for e in result_n.tax_events if e.tax_type == 'capital_gains')

        summary_data[f"1 vs {idx+1}"] = [
            int(round(result_1.final_value - result_n.final_value)),
            round(result_1.total_return - result_n.total_return, 1),
            round(result_1.cagr - result_n.cagr, 1),
            round(result_1.volatility - result_n.volatility, 1),
            round(result_1.sharpe_ratio - result_n.sharpe_ratio, 2),
            round(result_1.max_drawdown - result_n.max_drawdown, 1),
            int(round(result_1.total_withdrawal - result_n.total_withdrawal)),
            int(round(result_1.total_dividend_net - result_n.total_dividend_net)),
            int(round(result_1.total_tax - result_n.total_tax)),
            int(round(dividend_tax_1 - dividend_tax_n)),
            int(round(capital_tax_1 - capital_tax_n)),
            int(round(result_1.total_transaction_cost - result_n.total_transaction_cost))
        ]

    summary_df = pd.DataFrame(summary_data)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)
    
    # 포트폴리오 구성 표시
    cols = st.columns(num_portfolios)
    for i, (col, name) in enumerate(zip(cols, names)):
        with col:
            st.caption(f"**포트폴리오 {i+1}:** {name}")
    
    # 히스토리 데이터프레임 생성
    histories = [
        backtester.get_portfolio_history_df(result)
        for backtester, result in zip(backtesters, results)
    ]
    
    # 2. 시계열 성과 추이 그래프
    st.markdown("---")
    st.markdown("### 포트폴리오 가치 추이")
    
    fig = go.Figure()
    
    for i, history in enumerate(histories):
        fig.add_trace(go.Scatter(
            x=history['date'],
            y=history['total_value'],
            mode='lines',
            name=f'포트폴리오 {i+1}',
            line=dict(color=PORTFOLIO_COLORS[i], width=2)
        ))
    
    # 초기 자본 기준선
    fig.add_hline(
        y=initial_capital,
        line_dash="dash",
        line_color="gray",
        annotation_text=f"초기 자본: ${initial_capital:,.0f}"
    )
    
    fig.update_layout(
        title="포트폴리오 가치 비교",
        xaxis_title="날짜",
        yaxis_title="금액 (USD)",
        height=450,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 3. 수익률 차이 추이
    st.markdown("### 누적 수익률 비교")
    
    fig2 = go.Figure()
    
    for i, history in enumerate(histories):
        returns = (history['total_value'] / initial_capital - 1) * 100
        fig2.add_trace(go.Scatter(
            x=history['date'],
            y=returns,
            mode='lines',
            name=f'포트폴리오 {i+1}',
            line=dict(color=PORTFOLIO_COLORS[i], width=2)
        ))
    
    fig2.add_hline(y=0, line_dash="dash", line_color="gray")
    
    fig2.update_layout(
        title="누적 수익률 비교",
        xaxis_title="날짜",
        yaxis_title="수익률 (%)",
        height=400,
        hovermode='x unified',
        legend=dict(
            orientation="h",
            yanchor="bottom",
            y=1.02,
            xanchor="right",
            x=1
        )
    )
    
    st.plotly_chart(fig2, use_container_width=True)
    
    # 4. 연간 성과 비교
    st.markdown("### 연간 성과 비교")
    
    annual_summaries = [
        backtester.get_annual_summary_df(result)
        for backtester, result in zip(backtesters, results)
    ]
    
    # 모든 연간 데이터가 있는지 확인
    if all(not annual.empty for annual in annual_summaries):
        fig3 = go.Figure()
        
        for i, annual in enumerate(annual_summaries):
            fig3.add_trace(go.Bar(
                x=annual['year'],
                y=annual['return_pct'],
                name=f'포트폴리오 {i+1}',
                marker_color=PORTFOLIO_COLORS[i]
            ))
        
        fig3.update_layout(
            title="연간 수익률 비교",
            xaxis_title="연도",
            yaxis_title="수익률 (%)",
            height=400,
            barmode='group',
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        st.plotly_chart(fig3, use_container_width=True)
