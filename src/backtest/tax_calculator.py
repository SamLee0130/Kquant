"""
세금 계산 모듈

배당소득세 및 양도소득세 계산 로직을 제공합니다.
"""
from dataclasses import dataclass
from typing import Dict, List
import pandas as pd


@dataclass
class TaxEvent:
    """세금 이벤트 기록"""
    date: pd.Timestamp
    tax_type: str  # 'dividend' 또는 'capital_gains'
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
    """
    
    def __init__(
        self,
        dividend_tax_rate: float = 0.15,
        capital_gains_tax_rate: float = 0.22,
        capital_gains_exemption: float = 2000.0
    ):
        """
        Args:
            dividend_tax_rate: 배당소득세율 (기본 15%)
            capital_gains_tax_rate: 양도소득세율 (기본 22%)
            capital_gains_exemption: 양도소득세 기본공제액 (기본 $2,000)
        """
        self.dividend_tax_rate = dividend_tax_rate
        self.capital_gains_tax_rate = capital_gains_tax_rate
        self.capital_gains_exemption = capital_gains_exemption
        
        # 세금 이벤트 히스토리
        self.tax_history: List[TaxEvent] = []
        
        # 연도별 양도차익 누적 (연말 정산용)
        self.annual_capital_gains: Dict[int, float] = {}
        
        # 연도별 양도소득세 (다음해 차감용)
        self.annual_capital_gains_tax: Dict[int, float] = {}
    
    def calculate_dividend_tax(
        self,
        dividend_amount: float,
        date: pd.Timestamp
    ) -> TaxEvent:
        """배당소득세 계산
        
        배당금 수령 시 즉시 세금을 차감합니다.
        
        Args:
            dividend_amount: 배당금 (세전)
            date: 배당금 수령일
            
        Returns:
            세금 이벤트 (세전/세후 금액 포함)
        """
        tax_amount = dividend_amount * self.dividend_tax_rate
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
        date: pd.Timestamp
    ) -> None:
        """양도차익 기록
        
        매도 시 발생한 양도차익을 연도별로 누적합니다.
        연말에 정산하여 다음해에 세금을 차감합니다.
        
        Args:
            gain_amount: 양도차익 (손실이면 음수)
            date: 거래일
        """
        year = date.year
        if year not in self.annual_capital_gains:
            self.annual_capital_gains[year] = 0.0
        self.annual_capital_gains[year] += gain_amount
    
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
        """총 양도소득세 조회"""
        return sum(self.annual_capital_gains_tax.values())
    
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

