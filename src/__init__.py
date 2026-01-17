"""
Kquant 백테스트 프로젝트 메인 패키지
"""

__version__ = "0.1.0"
__author__ = "Kquant Team"
__description__ = "주식/암호화폐 백테스트 및 분석 도구"

from .database_manager import db_manager

__all__ = ['db_manager']
