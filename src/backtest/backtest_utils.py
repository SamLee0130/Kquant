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
        {'dividend_tax': float, 'capital_gains_tax': float,
         'kr_capital_gains_tax': float, 'total_tax': float}
    """
    dividend_tax = 0.0
    capital_gains_tax = 0.0
    kr_capital_gains_tax = 0.0

    for event in tax_events:
        if isinstance(event, TaxEvent):
            tax_type = event.tax_type
            amount = event.tax_amount
        else:
            tax_type = event.get('tax_type')
            amount = event.get('tax_amount', 0.0)

        if tax_type == 'dividend':
            dividend_tax += amount
        elif tax_type == 'capital_gains':
            capital_gains_tax += amount
        elif tax_type == 'kr_capital_gains':
            kr_capital_gains_tax += amount

    return {
        'dividend_tax': dividend_tax,
        'capital_gains_tax': capital_gains_tax,
        'kr_capital_gains_tax': kr_capital_gains_tax,
        'total_tax': dividend_tax + capital_gains_tax + kr_capital_gains_tax
    }
