"""
세금 계산 모듈

배당소득세 및 양도소득세 계산 로직을 제공합니다.

시장별 세금 규칙:
- US (해외 상장): 배당세 15%, 양도소득세 22% 연말 이연, 기본공제 $2,000
- KR_STOCK (국내 주식형): 배당세 15.4%, 양도차익 비과세
- KR_OTHER (국내 기타): 배당세 15.4%, 매매차익 배당소득세 15.4% 즉시
"""
from dataclasses import dataclass
from typing import Dict, List, Optional
import pandas as pd

from src.data.etf_classifier import Market
from config.settings import KOREAN_TAX_DEFAULTS


@dataclass
class TaxEvent:
    """세금 이벤트 기록"""
    date: pd.Timestamp
    tax_type: str  # 'dividend', 'capital_gains', 'kr_capital_gains'
    gross_amount: float  # 세전 금액
    tax_amount: float  # 세금 금액
    net_amount: float  # 세후 금액


class TaxCalculator:
    """세금 계산기

    배당소득세와 양도소득세를 계산합니다.
    - 배당소득세: 배당금 수령 시 즉시 차감
    - 양도소득세: 연말 정산 후 다음해 포트폴리오에서 차감
      - 연간 모든 종목의 수익/손실을 합산
      - 기본공제액($2,000)을 초과하는 금액에만 과세

    한국 상장 ETF 세금 규칙:
    - KR_STOCK: 배당세 15.4%, 양도차익 비과세
    - KR_OTHER: 배당세 15.4%, 매매차익 배당소득세 15.4% 즉시 과세
    """

    def __init__(
        self,
        dividend_tax_rate: float = 0.15,
        capital_gains_tax_rate: float = 0.22,
        capital_gains_exemption: float = 2000.0,
        kr_dividend_tax_rate: float = None,
        kr_capital_gains_rate: float = None
    ):
        """
        Args:
            dividend_tax_rate: 해외 ETF 배당소득세율 (기본 15%)
            capital_gains_tax_rate: 해외 ETF 양도소득세율 (기본 22%)
            capital_gains_exemption: 해외 ETF 양도소득세 기본공제액 (기본 $2,000)
            kr_dividend_tax_rate: 국내 ETF 배당소득세율 (기본 15.4%)
            kr_capital_gains_rate: 국내 기타 ETF 매매차익 세율 (기본 15.4%)
        """
        self.dividend_tax_rate = dividend_tax_rate
        self.capital_gains_tax_rate = capital_gains_tax_rate
        self.capital_gains_exemption = capital_gains_exemption
        self.kr_dividend_tax_rate = kr_dividend_tax_rate or KOREAN_TAX_DEFAULTS["kr_dividend_tax_rate"]
        self.kr_capital_gains_rate = kr_capital_gains_rate or KOREAN_TAX_DEFAULTS["kr_other_capital_gains_rate"]

        # 세금 이벤트 히스토리
        self.tax_history: List[TaxEvent] = []

        # 연도별 양도차익 누적 (연말 정산용 - US ETF만)
        self.annual_capital_gains: Dict[int, float] = {}

        # 연도별 양도소득세 (다음해 차감용)
        self.annual_capital_gains_tax: Dict[int, float] = {}

    def _get_dividend_tax_rate(self, market: Optional[Market]) -> float:
        """시장별 배당소득세율 반환"""
        if market in (Market.KR_STOCK, Market.KR_OTHER):
            return self.kr_dividend_tax_rate
        return self.dividend_tax_rate

    def calculate_dividend_tax(
        self,
        dividend_amount: float,
        date: pd.Timestamp,
        market: Optional[Market] = None
    ) -> TaxEvent:
        """배당소득세 계산

        배당금 수령 시 즉시 세금을 차감합니다.

        Args:
            dividend_amount: 배당금 (세전)
            date: 배당금 수령일
            market: ETF 시장 유형 (None이면 US 기본 세율 적용)

        Returns:
            세금 이벤트 (세전/세후 금액 포함)
        """
        rate = self._get_dividend_tax_rate(market)
        tax_amount = dividend_amount * rate
        net_amount = dividend_amount - tax_amount

        event = TaxEvent(
            date=date,
            tax_type='dividend',
            gross_amount=dividend_amount,
            tax_amount=tax_amount,
            net_amount=net_amount
        )

        self.tax_history.append(event)
        return event

    def record_capital_gain(
        self,
        gain_amount: float,
        date: pd.Timestamp,
        market: Optional[Market] = None
    ) -> Optional[TaxEvent]:
        """양도차익 기록

        시장 유형에 따라 다르게 처리:
        - US (None): 연도별 누적 → 연말 정산 (기존 로직)
        - KR_STOCK: 비과세 (no-op)
        - KR_OTHER: 즉시 15.4% 과세 → TaxEvent 반환

        Args:
            gain_amount: 양도차익 (손실이면 음수)
            date: 거래일
            market: ETF 시장 유형

        Returns:
            KR_OTHER의 경우 즉시 과세 TaxEvent, 그 외 None
        """
        # 국내 주식형 ETF: 양도차익 비과세
        if market == Market.KR_STOCK:
            return None

        # 국내 기타 ETF: 매매차익에 대해 즉시 15.4% 과세 (배당소득 간주)
        if market == Market.KR_OTHER:
            if gain_amount > 0:
                tax_amount = gain_amount * self.kr_capital_gains_rate
                event = TaxEvent(
                    date=date,
                    tax_type='kr_capital_gains',
                    gross_amount=gain_amount,
                    tax_amount=tax_amount,
                    net_amount=gain_amount - tax_amount
                )
                self.tax_history.append(event)
                return event
            return None

        # US (해외 상장 ETF): 기존 로직 - 연도별 누적
        year = date.year
        if year not in self.annual_capital_gains:
            self.annual_capital_gains[year] = 0.0
        self.annual_capital_gains[year] += gain_amount
        return None
    
    def settle_annual_capital_gains_tax(self, year: int) -> float:
        """연간 양도소득세 정산
        
        해당 연도의 양도차익에 대한 세금을 계산합니다.
        - 모든 종목의 수익과 손실을 합산
        - 기본공제액을 초과하는 금액에만 과세
        - 계산된 세금은 다음해 1월에 포트폴리오에서 차감됩니다.
        
        Args:
            year: 정산 연도
            
        Returns:
            양도소득세 금액 (공제 후 과세표준이 0 이하면 0)
        """
        total_gain = self.annual_capital_gains.get(year, 0.0)
        
        # 기본공제 적용: 양도차익에서 공제액을 뺀 금액이 과세표준
        # 손실이거나 공제액 이하면 세금 없음
        taxable_gain = max(0, total_gain - self.capital_gains_exemption)
        
        if taxable_gain > 0:
            tax_amount = taxable_gain * self.capital_gains_tax_rate
        else:
            tax_amount = 0.0
        
        self.annual_capital_gains_tax[year] = tax_amount
        
        # 세금 이벤트 기록
        if tax_amount > 0:
            event = TaxEvent(
                date=pd.Timestamp(year=year, month=12, day=31),
                tax_type='capital_gains',
                gross_amount=total_gain,
                tax_amount=tax_amount,
                net_amount=total_gain - tax_amount
            )
            self.tax_history.append(event)
        
        return tax_amount
    
    def get_deferred_tax(self, year: int) -> float:
        """이연된 양도소득세 조회
        
        전년도에 정산된 양도소득세를 조회합니다.
        이 금액은 해당 연도 1월에 포트폴리오에서 차감됩니다.
        
        Args:
            year: 현재 연도
            
        Returns:
            전년도 양도소득세 금액
        """
        previous_year = year - 1
        return self.annual_capital_gains_tax.get(previous_year, 0.0)
    
    def get_total_dividend_tax(self) -> float:
        """총 배당소득세 조회"""
        return sum(
            event.tax_amount 
            for event in self.tax_history 
            if event.tax_type == 'dividend'
        )
    
    def get_total_capital_gains_tax(self) -> float:
        """총 양도소득세 조회 (US 이연 + KR_OTHER 즉시)"""
        us_tax = sum(self.annual_capital_gains_tax.values())
        kr_tax = sum(
            event.tax_amount
            for event in self.tax_history
            if event.tax_type == 'kr_capital_gains'
        )
        return us_tax + kr_tax

    def get_total_tax(self) -> float:
        """총 세금 조회"""
        return self.get_total_dividend_tax() + self.get_total_capital_gains_tax()
    
    def get_tax_history_df(self) -> pd.DataFrame:
        """세금 히스토리 DataFrame 반환"""
        if not self.tax_history:
            return pd.DataFrame(columns=[
                'date', 'tax_type', 'gross_amount', 'tax_amount', 'net_amount'
            ])
        
        return pd.DataFrame([
            {
                'date': e.date,
                'tax_type': e.tax_type,
                'gross_amount': e.gross_amount,
                'tax_amount': e.tax_amount,
                'net_amount': e.net_amount
            }
            for e in self.tax_history
        ])
    
    def reset(self) -> None:
        """세금 계산기 초기화"""
        self.tax_history = []
        self.annual_capital_gains = {}
        self.annual_capital_gains_tax = {}

