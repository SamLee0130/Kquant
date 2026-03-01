"""backtest_utils 테스트"""
import pytest
import pandas as pd
from src.backtest.tax_calculator import TaxEvent
from src.backtest.backtest_utils import summarize_tax_events


def _make_event(tax_type: str, tax_amount: float) -> TaxEvent:
    return TaxEvent(
        date=pd.Timestamp("2024-06-15"),
        tax_type=tax_type,
        gross_amount=tax_amount / 0.15,
        tax_amount=tax_amount,
        net_amount=(tax_amount / 0.15) - tax_amount,
    )


class TestSummarizeTaxEvents:
    def test_empty_events(self):
        result = summarize_tax_events([])
        assert result['dividend_tax'] == 0.0
        assert result['capital_gains_tax'] == 0.0
        assert result['kr_capital_gains_tax'] == 0.0
        assert result['total_tax'] == 0.0

    def test_dividend_only(self):
        events = [_make_event('dividend', 100.0)]
        result = summarize_tax_events(events)
        assert result['dividend_tax'] == 100.0
        assert result['capital_gains_tax'] == 0.0
        assert result['kr_capital_gains_tax'] == 0.0
        assert result['total_tax'] == 100.0

    def test_capital_gains_only(self):
        events = [_make_event('capital_gains', 200.0)]
        result = summarize_tax_events(events)
        assert result['capital_gains_tax'] == 200.0
        assert result['total_tax'] == 200.0

    def test_kr_capital_gains_only(self):
        events = [_make_event('kr_capital_gains', 150.0)]
        result = summarize_tax_events(events)
        assert result['kr_capital_gains_tax'] == 150.0
        assert result['total_tax'] == 150.0

    def test_mixed_tax_types(self):
        events = [
            _make_event('dividend', 100.0),
            _make_event('capital_gains', 200.0),
            _make_event('kr_capital_gains', 50.0),
        ]
        result = summarize_tax_events(events)
        assert result['dividend_tax'] == 100.0
        assert result['capital_gains_tax'] == 200.0
        assert result['kr_capital_gains_tax'] == 50.0
        assert result['total_tax'] == 350.0

    def test_dict_events(self):
        events = [
            {'tax_type': 'dividend', 'tax_amount': 100.0},
            {'tax_type': 'kr_capital_gains', 'tax_amount': 50.0},
        ]
        result = summarize_tax_events(events)
        assert result['dividend_tax'] == 100.0
        assert result['kr_capital_gains_tax'] == 50.0
        assert result['total_tax'] == 150.0

    def test_has_kr_capital_gains_key(self):
        """반환값에 kr_capital_gains_tax 키가 항상 존재"""
        result = summarize_tax_events([])
        assert 'kr_capital_gains_tax' in result
