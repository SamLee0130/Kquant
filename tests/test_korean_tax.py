"""
한국 상장 ETF 세금 규칙 테스트

세금 규칙 매트릭스:
- US: 배당세 15%, 양도소득세 22% 연말 이연, $2,000 공제
- KR_STOCK: 배당세 15.4%, 양도차익 비과세
- KR_OTHER: 배당세 15.4%, 매매차익 배당소득세 15.4% 즉시
"""
import pytest
import pandas as pd
from src.backtest.tax_calculator import TaxCalculator, TaxEvent
from src.data.etf_classifier import Market


@pytest.fixture
def calculator():
    return TaxCalculator()


class TestKRStockDividendTax:
    """국내 주식형 ETF 배당소득세 테스트"""

    def test_kr_stock_dividend_rate(self, calculator):
        """KR_STOCK 배당세율 15.4%"""
        event = calculator.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert abs(event.tax_amount - 10000.0 * 0.154) < 0.01
        assert abs(event.net_amount - 10000.0 * 0.846) < 0.01

    def test_kr_stock_dividend_event_type(self, calculator):
        event = calculator.calculate_dividend_tax(
            5000.0, pd.Timestamp("2024-03-15"), market=Market.KR_STOCK
        )
        assert event.tax_type == 'dividend'

    def test_kr_stock_dividend_added_to_history(self, calculator):
        calculator.calculate_dividend_tax(
            5000.0, pd.Timestamp("2024-03-15"), market=Market.KR_STOCK
        )
        assert len(calculator.tax_history) == 1


class TestKRStockCapitalGains:
    """국내 주식형 ETF 양도차익 비과세 테스트"""

    def test_kr_stock_capital_gain_is_tax_free(self, calculator):
        """KR_STOCK 양도차익은 비과세 (None 반환)"""
        result = calculator.record_capital_gain(
            50000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert result is None

    def test_kr_stock_capital_gain_no_annual_accumulation(self, calculator):
        """KR_STOCK 양도차익은 연간 누적에도 포함되지 않음"""
        calculator.record_capital_gain(
            50000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert calculator.annual_capital_gains.get(2024, 0.0) == 0.0

    def test_kr_stock_capital_gain_no_tax_event(self, calculator):
        """KR_STOCK 양도차익은 세금 이벤트 없음"""
        calculator.record_capital_gain(
            50000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert len(calculator.tax_history) == 0

    def test_kr_stock_loss_also_ignored(self, calculator):
        """KR_STOCK 손실도 무시"""
        result = calculator.record_capital_gain(
            -10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert result is None
        assert len(calculator.tax_history) == 0


class TestKROtherDividendTax:
    """국내 기타 ETF 배당소득세 테스트"""

    def test_kr_other_dividend_rate(self, calculator):
        """KR_OTHER 배당세율 15.4%"""
        event = calculator.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert abs(event.tax_amount - 10000.0 * 0.154) < 0.01

    def test_kr_other_dividend_event_type(self, calculator):
        event = calculator.calculate_dividend_tax(
            5000.0, pd.Timestamp("2024-03-15"), market=Market.KR_OTHER
        )
        assert event.tax_type == 'dividend'


class TestKROtherCapitalGains:
    """국내 기타 ETF 매매차익 즉시 과세 테스트"""

    def test_kr_other_capital_gain_immediate_tax(self, calculator):
        """KR_OTHER 양도차익은 즉시 15.4% 과세"""
        event = calculator.record_capital_gain(
            100000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert event is not None
        assert abs(event.tax_amount - 100000.0 * 0.154) < 0.01
        assert event.tax_type == 'kr_capital_gains'

    def test_kr_other_capital_gain_net_amount(self, calculator):
        event = calculator.record_capital_gain(
            100000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert abs(event.net_amount - 100000.0 * 0.846) < 0.01

    def test_kr_other_capital_gain_added_to_history(self, calculator):
        calculator.record_capital_gain(
            100000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert len(calculator.tax_history) == 1
        assert calculator.tax_history[0].tax_type == 'kr_capital_gains'

    def test_kr_other_capital_loss_no_tax(self, calculator):
        """KR_OTHER 손실에는 세금 없음"""
        result = calculator.record_capital_gain(
            -50000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert result is None
        assert len(calculator.tax_history) == 0

    def test_kr_other_no_annual_accumulation(self, calculator):
        """KR_OTHER는 연간 누적에 포함되지 않음 (US와 분리)"""
        calculator.record_capital_gain(
            100000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert calculator.annual_capital_gains.get(2024, 0.0) == 0.0

    def test_kr_other_no_exemption(self, calculator):
        """KR_OTHER는 기본공제 없이 전액 과세"""
        event = calculator.record_capital_gain(
            1000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert event is not None
        assert abs(event.tax_amount - 1000.0 * 0.154) < 0.01


class TestUSCapitalGainsUnchanged:
    """US ETF 양도소득세 기존 로직 유지 테스트"""

    def test_us_capital_gain_deferred(self, calculator):
        """US 양도차익은 연간 누적 (이연)"""
        result = calculator.record_capital_gain(
            50000.0, pd.Timestamp("2024-06-15"), market=Market.US
        )
        assert result is None
        assert calculator.annual_capital_gains[2024] == 50000.0

    def test_us_capital_gain_no_market_param(self, calculator):
        """market 파라미터 없으면 US 기본 동작"""
        result = calculator.record_capital_gain(
            50000.0, pd.Timestamp("2024-06-15")
        )
        assert result is None
        assert calculator.annual_capital_gains[2024] == 50000.0

    def test_us_settlement_with_exemption(self, calculator):
        calculator.record_capital_gain(50000.0, pd.Timestamp("2024-06-15"))
        tax = calculator.settle_annual_capital_gains_tax(2024)
        expected = (50000.0 - 2000.0) * 0.22
        assert abs(tax - expected) < 0.01

    def test_us_dividend_rate_unchanged(self, calculator):
        """market=None 배당세율은 기존 15%"""
        event = calculator.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15")
        )
        assert abs(event.tax_amount - 10000.0 * 0.15) < 0.01


class TestMixedPortfolioTax:
    """혼합 포트폴리오 세금 테스트"""

    def test_mixed_capital_gains_separation(self, calculator):
        """US와 KR_OTHER 양도차익이 분리 처리됨"""
        calculator.record_capital_gain(50000.0, pd.Timestamp("2024-06-15"), market=Market.US)
        calculator.record_capital_gain(30000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER)
        calculator.record_capital_gain(20000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK)

        # US는 연간 누적에만 기록
        assert calculator.annual_capital_gains[2024] == 50000.0
        # KR_OTHER는 즉시 과세 이벤트로 기록
        kr_events = [e for e in calculator.tax_history if e.tax_type == 'kr_capital_gains']
        assert len(kr_events) == 1
        assert abs(kr_events[0].tax_amount - 30000.0 * 0.154) < 0.01
        # KR_STOCK은 어디에도 기록 없음

    def test_mixed_dividend_rates(self, calculator):
        """US와 KR 배당세율이 다르게 적용됨"""
        us_event = calculator.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.US
        )
        kr_event = calculator.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert abs(us_event.tax_amount - 1500.0) < 0.01   # 15%
        assert abs(kr_event.tax_amount - 1540.0) < 0.01   # 15.4%

    def test_total_tax_includes_all_types(self, calculator):
        """총 세금에 US 이연 + KR_OTHER 즉시 과세 모두 포함"""
        # US 배당
        calculator.calculate_dividend_tax(10000.0, pd.Timestamp("2024-06-15"), market=Market.US)
        # KR_OTHER 즉시 과세
        calculator.record_capital_gain(50000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER)
        # US 양도차익 정산
        calculator.record_capital_gain(30000.0, pd.Timestamp("2024-06-15"), market=Market.US)
        calculator.settle_annual_capital_gains_tax(2024)

        total = calculator.get_total_tax()
        us_dividend_tax = 10000.0 * 0.15
        kr_capital_tax = 50000.0 * 0.154
        us_capital_tax = (30000.0 - 2000.0) * 0.22
        expected = us_dividend_tax + kr_capital_tax + us_capital_tax
        assert abs(total - expected) < 0.01


class TestCustomKoreanRates:
    """사용자 지정 한국 세율 테스트"""

    def test_custom_kr_dividend_rate(self):
        calc = TaxCalculator(kr_dividend_tax_rate=0.20)
        event = calc.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert abs(event.tax_amount - 2000.0) < 0.01

    def test_custom_kr_capital_gains_rate(self):
        calc = TaxCalculator(kr_capital_gains_rate=0.20)
        event = calc.record_capital_gain(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_OTHER
        )
        assert abs(event.tax_amount - 2000.0) < 0.01

    def test_zero_kr_dividend_rate_respected(self):
        """kr_dividend_tax_rate=0.0이 기본값으로 대체되지 않아야 함"""
        calc = TaxCalculator(kr_dividend_tax_rate=0.0)
        assert calc.kr_dividend_tax_rate == 0.0
        event = calc.calculate_dividend_tax(
            10000.0, pd.Timestamp("2024-06-15"), market=Market.KR_STOCK
        )
        assert event.tax_amount == 0.0

    def test_zero_kr_capital_gains_rate_respected(self):
        """kr_capital_gains_rate=0.0이 기본값으로 대체되지 않아야 함"""
        calc = TaxCalculator(kr_capital_gains_rate=0.0)
        assert calc.kr_capital_gains_rate == 0.0
