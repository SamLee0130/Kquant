"""
Streamlit AppTest 기반 단위 테스트

AppTest는 Streamlit 앱을 헤드리스 모드로 테스트합니다.
실제 브라우저 없이 빠르게 위젯 상호작용을 검증합니다.
"""
import pytest
from streamlit.testing.v1 import AppTest


class TestMainAppLoads:
    """메인 앱 로드 테스트"""

    def test_app_loads_without_error(self):
        """앱이 에러 없이 로드되는지 확인"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)
        assert not at.exception, f"App raised exception: {at.exception}"

    def test_main_title_displayed(self):
        """메인 타이틀이 표시되는지 확인"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)

        # 타이틀 확인
        titles = [t.value for t in at.title]
        assert any("은퇴의 꿈" in title for title in titles), \
            f"Expected '은퇴의 꿈' in titles, got: {titles}"

    def test_sidebar_page_selector_exists(self):
        """사이드바 페이지 선택 라디오 버튼 존재 확인"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)

        # 사이드바에 radio 버튼이 있는지 확인
        assert len(at.sidebar.radio) > 0, "Expected radio button in sidebar"


class TestAllocationBacktestPage:
    """자산 배분 백테스트 페이지 테스트"""

    def test_default_page_is_backtest(self):
        """기본 페이지가 자산 배분 백테스트인지 확인"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)

        # 기본 선택된 라디오 값 확인
        radio = at.sidebar.radio[0]
        assert radio.value == "자산 배분 백테스트", \
            f"Expected default page '자산 배분 백테스트', got: {radio.value}"


class TestPortfolioComparisonPage:
    """포트폴리오 비교 페이지 테스트"""

    def test_switch_to_comparison_page(self):
        """포트폴리오 비교 페이지로 전환 테스트"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)

        # 페이지 전환
        at.sidebar.radio[0].set_value("포트폴리오 비교")
        at.run(timeout=30)

        assert not at.exception, f"Page switch raised exception: {at.exception}"

        # 전환 후 라디오 값 확인
        assert at.sidebar.radio[0].value == "포트폴리오 비교"


class TestAppIntegrity:
    """앱 무결성 테스트"""

    def test_no_runtime_errors_on_page_switch(self):
        """페이지 전환 시 런타임 에러가 없는지 확인"""
        at = AppTest.from_file("app.py")
        at.run(timeout=30)

        # 자산 배분 백테스트 → 포트폴리오 비교
        at.sidebar.radio[0].set_value("포트폴리오 비교")
        at.run(timeout=30)
        assert not at.exception, f"Switch to comparison raised: {at.exception}"

        # 포트폴리오 비교 → 자산 배분 백테스트
        at.sidebar.radio[0].set_value("자산 배분 백테스트")
        at.run(timeout=30)
        assert not at.exception, f"Switch to backtest raised: {at.exception}"
