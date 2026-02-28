"""
TaxCalculator 단위 테스트

배당소득세, 양도소득세 계산 로직을 검증합니다.
"""
import pytest
import pandas as pd

from src.backtest.tax_calculator import TaxCalculator, TaxEvent


class TestCalculateDividendTax:
    """배당소득세 계산 테스트"""

    def test_basic_dividend_tax(self):
        """기본 배당소득세 15% 적용"""
        calc = TaxCalculator(dividend_tax_rate=0.15)
        event = calc.calculate_dividend_tax(1000.0, pd.Timestamp("2024-03-15"))

        assert event.gross_amount == 1000.0
        assert event.tax_amount == pytest.approx(150.0)
        assert event.net_amount == pytest.approx(850.0)

    def test_tax_event_fields(self):
        """TaxEvent 필드가 올바르게 설정되는지 확인"""
        calc = TaxCalculator(dividend_tax_rate=0.15)
        event = calc.calculate_dividend_tax(500.0, pd.Timestamp("2024-06-01"))

        assert event.date == pd.Timestamp("2024-06-01")
        assert event.tax_type == "dividend"
        assert event.gross_amount == 500.0
        assert event.tax_amount == pytest.approx(75.0)
        assert event.net_amount == pytest.approx(425.0)

    def test_dividend_tax_added_to_history(self):
        """배당세 이벤트가 히스토리에 추가되는지 확인"""
        calc = TaxCalculator()
        calc.calculate_dividend_tax(100.0, pd.Timestamp("2024-01-15"))
        calc.calculate_dividend_tax(200.0, pd.Timestamp("2024-04-15"))

        assert len(calc.tax_history) == 2
        assert calc.tax_history[0].gross_amount == 100.0
        assert calc.tax_history[1].gross_amount == 200.0

    def test_zero_dividend(self):
        """배당금 0원일 때 세금도 0"""
        calc = TaxCalculator()
        event = calc.calculate_dividend_tax(0.0, pd.Timestamp("2024-01-01"))

        assert event.tax_amount == 0.0
        assert event.net_amount == 0.0

    def test_custom_tax_rate(self):
        """커스텀 배당세율 적용"""
        calc = TaxCalculator(dividend_tax_rate=0.20)
        event = calc.calculate_dividend_tax(1000.0, pd.Timestamp("2024-01-01"))

        assert event.tax_amount == pytest.approx(200.0)
        assert event.net_amount == pytest.approx(800.0)


class TestRecordCapitalGain:
    """양도차익 기록 테스트"""

    def test_positive_gain(self):
        """양도차익(이익) 기록"""
        calc = TaxCalculator()
        calc.record_capital_gain(5000.0, pd.Timestamp("2024-06-15"))

        assert calc.annual_capital_gains[2024] == pytest.approx(5000.0)

    def test_negative_gain(self):
        """양도차손(손실) 기록"""
        calc = TaxCalculator()
        calc.record_capital_gain(-3000.0, pd.Timestamp("2024-06-15"))

        assert calc.annual_capital_gains[2024] == pytest.approx(-3000.0)

    def test_accumulation_within_year(self):
        """같은 연도 내 양도차익 누적"""
        calc = TaxCalculator()
        calc.record_capital_gain(3000.0, pd.Timestamp("2024-03-15"))
        calc.record_capital_gain(2000.0, pd.Timestamp("2024-06-15"))
        calc.record_capital_gain(-1000.0, pd.Timestamp("2024-09-15"))

        assert calc.annual_capital_gains[2024] == pytest.approx(4000.0)

    def test_separate_years(self):
        """다른 연도는 별도로 누적"""
        calc = TaxCalculator()
        calc.record_capital_gain(5000.0, pd.Timestamp("2023-06-15"))
        calc.record_capital_gain(3000.0, pd.Timestamp("2024-06-15"))

        assert calc.annual_capital_gains[2023] == pytest.approx(5000.0)
        assert calc.annual_capital_gains[2024] == pytest.approx(3000.0)


class TestSettleAnnualCapitalGainsTax:
    """연간 양도소득세 정산 테스트"""

    def test_basic_settlement(self):
        """기본 양도소득세 정산: (gain - 2000) * 0.22"""
        calc = TaxCalculator(capital_gains_tax_rate=0.22, capital_gains_exemption=2000.0)
        calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        # (10000 - 2000) * 0.22 = 1760
        assert tax == pytest.approx(1760.0)

    def test_exemption_applied(self):
        """기본공제 $2,000 적용 확인"""
        calc = TaxCalculator(capital_gains_tax_rate=0.22, capital_gains_exemption=2000.0)
        calc.record_capital_gain(2500.0, pd.Timestamp("2024-06-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        # (2500 - 2000) * 0.22 = 110
        assert tax == pytest.approx(110.0)

    def test_gain_below_exemption(self):
        """양도차익이 공제액 이하이면 세금 0"""
        calc = TaxCalculator(capital_gains_exemption=2000.0)
        calc.record_capital_gain(1500.0, pd.Timestamp("2024-06-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        assert tax == 0.0

    def test_gain_exactly_exemption(self):
        """양도차익이 정확히 공제액과 같으면 세금 0"""
        calc = TaxCalculator(capital_gains_exemption=2000.0)
        calc.record_capital_gain(2000.0, pd.Timestamp("2024-06-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        assert tax == 0.0

    def test_loss_netting(self):
        """손익통산: 이익과 손실 합산"""
        calc = TaxCalculator(capital_gains_tax_rate=0.22, capital_gains_exemption=2000.0)
        calc.record_capital_gain(8000.0, pd.Timestamp("2024-03-15"))
        calc.record_capital_gain(-3000.0, pd.Timestamp("2024-09-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        # net gain = 8000 - 3000 = 5000, taxable = 5000 - 2000 = 3000
        # tax = 3000 * 0.22 = 660
        assert tax == pytest.approx(660.0)

    def test_loss_netting_results_in_no_tax(self):
        """손익통산 후 순손실이면 세금 0"""
        calc = TaxCalculator()
        calc.record_capital_gain(3000.0, pd.Timestamp("2024-03-15"))
        calc.record_capital_gain(-5000.0, pd.Timestamp("2024-09-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        assert tax == 0.0

    def test_loss_only_year(self):
        """손실만 있는 해는 세금 0"""
        calc = TaxCalculator()
        calc.record_capital_gain(-10000.0, pd.Timestamp("2024-06-15"))

        tax = calc.settle_annual_capital_gains_tax(2024)

        assert tax == 0.0

    def test_tax_event_recorded_on_dec_31(self):
        """양도소득세 이벤트가 12월 31일에 기록"""
        calc = TaxCalculator()
        calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))

        calc.settle_annual_capital_gains_tax(2024)

        assert len(calc.tax_history) == 1
        event = calc.tax_history[0]
        assert event.date == pd.Timestamp("2024-12-31")
        assert event.tax_type == "capital_gains"

    def test_no_event_when_no_tax(self):
        """세금이 0이면 이벤트 기록 안 함"""
        calc = TaxCalculator()
        calc.record_capital_gain(1000.0, pd.Timestamp("2024-06-15"))

        calc.settle_annual_capital_gains_tax(2024)

        assert len(calc.tax_history) == 0

    def test_no_gains_recorded_for_year(self):
        """해당 연도에 거래가 없으면 세금 0"""
        calc = TaxCalculator()
        tax = calc.settle_annual_capital_gains_tax(2024)

        assert tax == 0.0

    def test_tax_stored_in_annual_dict(self):
        """정산된 세금이 annual_capital_gains_tax에 저장"""
        calc = TaxCalculator(capital_gains_tax_rate=0.22, capital_gains_exemption=2000.0)
        calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))

        calc.settle_annual_capital_gains_tax(2024)

        assert calc.annual_capital_gains_tax[2024] == pytest.approx(1760.0)


class TestGetDeferredTax:
    """이연 양도소득세 조회 테스트"""

    def test_deferred_tax_from_previous_year(self):
        """전년도 세금이 올해 이연세로 반환"""
        calc = TaxCalculator(capital_gains_tax_rate=0.22, capital_gains_exemption=2000.0)
        calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))
        calc.settle_annual_capital_gains_tax(2024)

        deferred = calc.get_deferred_tax(2025)

        assert deferred == pytest.approx(1760.0)

    def test_no_deferred_tax_when_no_previous_year(self):
        """전년도 세금이 없으면 0"""
        calc = TaxCalculator()
        deferred = calc.get_deferred_tax(2025)

        assert deferred == 0.0


class TestAggregations:
    """세금 합계 조회 테스트"""

    def setup_method(self):
        self.calc = TaxCalculator(
            dividend_tax_rate=0.15,
            capital_gains_tax_rate=0.22,
            capital_gains_exemption=2000.0
        )
        # 배당세: 1000 * 0.15 = 150
        self.calc.calculate_dividend_tax(1000.0, pd.Timestamp("2024-03-15"))
        # 배당세: 500 * 0.15 = 75
        self.calc.calculate_dividend_tax(500.0, pd.Timestamp("2024-06-15"))
        # 양도소득세: (10000 - 2000) * 0.22 = 1760
        self.calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))
        self.calc.settle_annual_capital_gains_tax(2024)

    def test_total_dividend_tax(self):
        assert self.calc.get_total_dividend_tax() == pytest.approx(225.0)

    def test_total_capital_gains_tax(self):
        assert self.calc.get_total_capital_gains_tax() == pytest.approx(1760.0)

    def test_total_tax(self):
        assert self.calc.get_total_tax() == pytest.approx(1985.0)


class TestGetTaxHistoryDf:
    """세금 히스토리 DataFrame 테스트"""

    def test_empty_history(self):
        """이벤트 없으면 빈 DataFrame"""
        calc = TaxCalculator()
        df = calc.get_tax_history_df()

        assert isinstance(df, pd.DataFrame)
        assert len(df) == 0
        assert list(df.columns) == ["date", "tax_type", "gross_amount", "tax_amount", "net_amount"]

    def test_dataframe_structure(self):
        """DataFrame 구조 확인"""
        calc = TaxCalculator()
        calc.calculate_dividend_tax(1000.0, pd.Timestamp("2024-03-15"))
        calc.record_capital_gain(10000.0, pd.Timestamp("2024-06-15"))
        calc.settle_annual_capital_gains_tax(2024)

        df = calc.get_tax_history_df()

        assert len(df) == 2
        assert set(df.columns) == {"date", "tax_type", "gross_amount", "tax_amount", "net_amount"}
        assert df.iloc[0]["tax_type"] == "dividend"
        assert df.iloc[1]["tax_type"] == "capital_gains"


class TestReset:
    """초기화 테스트"""

    def test_reset_clears_all_state(self):
        """reset()이 모든 상태를 초기화"""
        calc = TaxCalculator()
        calc.calculate_dividend_tax(1000.0, pd.Timestamp("2024-03-15"))
        calc.record_capital_gain(5000.0, pd.Timestamp("2024-06-15"))
        calc.settle_annual_capital_gains_tax(2024)

        calc.reset()

        assert calc.tax_history == []
        assert calc.annual_capital_gains == {}
        assert calc.annual_capital_gains_tax == {}
        assert calc.get_total_tax() == 0.0
