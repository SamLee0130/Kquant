"""
자산 배분 백테스트 페이지

ETF 포트폴리오의 자산 배분 전략을 백테스팅합니다.
리밸런싱, 인출, 배당금, 세금을 고려한 시뮬레이션을 제공합니다.
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from datetime import datetime, timedelta
import logging

from src.backtest.portfolio_backtest import PortfolioBacktester, BacktestResult
from config.settings import ETF_BACKTEST_DEFAULTS

logger = logging.getLogger(__name__)


def show_allocation_backtest_page():
    """자산 배분 백테스트 페이지 표시"""
    st.header("자산 배분 백테스트")
    st.markdown("ETF 포트폴리오의 자산 배분 전략을 백테스팅합니다.")
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        st.subheader("백테스트 설정")
        
        # 초기 자본
        initial_capital = st.number_input(
            "초기 자본 (USD)",
            min_value=10_000,
            max_value=100_000_000,
            value=ETF_BACKTEST_DEFAULTS['initial_capital'],
            step=100_000,
            format="%d",
            help="백테스트 시작 시 투자할 초기 자본금"
        )
        
        # 백테스팅 기간
        backtest_years = st.number_input(
            "백테스팅 기간 (년)",
            min_value=1,
            max_value=30,
            value=ETF_BACKTEST_DEFAULTS['backtest_years'],
            step=1,
            help="최근 N년 동안의 백테스트 수행"
        )
        
        # 리밸런싱 주기
        rebalance_freq = st.selectbox(
            "리밸런싱 주기",
            options=['quarterly', 'yearly'],
            index=0 if ETF_BACKTEST_DEFAULTS['rebalance_frequency'] == 'quarterly' else 1,
            format_func=lambda x: '분기별' if x == 'quarterly' else '연간',
            help="포트폴리오 리밸런싱 주기"
        )
        
        # 연간 인출률
        withdrawal_rate = st.number_input(
            "연간 인출률 (%)",
            min_value=0.0,
            max_value=20.0,
            value=ETF_BACKTEST_DEFAULTS['withdrawal_rate'] * 100,
            step=0.5,
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
            help="배당금에 부과되는 세율"
        ) / 100
        
        # 양도소득세
        capital_gains_tax_rate = st.number_input(
            "양도소득세 (%)",
            min_value=0.0,
            max_value=50.0,
            value=ETF_BACKTEST_DEFAULTS['capital_gains_tax_rate'] * 100,
            step=1.0,
            help="양도차익에 부과되는 세율 (연말 정산, 다음해 차감)"
        ) / 100
        
        st.markdown("---")
        st.subheader("거래비용 설정")
        
        # 거래비용 (수수료 + 슬리피지)
        transaction_cost_rate = st.number_input(
            "거래비용 (%)",
            min_value=0.0,
            max_value=2.0,
            value=ETF_BACKTEST_DEFAULTS['transaction_cost_rate'] * 100,
            step=0.05,
            help="거래수수료 + 슬리피지 (거래금액의 %)"
        ) / 100
    
    # 메인 영역 - 자산 배분 설정
    st.subheader("자산 배분 설정")
    
    # 세션 상태 초기화
    if 'etf_allocation' not in st.session_state:
        st.session_state.etf_allocation = dict(ETF_BACKTEST_DEFAULTS['default_allocation'])
    
    # ETF 추가/삭제 UI
    col1, col2 = st.columns([3, 1])
    
    with col1:
        new_etf = st.text_input(
            "ETF 추가",
            placeholder="예: VOO, IWM, TLT",
            key="new_etf_input"
        ).upper().strip()
    
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("추가", type="secondary"):
            if new_etf and new_etf not in st.session_state.etf_allocation:
                st.session_state.etf_allocation[new_etf] = 0.0
                st.rerun()
            elif new_etf in st.session_state.etf_allocation:
                st.warning(f"{new_etf}는 이미 추가되어 있습니다.")
    
    # 현재 배분 표시 및 수정
    st.markdown("**현재 자산 배분**")
    
    allocation = {}
    cols = st.columns(len(st.session_state.etf_allocation) + 1)
    
    for i, (symbol, weight) in enumerate(st.session_state.etf_allocation.items()):
        with cols[i]:
            new_weight = st.number_input(
                f"{symbol}",
                min_value=0.0,
                max_value=100.0,
                value=weight * 100,
                step=5.0,
                key=f"weight_{symbol}",
                help=f"{symbol} 비중 (%)"
            )
            allocation[symbol] = new_weight / 100
            
            if st.button("삭제", key=f"del_{symbol}", type="secondary"):
                del st.session_state.etf_allocation[symbol]
                st.rerun()
    
    # 비중 합계 검증
    total_weight = sum(allocation.values())
    
    with cols[-1]:
        st.metric("합계", f"{total_weight * 100:.1f}%")
        if abs(total_weight - 1.0) > 0.01:
            st.error("100%")
        else:
            st.success("OK")
    
    # 비중 합계 경고
    if abs(total_weight - 1.0) > 0.01:
        st.warning(f"자산 배분 비중의 합계가 100%가 아닙니다. 현재: {total_weight * 100:.1f}%")
    
    st.markdown("---")
    
    # 백테스트 실행 버튼
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        run_backtest = st.button(
            "백테스트 실행",
            type="primary",
            use_container_width=True,
            disabled=abs(total_weight - 1.0) > 0.01
        )
    
    if run_backtest:
        if abs(total_weight - 1.0) > 0.01:
            st.error("자산 배분 비중의 합계가 100%여야 합니다.")
            return
        
        # 세션 상태에 배분 저장
        st.session_state.etf_allocation = allocation
        
        with st.spinner("백테스트 실행 중... (데이터 수집 및 시뮬레이션)"):
            try:
                # 백테스터 생성 및 실행
                backtester = PortfolioBacktester(
                    initial_capital=initial_capital,
                    allocation=allocation,
                    rebalance_frequency=rebalance_freq,
                    withdrawal_rate=withdrawal_rate,
                    dividend_tax_rate=dividend_tax_rate,
                    capital_gains_tax_rate=capital_gains_tax_rate,
                    transaction_cost_rate=transaction_cost_rate
                )
                
                result = backtester.run(years=backtest_years)
                
                # 결과 저장
                st.session_state.backtest_result = result
                st.session_state.backtester = backtester
                
                st.success("백테스트 완료!")
                
            except Exception as e:
                st.error(f"백테스트 실행 중 오류 발생: {str(e)}")
                logger.error(f"백테스트 오류: {str(e)}")
                return
    
    # 결과 표시
    if 'backtest_result' in st.session_state:
        display_backtest_results(
            st.session_state.backtest_result,
            st.session_state.backtester
        )


def display_backtest_results(result: BacktestResult, backtester: PortfolioBacktester):
    """백테스트 결과 표시"""
    
    st.markdown("---")
    st.subheader("백테스트 결과")

    # 분석 기간 표시
    if result.portfolio_history:
        start_date = result.portfolio_history[0].date.strftime('%Y-%m-%d')
        end_date = result.portfolio_history[-1].date.strftime('%Y-%m-%d')
        st.markdown(f"**분석 기간**: {start_date} ~ {end_date}")

    # 1. 주요 성과 지표
    st.markdown("**주요 성과 지표**")
    
    # 1행: 최종 자산, 총 인출금, 총 배당금(세후)
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        st.metric(
            "최종 자산",
            f"${result.final_value:,.0f}",
            delta=f"{result.total_return:+.1f}%"
        )
    with row1_col2:
        st.metric(
            "총 인출금",
            f"${result.total_withdrawal:,.0f}",
            help="백테스트 기간 동안 인출한 총 금액"
        )
    with row1_col3:
        st.metric(
            "총 배당금",
            f"${result.total_dividend_net:,.0f}",
            help="수령한 총 배당금 (세후)"
        )
    
    # 세금 분리 집계
    dividend_tax = sum(
        e.tax_amount for e in result.tax_events
        if e.tax_type == 'dividend'
    )
    capital_gains_tax = sum(
        e.tax_amount for e in result.tax_events
        if e.tax_type == 'capital_gains'
    )

    # 2행: 총 세금, 총 세금(배당), 총 세금(양도), 총 거래비용
    row2_col1, row2_col2, row2_col3, row2_col4 = st.columns(4)
    with row2_col1:
        st.metric(
            "총 세금",
            f"${result.total_tax:,.0f}",
            help="배당소득세 + 양도소득세"
        )
    with row2_col2:
        st.metric(
            "총 세금(배당)",
            f"${dividend_tax:,.0f}",
            help="배당소득세 합계"
        )
    with row2_col3:
        st.metric(
            "총 세금(양도)",
            f"${capital_gains_tax:,.0f}",
            help="양도소득세 합계"
        )
    with row2_col4:
        st.metric(
            "총 거래비용",
            f"${result.total_transaction_cost:,.0f}",
            help="거래수수료 + 슬리피지"
        )
    
    # 3행: CAGR, 변동성, 샤프비율, 최대 낙폭
    row3_col1, row3_col2, row3_col3, row3_col4 = st.columns(4)
    with row3_col1:
        st.metric(
            "CAGR",
            f"{result.cagr:.2f}%",
            help="연평균 복리 수익률"
        )
    with row3_col2:
        st.metric(
            "변동성",
            f"{result.volatility:.2f}%",
            help="연율화된 표준편차"
        )
    with row3_col3:
        st.metric(
            "샤프비율",
            f"{result.sharpe_ratio:.2f}",
            help="위험 대비 수익률 (무위험수익률 3% 가정)"
        )
    with row3_col4:
        st.metric(
            "최대 낙폭",
            f"{result.max_drawdown:.1f}%",
            help="최고점 대비 최대 하락폭"
        )
    
    st.markdown("---")
    
    # 2. 포트폴리오 가치 추이 차트
    st.subheader("포트폴리오 가치 추이")
    
    history_df = backtester.get_portfolio_history_df(result)
    
    fig = go.Figure()
    
    # 포트폴리오 총 가치
    fig.add_trace(go.Scatter(
        x=history_df['date'],
        y=history_df['total_value'],
        mode='lines',
        name='포트폴리오 가치',
        line=dict(color='#1f77b4', width=2)
    ))
    
    # 누적 인출금
    fig.add_trace(go.Scatter(
        x=history_df['date'],
        y=history_df['cumulative_withdrawal'],
        mode='lines',
        name='누적 인출금',
        line=dict(color='#2ca02c', width=2, dash='dash')
    ))
    
    # 초기 자본 기준선
    fig.add_hline(
        y=result.initial_value,
        line_dash="dot",
        line_color="gray",
        annotation_text=f"초기 자본: ${result.initial_value:,.0f}"
    )
    
    fig.update_layout(
        title="포트폴리오 가치 및 누적 인출금",
        xaxis_title="날짜",
        yaxis_title="금액 (USD)",
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
    
    st.plotly_chart(fig, use_container_width=True)
    
    # 3. 자산별 비중 변화 (Stacked Area)
    st.subheader("자산별 비중 변화")
    
    # 자산별 가치 컬럼 찾기 (total 제외)
    value_cols = [col for col in history_df.columns if col.endswith('_value') and col != 'total_value']
    symbols = [col.replace('_value', '') for col in value_cols]
    
    if value_cols:
        fig2 = go.Figure()
        
        colors = px.colors.qualitative.Set2
        
        for i, (symbol, col) in enumerate(zip(symbols, value_cols)):
            fig2.add_trace(go.Scatter(
                x=history_df['date'],
                y=history_df[col],
                mode='lines',
                name=symbol,
                stackgroup='one',
                line=dict(width=0),
                fillcolor=colors[i % len(colors)]
            ))
        
        fig2.update_layout(
            title="자산별 가치 변화",
            xaxis_title="날짜",
            yaxis_title="금액 (USD)",
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
    
    # 4. 연간 요약 테이블
    st.subheader("연간 성과 요약")
    
    annual_df = backtester.get_annual_summary_df(result)
    
    if not annual_df.empty:
        # 포맷팅: 숫자값 유지, 소수점 처리
        display_df = annual_df.copy()
        display_df['year'] = display_df['year'].astype(int)
        display_df['return_pct'] = display_df['return_pct'].round(1)

        # 달러 컬럼들은 정수로 반올림
        dollar_columns = ['start_value', 'start_value_after_capital_tax', 'end_value',
                          'withdrawal', 'dividend_gross', 'dividend_net',
                          'tax_dividend', 'tax_capital_gains', 'transaction_cost']
        for col in dollar_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(0).astype(int)

        display_df.columns = [
            '연도', '시작 가치 ($)', '시작 가치(양도세 차감 후) ($)', '종료 가치 ($)', '수익률 (%)',
            '인출금 ($)', '배당금(세전) ($)', '배당금(세후) ($)', '세금(배당) ($)', '세금(양도 차익) ($)', '거래비용 ($)'
        ]

        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    # 5. 인출금 vs 배당금 비교
    st.subheader("인출금 vs 배당금")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if result.withdrawal_events:
            withdrawal_df = pd.DataFrame(result.withdrawal_events)
            
            fig3 = go.Figure()
            fig3.add_trace(go.Bar(
                x=withdrawal_df['date'],
                y=withdrawal_df['from_dividend'],
                name='배당금에서',
                marker_color='#2ca02c'
            ))
            fig3.add_trace(go.Bar(
                x=withdrawal_df['date'],
                y=withdrawal_df['from_portfolio'],
                name='포트폴리오에서',
                marker_color='#d62728'
            ))
            
            fig3.update_layout(
                title="인출금 구성",
                xaxis_title="날짜",
                yaxis_title="금액 (USD)",
                barmode='stack',
                height=350
            )
            
            st.plotly_chart(fig3, use_container_width=True)
    
    with col2:
        if result.dividend_events:
            div_df = pd.DataFrame(result.dividend_events)
            div_monthly = div_df.groupby(div_df['date'].dt.to_period('M')).agg({
                'gross_dividend': 'sum',
                'net_dividend': 'sum',
                'tax': 'sum'
            }).reset_index()
            div_monthly['date'] = div_monthly['date'].dt.to_timestamp()
            
            fig4 = go.Figure()
            fig4.add_trace(go.Bar(
                x=div_monthly['date'],
                y=div_monthly['net_dividend'],
                name='순 배당금',
                marker_color='#2ca02c'
            ))
            fig4.add_trace(go.Bar(
                x=div_monthly['date'],
                y=div_monthly['tax'],
                name='배당소득세',
                marker_color='#ff7f0e'
            ))
            
            fig4.update_layout(
                title="월별 배당금 및 세금",
                xaxis_title="날짜",
                yaxis_title="금액 (USD)",
                barmode='stack',
                height=350
            )
            
            st.plotly_chart(fig4, use_container_width=True)
    
    # 6. 세금 요약
    st.subheader("세금 요약")
    
    col1, col2, col3 = st.columns(3)
    
    dividend_tax = sum(
        e.tax_amount for e in result.tax_events 
        if e.tax_type == 'dividend'
    )
    capital_gains_tax = sum(
        e.tax_amount for e in result.tax_events 
        if e.tax_type == 'capital_gains'
    )
    
    with col1:
        st.metric("배당소득세 합계", f"${dividend_tax:,.0f}")
    
    with col2:
        st.metric("양도소득세 합계", f"${capital_gains_tax:,.0f}")
    
    with col3:
        st.metric("총 세금", f"${result.total_tax:,.0f}")
    
    # 세금 비율 파이 차트
    if result.total_tax > 0:
        fig5 = go.Figure(data=[go.Pie(
            labels=['배당소득세', '양도소득세'],
            values=[dividend_tax, capital_gains_tax],
            hole=.4,
            marker_colors=['#ff7f0e', '#d62728']
        )])
        
        fig5.update_layout(
            title="세금 구성",
            height=300
        )
        
        st.plotly_chart(fig5, use_container_width=True)
    
    # 7. 상세 로그 (펼쳐보기)
    with st.expander("상세 리밸런싱 로그"):
        if result.rebalance_events:
            for event in result.rebalance_events[:10]:  # 최근 10개만
                st.markdown(f"**{event['date'].strftime('%Y-%m-%d')}** - 포트폴리오 가치: ${event['portfolio_value']:,.0f}")
                if event['trades']:
                    for trade in event['trades']:
                        action = "매수" if trade['shares'] > 0 else "매도"
                        st.markdown(
                            f"  - {trade['symbol']}: {action} {abs(trade['shares']):.2f}주 "
                            f"@ ${trade['price']:.2f} = ${abs(trade['value']):,.0f}"
                        )
                st.markdown("---")
    
    with st.expander("상세 배당금 로그"):
        if result.dividend_events:
            div_summary = pd.DataFrame(result.dividend_events)
            div_summary['date'] = div_summary['date'].dt.strftime('%Y-%m-%d')
            div_summary = div_summary.round(2)
            # 전체 기간 배당 로그 표시 (최근 20개 제한 제거)
            st.dataframe(div_summary, use_container_width=True, hide_index=True)

