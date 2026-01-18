"""
Kquant 백테스트 대시보드 메인 실행 파일

실행 방법:
    streamlit run app.py
"""
import sys
from pathlib import Path

# 프로젝트 루트를 Python 경로에 추가
project_root = Path(__file__).parent
sys.path.append(str(project_root))

# 메인 대시보드 실행
from src.dashboard.main_app import main

# Streamlit은 스크립트를 직접 실행하므로 조건문 없이 main() 호출
main()
