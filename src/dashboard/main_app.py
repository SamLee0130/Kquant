"""
Kquant 메인 Streamlit 대시보드
"""
import streamlit as st
import logging

# 로컬 모듈 임포트
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent.parent.parent))

from src.dashboard.allocation_backtest_page import show_allocation_backtest_page
from src.dashboard.portfolio_comparison_page import show_portfolio_comparison_page
from src.dashboard.optimization_page import show_portfolio_optimization_page
from src.dashboard.index_comparison_page import show_index_comparison_page
from config.settings import STREAMLIT_CONFIG

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 페이지 설정
st.set_page_config(
    page_title=STREAMLIT_CONFIG['page_title'],
    page_icon=STREAMLIT_CONFIG['page_icon'],
    layout=STREAMLIT_CONFIG['layout'],
    initial_sidebar_state=STREAMLIT_CONFIG['sidebar_state']
)


def main():
    """메인 함수"""
    st.title("📈 은퇴의 꿈")
    st.markdown("---")
    
    # 사이드바 - 페이지 선택
    with st.sidebar:
        page = st.radio(
            "페이지 선택",
            options=["자산 배분 백테스트", "포트폴리오 비교", "최적 포트폴리오", "지수 / ETF 비교"],
            index=0
        )
        st.markdown("---")

    # 페이지 라우팅
    if page == "자산 배분 백테스트":
        show_allocation_backtest_page()
    elif page == "포트폴리오 비교":
        show_portfolio_comparison_page()
    elif page == "최적 포트폴리오":
        show_portfolio_optimization_page()
    elif page == "지수 / ETF 비교":
        show_index_comparison_page()


if __name__ == "__main__":
    main()
