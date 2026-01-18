"""
Playwright E2E UI 테스트

실제 브라우저에서 사용자 상호작용을 테스트합니다.
"""
import pytest
from playwright.sync_api import Page, expect


class TestMainPage:
    """메인 페이지 E2E 테스트"""

    def test_page_loads_with_title(self, page: Page, streamlit_server: str):
        """페이지가 올바른 타이틀과 함께 로드되는지 확인"""
        page.goto(streamlit_server)

        # 페이지 로드 대기
        page.wait_for_load_state("networkidle")

        # 메인 타이틀 확인
        expect(page.locator("h1")).to_contain_text("은퇴의 꿈")

    def test_sidebar_navigation_exists(self, page: Page, streamlit_server: str):
        """사이드바 네비게이션이 존재하는지 확인"""
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")

        # 사이드바에서 페이지 선택 라디오 버튼 확인
        sidebar = page.locator('[data-testid="stSidebar"]')
        expect(sidebar).to_be_visible()

        # 자산 배분 백테스트 옵션 확인
        expect(page.get_by_text("자산 배분 백테스트")).to_be_visible()

        # 포트폴리오 비교 옵션 확인
        expect(page.get_by_text("포트폴리오 비교")).to_be_visible()


class TestBacktestPage:
    """자산 배분 백테스트 페이지 E2E 테스트"""

    def test_backtest_page_is_default(self, page: Page, streamlit_server: str):
        """자산 배분 백테스트가 기본 페이지인지 확인"""
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")

        # 자산 배분 백테스트 라디오가 선택되어 있는지 확인
        radio = page.locator('input[type="radio"][value="자산 배분 백테스트"]')
        expect(radio).to_be_checked()


class TestPortfolioComparisonPage:
    """포트폴리오 비교 페이지 E2E 테스트"""

    def test_navigate_to_comparison_page(self, page: Page, streamlit_server: str):
        """포트폴리오 비교 페이지로 이동 테스트"""
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")

        # 포트폴리오 비교 클릭
        page.get_by_text("포트폴리오 비교").click()

        # 페이지 전환 대기
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)  # Streamlit 렌더링 대기

        # 포트폴리오 비교 라디오가 선택되어 있는지 확인
        radio = page.locator('input[type="radio"][value="포트폴리오 비교"]')
        expect(radio).to_be_checked()


class TestPageTransitions:
    """페이지 전환 E2E 테스트"""

    def test_switch_pages_without_error(self, page: Page, streamlit_server: str):
        """페이지 전환 시 에러 없이 동작하는지 확인"""
        page.goto(streamlit_server)
        page.wait_for_load_state("networkidle")

        # 포트폴리오 비교로 전환
        page.get_by_text("포트폴리오 비교").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # 에러 메시지가 없는지 확인
        error_elements = page.locator('[data-testid="stException"]')
        expect(error_elements).to_have_count(0)

        # 다시 자산 배분 백테스트로 전환
        page.get_by_text("자산 배분 백테스트").click()
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)

        # 에러 메시지가 없는지 확인
        error_elements = page.locator('[data-testid="stException"]')
        expect(error_elements).to_have_count(0)
