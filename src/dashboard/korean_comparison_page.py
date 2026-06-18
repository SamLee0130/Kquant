"""
한국 주식/ETF 기간 수익률 비교 페이지

한국어 종목명 또는 6자리 코드로 한국 상장 주식·ETF를 검색해 선택하고,
기간별(1M·3M·6M·YTD·1Y·3Y·5Y) 후행 수익률을 표로 비교하며, 하단에 기간 수익률
추이를 라인 차트로 보여준다. 배당소득세(15.4%) 반영 total return 기준이며,
양도차익세는 미실현이라 미반영한다. '기준일 주가'는 실제 종가(Close) 기준이다.
"""
from datetime import date, datetime, timedelta

import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from dateutil.relativedelta import relativedelta

from src.data.krx_listing import all_securities, format_option_label
from src.data.data_fetcher import fetch_total_return_prices, fetch_close_prices
from src.backtest.trailing_returns import (
    compute_trailing_returns,
    horizon_start_date,
    TRAILING_HORIZONS,
)
from config.settings import KOREAN_TAX_DEFAULTS

MAX_KOREAN_COMPARISON = 5
DEFAULT_TREND_HORIZON = "5Y"
TREND_COLORS = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']


def _format_return(value):
    return "—" if value is None else f"{value:+.1f}%"


def _format_price(value):
    if value is None or pd.isna(value):
        return "—"
    return f"₩{int(round(value)):,}"


def _fetch_price_on_date(ticker, start_fetch, end_fetch, as_of):
    """기준일(또는 직전 거래일)의 실제 종가와 그 거래일. 실패 시 (None, None)."""
    try:
        close = fetch_close_prices(ticker, start_fetch, end_fetch)
    except ValueError:
        return None, None
    windowed = close[close.index <= as_of]
    if windowed.empty:
        return None, None
    return float(windowed.iloc[-1]), windowed.index[-1]


def _run_comparison(picked, as_of_input, is_net):
    """선택 종목 조회 + 후행 수익률 계산. (rows, as_of, price_date) 또는 None.

    rows: [(security, returns, prices, price_on_date)]
    """
    dividend_tax_rate = (
        KOREAN_TAX_DEFAULTS["kr_dividend_tax_rate"] if is_net else 0.0
    )
    as_of = pd.Timestamp(as_of_input)
    start_fetch = (as_of - relativedelta(years=5) - timedelta(days=60)).strftime("%Y-%m-%d")
    end_fetch = (as_of + timedelta(days=1)).strftime("%Y-%m-%d")

    rows = []
    price_dates = []
    with st.spinner("데이터 조회 및 계산 중..."):
        for security in picked:
            try:
                prices = fetch_total_return_prices(
                    security.yf_ticker, start_fetch, end_fetch, dividend_tax_rate,
                )
            except ValueError as error:
                st.warning(f"{security.name}({security.code}) 데이터 조회 실패: {error}")
                continue
            returns = compute_trailing_returns(prices, as_of)
            price_on_date, price_date = _fetch_price_on_date(
                security.yf_ticker, start_fetch, end_fetch, as_of,
            )
            if price_date is not None:
                price_dates.append(price_date)
            rows.append((security, returns, prices, price_on_date))

    if not rows:
        return None
    effective_date = max(price_dates) if price_dates else None
    return rows, as_of, effective_date


def _render_trailing_table(rows, as_of, is_net, price_date):
    """후행 수익률 표 렌더링. rows: [(security, returns, prices, price_on_date)]"""
    data = []
    for security, returns, _prices, price_on_date in rows:
        record = {
            "종목": security.name,
            "코드": security.code,
            "기준일 주가": _format_price(price_on_date),
        }
        for horizon in TRAILING_HORIZONS:
            record[horizon] = _format_return(returns[horizon])
        data.append(record)

    frame = pd.DataFrame(data)
    st.dataframe(frame, use_container_width=True, hide_index=True)

    tax_note = "세후 (배당소득세 15.4% 반영)" if is_net else "세전 (gross)"
    price_note = (
        f"{price_date.date()} 종가" if price_date is not None
        else "직전 거래일 종가"
    )
    st.caption(
        f"기준일 {as_of.date()} · {tax_note} · 배당 재투자 total return 기준. "
        f"'기준일 주가'는 {price_note} 기준입니다(분할만 반영, 배당 미조정 실제 종가). "
        "각 구간은 누적 수익률(연율화 아님)이며, 데이터가 부족한 구간은 '—'로 표시됩니다 "
        "(예: 신규 상장 종목의 3년·5년). "
        "양도차익세는 보유(미실현) 가정이라 반영하지 않습니다."
    )


def _render_trend_chart(rows, as_of, horizon):
    """기간 수익률 추이 라인 차트. 선택 구간 시작=0%로 정규화."""
    window_start = horizon_start_date(as_of, horizon)
    fig = go.Figure()
    plotted = False

    for index, (security, _returns, prices, _price_on_date) in enumerate(rows):
        windowed = prices[(prices.index >= window_start) & (prices.index <= as_of)]
        if len(windowed) < 2:
            continue
        cumulative = (windowed / windowed.iloc[0] - 1) * 100
        fig.add_trace(go.Scatter(
            x=cumulative.index,
            y=cumulative.values,
            name=f"{security.name} ({security.code})",
            line=dict(color=TREND_COLORS[index % len(TREND_COLORS)]),
        ))
        plotted = True

    if not plotted:
        st.info("선택한 기간에 표시할 데이터가 부족합니다. 더 긴 기간을 선택해 보세요.")
        return

    fig.add_hline(y=0, line_dash="dash", line_color="gray")
    fig.update_layout(
        title=f"기간 수익률 추이 ({horizon}, 구간 시작=0%)",
        yaxis_title="누적 수익률 (%)",
        xaxis_title="날짜",
        hovermode="x unified",
        height=460,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.caption(
        f"각 종목을 선택 기간({horizon})의 첫 거래일 대비 누적 수익률(%)로 표시합니다. "
        "상장이 늦은 종목은 데이터가 있는 시점부터 선이 시작됩니다."
    )


def show_korean_comparison_page():
    """한국 주식/ETF 비교 페이지 표시"""
    st.header("한국 주식 / ETF 비교")
    st.markdown(
        "한국에 상장된 주식·ETF를 한글 종목명 또는 6자리 코드로 검색해 1~5개 선택하면, "
        "기간별(1개월~5년) 후행 수익률을 표와 추이 차트로 비교합니다. 배당 재투자가 "
        "반영된 total return 기준이며, 한국 배당소득세(15.4%)를 적용해 세후로 계산할 수 있습니다."
    )
    st.markdown("---")

    with st.sidebar:
        st.subheader("비교 설정")
        today = datetime.now().date()
        as_of_input = st.date_input(
            "기준일", value=today,
            min_value=date(2000, 1, 1), max_value=today,
            key="korean_as_of",
            help="후행 수익률·기준일 주가의 종점입니다. 이 날짜를 기준으로 1개월·1년·5년 전과 비교합니다.",
        )
        tax_mode = st.radio(
            "세금 기준",
            options=["세후 (배당세 15.4%)", "세전 (gross)"],
            index=0, key="korean_tax_mode",
            help="세후는 배당 기여분에 한국 배당소득세 15.4%를 적용한 net total return입니다. "
                 "주식·ETF 모두 동일하게 적용하는 단순화 모델입니다.",
        )

    picked = st.multiselect(
        "종목 검색·선택 (한글명 또는 6자리 코드 입력, 최대 5개)",
        options=all_securities(),
        format_func=format_option_label,
        max_selections=MAX_KOREAN_COMPARISON,
        key="korean_picks",
        help="검색창에 한글 종목명(예: 삼성전자)이나 코드(예: 005930)를 입력하면 후보가 "
             "필터되고, 그 자리에서 바로 선택할 수 있습니다.",
    )

    if not picked:
        st.info("비교할 종목을 1개 이상 선택하세요.")
        return

    is_net = tax_mode.startswith("세후")
    result = _run_comparison(picked, as_of_input, is_net)
    if result is None:
        st.error("조회된 종목이 없습니다. 다른 종목을 선택하거나 기준일을 조정하세요.")
        return

    rows, as_of, price_date = result
    _render_trailing_table(rows, as_of, is_net, price_date)
    st.markdown("---")
    horizon = st.radio(
        "추이 차트 기간", options=TRAILING_HORIZONS,
        index=TRAILING_HORIZONS.index(DEFAULT_TREND_HORIZON),
        horizontal=True, key="korean_trend_horizon",
        help="표와 동일한 구간을 선택하면, 해당 구간 시작일을 0%로 맞춰 추이를 그립니다.",
    )
    _render_trend_chart(rows, as_of, horizon)
