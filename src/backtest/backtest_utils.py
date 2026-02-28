"""
백테스트 공통 유틸리티

대시보드 페이지에서 공통으로 사용하는 세금 필터링 및 데이터 처리 함수입니다.
"""
from typing import Dict, List, Union
from src.backtest.tax_calculator import TaxEvent


def summarize_tax_events(
    tax_events: Union[List[TaxEvent], List[Dict]]
) -> Dict[str, float]:
    """세금 이벤트를 유형별로 합산

    Args:
        tax_events: TaxEvent 객체 리스트 또는 딕셔너리 리스트

    Returns:
        {'dividend_tax': float, 'capital_gains_tax': float, 'total_tax': float}
    """
    dividend_tax = 0.0
    capital_gains_tax = 0.0

    for event in tax_events:
        if isinstance(event, TaxEvent):
            if event.tax_type == 'dividend':
                dividend_tax += event.tax_amount
            elif event.tax_type == 'capital_gains':
                capital_gains_tax += event.tax_amount
        else:
            # Dict-like event
            if event.get('tax_type') == 'dividend':
                dividend_tax += event.get('tax_amount', 0.0)
            elif event.get('tax_type') == 'capital_gains':
                capital_gains_tax += event.get('tax_amount', 0.0)

    return {
        'dividend_tax': dividend_tax,
        'capital_gains_tax': capital_gains_tax,
        'total_tax': dividend_tax + capital_gains_tax
    }
