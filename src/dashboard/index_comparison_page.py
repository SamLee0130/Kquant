"""
지수/ETF 비교 페이지

주요 지수 추종 ETF나 임의의 ETF/종목을 1~5개 선택해 리밸런싱 없이
buy-and-hold 했을 때의 누적 수익률을 비교한다.

- 배당 재투자가 반영된 total return(yfinance 조정 종가)을 사용한다.
- 거래 통화가 다른 종목은 기준 통화로 환산해 단일 통화 기준으로 비교한다
  (USD↔KRW 직접, 그 외 통화는 USD 피벗).
- 지표: 누적 수익률, CAGR, 최대 낙폭(MDD), 샤프비율, 변동성.
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import date, datetime, timedelta
from typing import Dict, List
import logging

from src.backtest.index_metrics import compute_buy_hold_metrics
from src.data.data_fetcher import fetch_total_return_prices, fetch_ticker_currency
from src.data.fx_fetcher import CurrencyConverter
from src.data.index_registry import (
    INDEX_REGISTRY, DEFAULT_INDEX_KEYS, MAX_COMPARISON_INDICES, IndexInfo, get_index,
)

logger = logging.getLogger(__name__)

# 지수별 색상
INDEX_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']


def _to_base_currency(
    prices: pd.Series,
    currency: str,
    converter: CurrencyConverter,
) -> pd.Series:
    """가격 시계열을 기준 통화로 환산"""
    if currency == converter.base_currency:
        return prices
    rates = pd.Series(
        [converter.get_fx_rate(currency, date) for date in prices.index],
        index=prices.index,
    )
    return prices * rates


def _resolve_custom_ticker(ticker: str) -> IndexInfo:
    """임의 티커를 IndexInfo로 변환 (통화 자동 감지)

    Raises:
        ValueError: 통화/데이터를 가져올 수 없는 경우
    """
    currency = fetch_ticker_currency(ticker)
    return IndexInfo(
        key=ticker, display_name=ticker, etf_ticker=ticker,
        currency=currency, description="사용자 지정",
    )


def _load_index_series(
    infos: List[IndexInfo],
    base_currency: str,
    start_date: str,
    end_date: str,
    dividend_tax_rate: float = 0.0,
) -> Dict[IndexInfo, pd.Series]:
    """선택 종목별 기준 통화 가격 시계열을 조회

    각 종목은 데이터 이력만큼의 전체 구간을 그대로 유지한다(서로 자르지 않음).
    공통 구간 정렬이 필요하면 _clip_to_common_window()를 따로 적용한다.
    dividend_tax_rate > 0이면 배당세 반영 net total return을 사용한다.

    Returns:
        IndexInfo → 기준 통화 가격 Series (각자 전체 기간)
    """
    needs_fx = any(info.currency != base_currency for info in infos)

    converter = CurrencyConverter(base_currency=base_currency)
    if needs_fx:
        converter.fetch_fx_data(start_date, end_date)

    series_by_info: Dict[IndexInfo, pd.Series] = {}
    for info in infos:
        prices = fetch_total_return_prices(
            info.etf_ticker, start_date, end_date, dividend_tax_rate,
        )
        series_by_info[info] = _to_base_currency(prices, info.currency, converter)

    return series_by_info


def _clip_to_common_window(
    series_by_info: Dict[IndexInfo, pd.Series],
) -> Dict[IndexInfo, pd.Series]:
    """모든 종목이 거래된 공통 거래일로 잘라 동일 구간 비교용 시계열을 만든다"""
    common_dates = None
    for series in series_by_info.values():
        common_dates = (
            series.index if common_dates is None
            else common_dates.intersection(series.index)
        )
    return {info: series.loc[common_dates] for info, series in series_by_info.items()}


def _render_summary_table(
    series_by_info: Dict[IndexInfo, pd.Series],
    base_currency: str,
    common_window: bool,
    dividend_tax_rate: float,
):
    """성과 요약 테이블 렌더링"""
    st.markdown("### 성과 요약")

    rows = []
    for info, series in series_by_info.items():
        metrics = compute_buy_hold_metrics(series)
        elapsed_years = (series.index[-1] - series.index[0]).days / 365.25
        rows.append({
            "종목": info.display_name,
            "티커": info.etf_ticker,
            "데이터 시작": series.index[0].strftime("%Y-%m-%d"),
            "데이터 종료": series.index[-1].strftime("%Y-%m-%d"),
            "계산 기간 (년)": round(elapsed_years, 1),
            "누적 수익률 (%)": round(metrics["total_return"], 1),
            "CAGR (%)": round(metrics["cagr"], 1),
            "변동성 (%)": round(metrics["volatility"], 1),
            "샤프비율": round(metrics["sharpe_ratio"], 2),
            "최대 낙폭 (%)": round(metrics["max_drawdown"], 1),
        })

    summary_df = pd.DataFrame(rows)
    st.dataframe(summary_df, use_container_width=True, hide_index=True)

    if common_window:
        sample = next(iter(series_by_info.values()))
        window = (
            f"공통 구간: {sample.index[0]:%Y-%m-%d} ~ {sample.index[-1]:%Y-%m-%d} "
            f"({len(sample)} 거래일)"
        )
    else:
        window = "각 종목 전체 기간 (종목별 시작일은 표의 '데이터 시작' 참고)"
    tax_note = (
        f"배당세 {dividend_tax_rate:.1%} 반영 net total return"
        if dividend_tax_rate > 0 else "세전 gross total return (배당세 0%)"
    )
    st.caption(f"기준 통화: {base_currency} · {window} · {tax_note}")


def _render_cumulative_returns_chart(
    series_by_info: Dict[IndexInfo, pd.Series],
    log_scale: bool = False,
):
    """누적 수익률 비교 차트 렌더링 (각 시계열을 시작 시점 기준으로 리베이스)

    선형 축에서는 누적 수익률(%)을, 로그 축에서는 성장 지수(시작=100)를
    표시한다. 수익률(%)은 0 이하 값이 있어 로그 축에 그릴 수 없으므로,
    로그 모드에서는 항상 양수인 성장 지수를 사용한다.
    """
    st.markdown("### 누적 수익률 비교")

    fig = go.Figure()
    for i, (info, series) in enumerate(series_by_info.items()):
        growth = series / series.iloc[0] * 100
        y = growth if log_scale else (growth - 100)
        fig.add_trace(go.Scatter(
            x=growth.index,
            y=y.values,
            mode='lines',
            name=info.display_name,
            line=dict(color=INDEX_COLORS[i % len(INDEX_COLORS)], width=2),
        ))

    if log_scale:
        fig.update_yaxes(type='log')
        fig.add_hline(y=100, line_dash="dash", line_color="gray")
        title, yaxis_title = "누적 성장 비교 (로그 스케일, 시작=100)", "성장 지수"
    else:
        fig.add_hline(y=0, line_dash="dash", line_color="gray")
        title, yaxis_title = "누적 수익률 비교 (Buy & Hold)", "수익률 (%)"

    fig.update_layout(
        title=title,
        xaxis_title="날짜",
        yaxis_title=yaxis_title,
        height=450,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _render_drawdown_chart(series_by_info: Dict[IndexInfo, pd.Series]):
    """낙폭(Drawdown) 추이 차트 렌더링"""
    st.markdown("### 낙폭 (Drawdown) 추이")

    fig = go.Figure()
    for i, (info, series) in enumerate(series_by_info.items()):
        drawdown = (series / series.cummax() - 1) * 100
        fig.add_trace(go.Scatter(
            x=drawdown.index,
            y=drawdown.values,
            mode='lines',
            name=info.display_name,
            line=dict(color=INDEX_COLORS[i % len(INDEX_COLORS)], width=1.5),
        ))

    fig.update_layout(
        title="낙폭 추이",
        xaxis_title="날짜",
        yaxis_title="낙폭 (%)",
        height=350,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    st.plotly_chart(fig, use_container_width=True)


def _format_option(key: str) -> str:
    """multiselect 항목 표시: 프리셋은 이름+설명, 직접 입력 티커는 대문자 그대로"""
    if key in INDEX_REGISTRY:
        info = INDEX_REGISTRY[key]
        return f"{info.display_name} ({info.description})"
    return key.upper()


def _build_index_infos(selected_items: List[str]) -> List[IndexInfo]:
    """선택 항목(프리셋 키 또는 직접 입력 티커)을 IndexInfo 리스트로 변환

    잘못된 티커는 경고 후 건너뛴다. 동일 티커는 한 번만 포함한다.
    """
    infos: List[IndexInfo] = []
    seen_tickers = set()

    for item in selected_items:
        if item in INDEX_REGISTRY:
            info = get_index(item)
        else:
            ticker = item.strip().upper()
            if not ticker:
                continue
            try:
                info = _resolve_custom_ticker(ticker)
            except ValueError as error:
                st.warning(f"'{ticker}' 건너뜀: {error}")
                continue

        if info.etf_ticker in seen_tickers:
            continue
        seen_tickers.add(info.etf_ticker)
        infos.append(info)

    return infos


def show_index_comparison_page():
    """지수/ETF 비교 페이지 표시"""
    st.header("지수 / ETF 비교")
    st.markdown(
        "주요 지수 추종 ETF나 임의의 ETF/종목을 1~5개 선택해 리밸런싱 없이 "
        "장기 보유(Buy & Hold)했을 때의 누적 수익률을 비교합니다. "
        "배당 재투자가 반영된 total return 기준이며, 배당소득세율을 적용해 "
        "세후(net) 기준으로도 계산할 수 있습니다."
    )
    st.markdown("---")

    with st.sidebar:
        st.subheader("비교 설정")
        base_currency = st.selectbox(
            "기준 통화", options=["USD", "KRW"], index=0, key="index_base_currency",
        )
        today = datetime.now().date()
        col_start, col_end = st.columns(2)
        with col_start:
            start_input = st.date_input(
                "시작일", value=today - timedelta(days=365 * 10),
                min_value=date(1980, 1, 1), max_value=today,
                key="index_start_date",
                help="요청 시작일보다 종목 데이터 이력이 짧으면 데이터가 있는 "
                     "구간으로 자동 제한됩니다 (예: SPY는 1993년 상장). 실제 비교 "
                     "구간은 결과 하단에 표시됩니다.",
            )
        with col_end:
            end_input = st.date_input(
                "종료일", value=today,
                min_value=date(1980, 1, 1), max_value=today,
                key="index_end_date",
            )
        common_window = st.checkbox(
            "공통 구간으로 정렬 (공정 비교)", value=False,
            key="index_common_window",
            help="체크 시 모든 종목을 함께 거래된 공통 구간으로 잘라 동일 기간 "
                 "기준으로 비교합니다. 해제 시 각 종목의 전체 이력을 그대로 사용합니다 "
                 "(짧은 종목이 다른 종목을 자르지 않음).",
        )
        log_scale = st.checkbox(
            "누적 차트 로그 스케일", value=False, key="index_log_scale",
            help="장기·다종목 비교 시 초기 구간이 눌리지 않도록 로그 축으로 표시합니다. "
                 "로그 모드에서는 수익률(%) 대신 성장 지수(시작=100)를 표시합니다.",
        )
        dividend_tax_pct = st.slider(
            "배당소득세율 (%)", min_value=0.0, max_value=30.0, value=15.0, step=0.1,
            key="index_dividend_tax",
            help="배당 재투자 시 부과되는 세금. 배당 기여분에만 적용해 net total "
                 "return으로 계산합니다. 0%면 세전(gross). 모든 종목에 동일 세율을 "
                 "적용하는 단순화 모델입니다.",
        )

    index_options = list(INDEX_REGISTRY.keys())
    selected_items = st.multiselect(
        "비교할 지수/ETF 선택 (검색하거나 티커를 직접 입력 후 Enter, 최대 5개)",
        options=index_options,
        default=DEFAULT_INDEX_KEYS,
        format_func=_format_option,
        max_selections=MAX_COMPARISON_INDICES,
        accept_new_options=True,
        help="프리셋은 목록에서 검색해 선택하고, 그 외 종목(예: GDX, GLD, ARKK)은 "
             "티커를 입력 후 Enter로 추가합니다. 통화는 자동 감지되어 기준 통화로 "
             "환산됩니다 (USD↔KRW 및 그 외 통화 USD 피벗).",
    )

    if not st.button("비교 실행", type="primary"):
        return

    if start_input >= end_input:
        st.error("시작일은 종료일보다 앞서야 합니다.")
        return

    infos = _build_index_infos(selected_items)
    if not infos:
        st.info("비교할 종목을 1개 이상 선택하거나 입력하세요.")
        return

    start_date = start_input.strftime("%Y-%m-%d")
    end_date = end_input.strftime("%Y-%m-%d")

    with st.spinner("데이터 조회 및 계산 중..."):
        try:
            series_by_info = _load_index_series(
                infos, base_currency, start_date, end_date,
                dividend_tax_rate=dividend_tax_pct / 100.0,
            )
        except ValueError as error:
            st.error(f"데이터 조회 실패: {error}")
            return

    if common_window:
        series_by_info = _clip_to_common_window(series_by_info)

    if any(len(series) < 2 for series in series_by_info.values()):
        st.error("선택한 종목의 데이터 구간이 충분하지 않습니다.")
        return

    _render_summary_table(
        series_by_info, base_currency, common_window, dividend_tax_pct / 100.0,
    )
    st.markdown("---")
    _render_cumulative_returns_chart(series_by_info, log_scale)
    st.markdown("---")
    _render_drawdown_chart(series_by_info)
