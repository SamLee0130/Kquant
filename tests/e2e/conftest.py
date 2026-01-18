"""
Playwright E2E 테스트 설정

Streamlit 서버를 자동으로 시작/종료하는 fixture를 제공합니다.
"""
import pytest
import subprocess
import time
import sys
import socket
from pathlib import Path
from playwright.sync_api import Page

# pytest-playwright 플러그인 활성화
pytest_plugins = ["pytest_playwright"]


def is_port_in_use(port: int) -> bool:
    """포트가 사용 중인지 확인"""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        return s.connect_ex(("localhost", port)) == 0


def wait_for_server(port: int, timeout: int = 30) -> bool:
    """서버가 준비될 때까지 대기"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        if is_port_in_use(port):
            return True
        time.sleep(0.5)
    return False


@pytest.fixture(scope="module")
def streamlit_server():
    """
    Streamlit 서버를 시작하고 테스트 후 종료합니다.

    Yields:
        str: Streamlit 서버 URL (예: http://localhost:8501)
    """
    port = 8501
    project_root = Path(__file__).parent.parent.parent

    # 이미 실행 중이면 기존 서버 사용
    if is_port_in_use(port):
        yield f"http://localhost:{port}"
        return

    # Streamlit 서버 시작
    process = subprocess.Popen(
        [
            sys.executable, "-m", "streamlit", "run",
            str(project_root / "app.py"),
            "--server.port", str(port),
            "--server.headless", "true",
            "--server.fileWatcherType", "none",
            "--browser.gatherUsageStats", "false",
        ],
        cwd=str(project_root),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

    # 서버 준비 대기
    if not wait_for_server(port, timeout=30):
        process.terminate()
        process.wait()
        pytest.fail(f"Streamlit server failed to start on port {port}")

    # 추가 안정화 대기
    time.sleep(2)

    yield f"http://localhost:{port}"

    # 테스트 완료 후 서버 종료
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
