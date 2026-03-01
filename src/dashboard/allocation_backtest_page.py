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
from src.backtest.backtest_utils import summarize_tax_events
from src.dashboard.sidebar_utils import render_common_sidebar
from src.data.etf_classifier import (
    classify_portfolio, normalize_ticker, is_korean_ticker,
    has_mixed_currencies, get_tax_label
)
from src.data.fx_fetcher import CurrencyConverter
from config.settings import ETF_BACKTEST_DEFAULTS, KOREAN_ETF_PRESETS

logger = logging.getLogger(__name__)


def _has_korean_etfs(allocation: dict) -> bool:
    """포트폴리오에 한국 ETF가 포함되어 있는지 확인"""
    return any(is_korean_ticker(symbol) for symbol in allocation)


def _currency_symbol(allocation: dict) -> str:
    """포트폴리오 기반 통화 기호 반환"""
    return "₩" if _has_korean_etfs(allocation) else "$"


def _currency_label(allocation: dict) -> str:
    """포트폴리오 기반 통화 레이블 반환"""
    return "KRW" if _has_korean_etfs(allocation) else "USD"


def calculate_dividend_yield(price_data: dict, dividend_data: dict, symbols: list) -> pd.DataFrame:
    """
    연간 배당수익률 계산

    배당수익률 = (연간 배당금 합계) / (연말 주가) × 100

    Args:
        price_data: {symbol: DataFrame with 'price' column}
        dividend_data: {symbol: Series of dividends}
        symbols: list of ETF symbols

    Returns:
        DataFrame with annual dividend yields per symbol
    """
    if not price_data or not symbols:
        return pd.DataFrame()

    # 모든 데이터에서 연도 범위 추출
    all_years = set()
    for symbol in symbols:
        if symbol in price_data:
            years = price_data[symbol].index.year.unique()
            all_years.update(years)

    years = sorted(all_years)
    yield_data = []

    for year in years:
        row = {'연도': year}

        for symbol in symbols:
            year_end_price = None
            total_div = 0.0

            # 연말 주가 (해당 연도 마지막 거래일)
            if symbol in price_data:
                price_df = price_data[symbol]
                year_prices = price_df[price_df.index.year == year]
                if len(year_prices) > 0:
                    year_end_price = year_prices['price'].iloc[-1]

            # 연간 배당금 합계
            if symbol in dividend_data:
                div_series = dividend_data[symbol]
                if len(div_series) > 0:
                    year_divs = div_series[div_series.index.year == year]
                    total_div = year_divs.sum() if len(year_divs) > 0 else 0.0

            # 배당수익률 계산
            if year_end_price and year_end_price > 0:
                div_yield = (total_div / year_end_price) * 100
            else:
                div_yield = 0.0

            row[f'{symbol} (%)'] = round(div_yield, 2)

        yield_data.append(row)

    return pd.DataFrame(yield_data)


def _etf_currency_label(symbol: str) -> str:
    """개별 ETF의 native currency 레이블 반환"""
    return "KRW" if is_korean_ticker(symbol) else "USD"


def display_etf_performance(backtester: 'PortfolioBacktester'):
    """
    구성 종목별 성과 표시 (주가 차트 + 배당금 차트 + 배당수익률 테이블)

    Args:
        backtester: PortfolioBacktester instance with _price_data and _dividend_data
    """
    symbols = list(backtester.allocation.keys())
    price_data = backtester._price_data
    dividend_data = backtester._dividend_data

    if not price_data or not symbols:
        st.warning("종목별 성과 데이터를 표시할 수 없습니다.")
        return

    colors = px.colors.qualitative.Set2

    # 탭으로 종목별 차트 표시
    tabs = st.tabs(symbols)

    for i, (tab, symbol) in enumerate(zip(tabs, symbols)):
        with tab:
            # 주가 + 배당금 서브플롯 차트
            fig = make_subplots(
                rows=2, cols=1,
                shared_xaxes=True,
                vertical_spacing=0.08,
                row_heights=[0.7, 0.3],
                subplot_titles=(f'{symbol} 주가', f'{symbol} 배당금')
            )

            # Row 1: 주가 line chart
            if symbol in price_data:
                df = price_data[symbol]
                fig.add_trace(go.Scatter(
                    x=df.index,
                    y=df['price'],
                    name='주가',
                    mode='lines',
                    line=dict(color=colors[i % len(colors)], width=2)
                ), row=1, col=1)

            # Row 2: 배당금 bar chart
            if symbol in dividend_data:
                div_series = dividend_data[symbol]
                if len(div_series) > 0:
                    fig.add_trace(go.Bar(
                        x=div_series.index,
                        y=div_series.values,
                        name='배당금',
                        marker_color=colors[i % len(colors)],
                        opacity=0.7
                    ), row=2, col=1)

            fig.update_layout(
                height=500,
                hovermode='x unified',
                showlegend=False
            )

            etf_lbl = _etf_currency_label(symbol)
            fig.update_yaxes(title_text=f"주가 ({etf_lbl})", row=1, col=1)
            fig.update_yaxes(title_text=f"배당금 ({etf_lbl})", row=2, col=1)
            fig.update_xaxes(title_text="날짜", row=2, col=1)

            st.plotly_chart(fig, use_container_width=True)

    # 2. 연간 배당수익률 테이블
    st.markdown("**연간 배당수익률**")
    st.caption("배당수익률 = (연간 배당금 합계) / (연말 주가) × 100")

    yield_df = calculate_dividend_yield(price_data, dividend_data, symbols)

    if not yield_df.empty:
        yield_df['연도'] = yield_df['연도'].astype(int)
        st.dataframe(yield_df, use_container_width=True, hide_index=True)
    else:
        st.info("배당수익률 데이터가 없습니다.")


def show_allocation_backtest_page():
    """자산 배분 백테스트 페이지 표시"""
    st.header("자산 배분 백테스트")
    st.markdown("ETF 포트폴리오의 자산 배분 전략을 백테스팅합니다.")
    st.markdown("---")
    
    # 사이드바 설정
    with st.sidebar:
        settings = render_common_sidebar()

    # 설정값 추출
    initial_capital = settings.initial_capital
    backtest_years = settings.backtest_years
    rebalance_freq = settings.rebalance_freq
    withdrawal_rate = settings.withdrawal_rate
    dividend_tax_rate = settings.dividend_tax_rate
    capital_gains_tax_rate = settings.capital_gains_tax_rate
    transaction_cost_rate = settings.transaction_cost_rate
    
    # 메인 영역 - 자산 배분 설정
    st.subheader("자산 배분 설정")

    # 세션 상태 초기화
    if 'etf_allocation' not in st.session_state:
        st.session_state.etf_allocation = dict(ETF_BACKTEST_DEFAULTS['default_allocation'])

    # 프리셋 선택 (한국 ETF 프리셋 포함)
    all_presets = {"직접 입력": {}}
    all_presets["US 기본 (SPY/QQQ/BIL)"] = ETF_BACKTEST_DEFAULTS['default_allocation']
    all_presets.update(KOREAN_ETF_PRESETS)

    preset_choice = st.selectbox(
        "프리셋 포트폴리오",
        options=list(all_presets.keys()),
        index=0,
        help="미리 정의된 포트폴리오 구성 선택"
    )

    if preset_choice != "직접 입력" and st.button("프리셋 적용", type="secondary"):
        st.session_state.etf_allocation = dict(all_presets[preset_choice])
        st.rerun()

    # ETF 추가/삭제 UI
    col1, col2 = st.columns([3, 1])

    with col1:
        new_etf = st.text_input(
            "ETF 추가",
            placeholder="예: VOO, IWM, TLT, 069500 (KODEX 200)",
            key="new_etf_input"
        ).strip()

    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("추가", type="secondary"):
            if new_etf:
                normalized = normalize_ticker(new_etf)
                if normalized not in st.session_state.etf_allocation:
                    st.session_state.etf_allocation[normalized] = 0.0
                    st.rerun()
                else:
                    st.warning(f"{normalized}는 이미 추가되어 있습니다.")
    
    # 현재 배분 표시 및 수정
    st.markdown("**현재 자산 배분**")

    # 한국 ETF 정보 표시
    etf_info = classify_portfolio(st.session_state.etf_allocation)
    has_kr = _has_korean_etfs(st.session_state.etf_allocation)

    if has_kr:
        kr_labels = []
        for symbol, info in etf_info.items():
            if is_korean_ticker(symbol):
                tax_label = get_tax_label(info.market)
                kr_labels.append(f"{symbol} ({info.display_name}) - {tax_label}")
        if kr_labels:
            st.info("국내 ETF: " + " | ".join(kr_labels))

    allocation = {}
    cols = st.columns(len(st.session_state.etf_allocation) + 1)

    for i, (symbol, weight) in enumerate(st.session_state.etf_allocation.items()):
        with cols[i]:
            label = symbol
            if symbol in etf_info and is_korean_ticker(symbol):
                label = f"{symbol}\n({etf_info[symbol].display_name})"
            new_weight = st.number_input(
                label,
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
                # ETF 분류 및 환율 변환기 생성
                portfolio_etf_info = classify_portfolio(allocation)
                converter = None
                if has_mixed_currencies(portfolio_etf_info):
                    converter = CurrencyConverter(base_currency="KRW")

                # 백테스터 생성 및 실행
                backtester = PortfolioBacktester(
                    initial_capital=initial_capital,
                    allocation=allocation,
                    rebalance_frequency=rebalance_freq,
                    withdrawal_rate=withdrawal_rate,
                    dividend_tax_rate=dividend_tax_rate,
                    capital_gains_tax_rate=capital_gains_tax_rate,
                    transaction_cost_rate=transaction_cost_rate,
                    etf_info=portfolio_etf_info,
                    currency_converter=converter,
                    kr_dividend_tax_rate=settings.kr_dividend_tax_rate,
                    kr_capital_gains_rate=settings.kr_capital_gains_rate
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


def _render_performance_metrics(result: BacktestResult, allocation: dict):
    """주요 성과 지표 렌더링 (분석 기간 + 3행 메트릭)"""

    sym = _currency_symbol(allocation)

    # 분석 기간 표시
    if result.portfolio_history:
        start_date = result.portfolio_history[0].date.strftime('%Y-%m-%d')
        end_date = result.portfolio_history[-1].date.strftime('%Y-%m-%d')
        st.markdown(f"**분석 기간**: {start_date} ~ {end_date}")

    st.markdown("**주요 성과 지표**")

    # 1행: 최종 자산, 총 인출금, 총 배당금(세후)
    row1_col1, row1_col2, row1_col3 = st.columns(3)
    with row1_col1:
        st.metric(
            "최종 자산",
            f"{sym}{result.final_value:,.0f}",
            delta=f"{result.total_return:+.1f}%"
        )
    with row1_col2:
        st.metric(
            "총 인출금",
            f"{sym}{result.total_withdrawal:,.0f}",
            help="백테스트 기간 동안 인출한 총 금액"
        )
    with row1_col3:
        st.metric(
            "총 배당금",
            f"{sym}{result.total_dividend_net:,.0f}",
            help="수령한 총 배당금 (세후)"
        )

    # 세금 분리 집계
    tax_summary = summarize_tax_events(result.tax_events)
    dividend_tax = tax_summary['dividend_tax']
    capital_gains_tax = tax_summary['capital_gains_tax']
    kr_capital_gains_tax = tax_summary['kr_capital_gains_tax']

    # 2행: 총 세금, 배당세, 양도소득세, 거래비용 (+ KR 즉시과세)
    has_kr_tax = kr_capital_gains_tax > 0
    num_tax_cols = 5 if has_kr_tax else 4
    row2_cols = st.columns(num_tax_cols)

    with row2_cols[0]:
        st.metric(
            "총 세금",
            f"{sym}{result.total_tax:,.0f}",
            help="배당소득세 + 양도소득세 + 국내 기타 ETF 매매차익세"
        )
    with row2_cols[1]:
        st.metric(
            "총 세금(배당)",
            f"{sym}{dividend_tax:,.0f}",
            help="배당소득세 합계"
        )
    with row2_cols[2]:
        st.metric(
            "총 세금(양도)",
            f"{sym}{capital_gains_tax:,.0f}",
            help="해외 ETF 양도소득세 합계"
        )
    if has_kr_tax:
        with row2_cols[3]:
            st.metric(
                "총 세금(국내 매매)",
                f"{sym}{kr_capital_gains_tax:,.0f}",
                help="국내 기타 ETF 매매차익 배당소득세 합계"
            )
    with row2_cols[-1]:
        st.metric(
            "총 거래비용",
            f"{sym}{result.total_transaction_cost:,.0f}",
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


def _render_portfolio_chart(history_df: pd.DataFrame, result: BacktestResult, allocation: dict):
    """포트폴리오 가치 추이 차트 렌더링"""

    sym = _currency_symbol(allocation)
    lbl = _currency_label(allocation)

    st.subheader("포트폴리오 가치 추이")

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
        annotation_text=f"초기 자본: {sym}{result.initial_value:,.0f}"
    )

    fig.update_layout(
        title="포트폴리오 가치 및 누적 인출금",
        xaxis_title="날짜",
        yaxis_title=f"금액 ({lbl})",
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


def _render_allocation_chart(history_df: pd.DataFrame, allocation: dict):
    """자산별 비중 변화 (Stacked Area) 차트 렌더링"""

    lbl = _currency_label(allocation)

    st.subheader("자산별 비중 변화")

    # 자산별 가치 컬럼 찾기 (total 제외)
    value_cols = [col for col in history_df.columns if col.endswith('_value') and col != 'total_value']
    symbols = [col.replace('_value', '') for col in value_cols]

    if value_cols:
        fig = go.Figure()

        colors = px.colors.qualitative.Set2

        for i, (symbol, col) in enumerate(zip(symbols, value_cols)):
            fig.add_trace(go.Scatter(
                x=history_df['date'],
                y=history_df[col],
                mode='lines',
                name=symbol,
                stackgroup='one',
                line=dict(width=0),
                fillcolor=colors[i % len(colors)]
            ))

        fig.update_layout(
            title="자산별 가치 변화",
            xaxis_title="날짜",
            yaxis_title=f"금액 ({lbl})",
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


def _render_annual_summary(annual_df: pd.DataFrame, allocation: dict):
    """연간 성과 요약 테이블 렌더링"""

    sym = _currency_symbol(allocation)

    st.subheader("연간 성과 요약")

    if not annual_df.empty:
        # 포맷팅: 숫자값 유지, 소수점 처리
        display_df = annual_df.copy()
        display_df['year'] = display_df['year'].astype(int)
        display_df['return_pct'] = display_df['return_pct'].round(1)

        # 금액 컬럼들은 정수로 반올림
        money_columns = ['start_value', 'start_value_after_capital_tax', 'end_value',
                          'withdrawal', 'dividend_gross', 'dividend_net',
                          'tax_dividend', 'tax_capital_gains', 'tax_kr_capital_gains',
                          'transaction_cost']
        for col in money_columns:
            if col in display_df.columns:
                display_df[col] = display_df[col].round(0).astype(int)

        # KR 매매차익세 컬럼이 모두 0이면 제거
        has_kr_tax = 'tax_kr_capital_gains' in display_df.columns and display_df['tax_kr_capital_gains'].sum() > 0

        column_rename = {
            'year': '연도',
            'start_value': f'시작 가치 ({sym})',
            'start_value_after_capital_tax': f'시작 가치(양도세 차감 후) ({sym})',
            'end_value': f'종료 가치 ({sym})',
            'return_pct': '수익률 (%)',
            'withdrawal': f'인출금 ({sym})',
            'dividend_gross': f'배당금(세전) ({sym})',
            'dividend_net': f'배당금(세후) ({sym})',
            'tax_dividend': f'세금(배당) ({sym})',
            'tax_capital_gains': f'세금(양도 차익) ({sym})',
            'tax_kr_capital_gains': f'세금(국내 매매) ({sym})',
            'transaction_cost': f'거래비용 ({sym})'
        }

        if not has_kr_tax and 'tax_kr_capital_gains' in display_df.columns:
            display_df = display_df.drop(columns=['tax_kr_capital_gains'])

        display_df = display_df.rename(columns=column_rename)

        st.dataframe(display_df, use_container_width=True, hide_index=True)


def _render_withdrawal_dividend(result: BacktestResult, allocation: dict):
    """인출금 vs 배당금 비교 차트 렌더링"""

    lbl = _currency_label(allocation)

    st.subheader("인출금 vs 배당금")

    col1, col2 = st.columns(2)

    with col1:
        if result.withdrawal_events:
            withdrawal_df = pd.DataFrame(result.withdrawal_events)

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=withdrawal_df['date'],
                y=withdrawal_df['from_dividend'],
                name='배당금에서',
                marker_color='#2ca02c'
            ))
            fig.add_trace(go.Bar(
                x=withdrawal_df['date'],
                y=withdrawal_df['from_portfolio'],
                name='포트폴리오에서',
                marker_color='#d62728'
            ))

            fig.update_layout(
                title="인출금 구성",
                xaxis_title="날짜",
                yaxis_title=f"금액 ({lbl})",
                barmode='stack',
                height=350
            )

            st.plotly_chart(fig, use_container_width=True)

    with col2:
        if result.dividend_events:
            div_df = pd.DataFrame(result.dividend_events)
            div_monthly = div_df.groupby(div_df['date'].dt.to_period('M')).agg({
                'gross_dividend': 'sum',
                'net_dividend': 'sum',
                'tax': 'sum'
            }).reset_index()
            div_monthly['date'] = div_monthly['date'].dt.to_timestamp()

            fig = go.Figure()
            fig.add_trace(go.Bar(
                x=div_monthly['date'],
                y=div_monthly['net_dividend'],
                name='순 배당금',
                marker_color='#2ca02c'
            ))
            fig.add_trace(go.Bar(
                x=div_monthly['date'],
                y=div_monthly['tax'],
                name='배당소득세',
                marker_color='#ff7f0e'
            ))

            fig.update_layout(
                title="월별 배당금 및 세금",
                xaxis_title="날짜",
                yaxis_title=f"금액 ({lbl})",
                barmode='stack',
                height=350
            )

            st.plotly_chart(fig, use_container_width=True)


def _render_tax_summary(result: BacktestResult, allocation: dict):
    """세금 요약 및 파이 차트 렌더링"""

    sym = _currency_symbol(allocation)

    st.subheader("세금 요약")

    tax_summary = summarize_tax_events(result.tax_events)
    dividend_tax = tax_summary['dividend_tax']
    capital_gains_tax = tax_summary['capital_gains_tax']
    kr_capital_gains_tax = tax_summary['kr_capital_gains_tax']
    has_kr_tax = kr_capital_gains_tax > 0

    num_cols = 4 if has_kr_tax else 3
    cols = st.columns(num_cols)

    with cols[0]:
        st.metric("배당소득세 합계", f"{sym}{dividend_tax:,.0f}")

    with cols[1]:
        st.metric("양도소득세 합계", f"{sym}{capital_gains_tax:,.0f}")

    if has_kr_tax:
        with cols[2]:
            st.metric("국내 매매차익세 합계", f"{sym}{kr_capital_gains_tax:,.0f}")

    with cols[-1]:
        st.metric("총 세금", f"{sym}{result.total_tax:,.0f}")

    # 세금 비율 파이 차트
    if result.total_tax > 0:
        labels = ['배당소득세', '양도소득세']
        values = [dividend_tax, capital_gains_tax]
        colors = ['#ff7f0e', '#d62728']

        if has_kr_tax:
            labels.append('국내 매매차익세')
            values.append(kr_capital_gains_tax)
            colors.append('#9467bd')

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.4,
            marker_colors=colors
        )])

        fig.update_layout(
            title="세금 구성",
            height=300
        )

        st.plotly_chart(fig, use_container_width=True)


def _render_detail_logs(result: BacktestResult, allocation: dict):
    """상세 리밸런싱/배당금 로그 렌더링"""

    sym = _currency_symbol(allocation)

    with st.expander("상세 리밸런싱 로그"):
        if result.rebalance_events:
            withdrawal_by_date = {e['date']: e for e in result.withdrawal_events} if result.withdrawal_events else {}
            for event in result.rebalance_events[-10:]:  # 최근 10개만
                # 초기 매수와 리밸런싱 구분
                is_initial = event.get('is_initial_purchase', False)
                event_type = "📦 초기 매수" if is_initial else "🔄 리밸런싱"
                st.markdown(f"**{event['date'].strftime('%Y-%m-%d')}** {event_type} - 포트폴리오 가치: {sym}{event['portfolio_value']:,.0f}")

                # 인출금 표시 (초기 매수 제외)
                if not is_initial:
                    withdrawal = withdrawal_by_date.get(event['date'])
                    if withdrawal and withdrawal['total_withdrawal'] > 0:
                        from_cash = withdrawal['from_dividend']
                        from_sell = withdrawal['from_portfolio']
                        cost = withdrawal['transaction_cost']
                        parts = []
                        if from_cash > 0:
                            parts.append(f"현금: {sym}{from_cash:,.0f}")
                        if from_sell > 0:
                            parts.append(f"매도: {sym}{from_sell:,.0f}")
                        source = " + ".join(parts) if parts else ""
                        cost_str = f" | 거래비용: {sym}{cost:,.0f}" if cost > 0 else ""
                        st.markdown(f"  💰 인출: {sym}{withdrawal['total_withdrawal']:,.0f} ({source}){cost_str}")

                if event['trades']:
                    for trade in event['trades']:
                        action = "매수" if trade['shares'] > 0 else "매도"
                        action_symbol = "+" if trade['shares'] > 0 else "-"

                        # 현재/목표 보유량 표시 (있는 경우)
                        if 'current_shares' in trade and 'target_shares' in trade:
                            st.markdown(
                                f"  - {trade['symbol']}: {round(trade['current_shares']):,}주 → "
                                f"{round(trade['target_shares']):,}주 ({action_symbol}{round(abs(trade['shares'])):,}주 {action}) "
                                f"× {sym}{trade['price']:,.2f} = {sym}{abs(trade['value']):,.0f}"
                            )
                        else:
                            st.markdown(
                                f"  - {trade['symbol']}: {action} {round(abs(trade['shares'])):,}주 "
                                f"× {sym}{trade['price']:,.2f} = {sym}{abs(trade['value']):,.0f}"
                            )
                else:
                    st.markdown("  - 거래 없음 (목표 비율 유지)")
                st.markdown("---")

    with st.expander("상세 배당금 로그"):
        if result.dividend_events:
            div_summary = pd.DataFrame(result.dividend_events)
            div_summary['date'] = div_summary['date'].dt.strftime('%Y-%m-%d')
            div_summary = div_summary.round(2)
            # 전체 기간 배당 로그 표시 (최근 20개 제한 제거)
            st.dataframe(div_summary, use_container_width=True, hide_index=True)


def display_backtest_results(result: BacktestResult, backtester: PortfolioBacktester):
    """백테스트 결과 표시"""

    st.markdown("---")
    st.subheader("백테스트 결과")

    allocation = backtester.allocation

    _render_performance_metrics(result, allocation)

    st.markdown("---")
    history_df = backtester.get_portfolio_history_df(result)

    _render_portfolio_chart(history_df, result, allocation)
    _render_allocation_chart(history_df, allocation)

    st.subheader("구성 종목별 성과")
    display_etf_performance(backtester)

    _render_annual_summary(backtester.get_annual_summary_df(result), allocation)
    _render_withdrawal_dividend(result, allocation)
    _render_tax_summary(result, allocation)
    _render_detail_logs(result, allocation)

