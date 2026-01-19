"""
포트폴리오 백테스트 엔진

자산 배분 전략의 백테스팅을 수행합니다.
리밸런싱, 인출, 배당금, 세금을 고려한 시뮬레이션을 제공합니다.
"""
import pandas as pd
import numpy as np
import yfinance as yf
from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timedelta
import logging

from .tax_calculator import TaxCalculator

logger = logging.getLogger(__name__)


@dataclass
class PortfolioSnapshot:
    """포트폴리오 스냅샷"""
    date: pd.Timestamp
    holdings: Dict[str, float]  # 종목별 보유 수량
    prices: Dict[str, float]  # 종목별 가격
    cash: float  # 현금
    total_value: float  # 총 자산 가치
    cumulative_withdrawal: float  # 누적 인출금
    cumulative_dividend: float  # 누적 배당금 (세후)
    cumulative_tax: float  # 누적 세금


@dataclass
class BacktestResult:
    """백테스트 결과"""
    # 포트폴리오 히스토리
    portfolio_history: List[PortfolioSnapshot]
    
    # 이벤트 로그
    rebalance_events: List[Dict]
    withdrawal_events: List[Dict]
    dividend_events: List[Dict]
    tax_events: List[Dict]
    
    # 성과 지표
    initial_value: float
    final_value: float
    total_return: float
    cagr: float
    volatility: float
    sharpe_ratio: float
    max_drawdown: float
    
    # 인출/배당/세금/거래비용 요약
    total_withdrawal: float
    total_dividend_gross: float
    total_dividend_net: float
    total_tax: float
    total_transaction_cost: float


class PortfolioBacktester:
    """포트폴리오 백테스터
    
    자산 배분 전략의 백테스팅을 수행합니다.
    """
    
    def __init__(
        self,
        initial_capital: float = 1_000_000,
        allocation: Dict[str, float] = None,
        rebalance_frequency: str = 'quarterly',  # 'quarterly' 또는 'yearly'
        withdrawal_rate: float = 0.05,  # 연간 인출률 (5%)
        dividend_tax_rate: float = 0.15,  # 배당소득세 (15%)
        capital_gains_tax_rate: float = 0.22,  # 양도소득세 (22%)
        capital_gains_exemption: float = 2000.0,  # 양도소득세 기본공제 ($2,000)
        transaction_cost_rate: float = 0.002  # 거래비용 (0.2%)
    ):
        """
        Args:
            initial_capital: 초기 자본금 (USD)
            allocation: 자산 배분 비율 (예: {'SPY': 0.6, 'QQQ': 0.3, 'BIL': 0.1})
            rebalance_frequency: 리밸런싱 주기 ('quarterly' 또는 'yearly')
            withdrawal_rate: 연간 인출률 (0.05 = 5%)
            dividend_tax_rate: 배당소득세율 (0.15 = 15%)
            capital_gains_tax_rate: 양도소득세율 (0.22 = 22%)
            capital_gains_exemption: 양도소득세 기본공제액 (기본 $2,000)
            transaction_cost_rate: 거래비용률 - 거래수수료 + 슬리피지 (0.002 = 0.2%)
        """
        self.initial_capital = initial_capital
        self.allocation = allocation or {'SPY': 0.60, 'QQQ': 0.30, 'BIL': 0.10}
        self.rebalance_frequency = rebalance_frequency
        self.withdrawal_rate = withdrawal_rate
        self.transaction_cost_rate = transaction_cost_rate
        
        # 세금 계산기 초기화
        self.tax_calculator = TaxCalculator(
            dividend_tax_rate=dividend_tax_rate,
            capital_gains_tax_rate=capital_gains_tax_rate,
            capital_gains_exemption=capital_gains_exemption
        )
        
        # 데이터 캐시
        self._price_data: Dict[str, pd.DataFrame] = {}
        self._dividend_data: Dict[str, pd.DataFrame] = {}
        
        # 포트폴리오 상태
        self.holdings: Dict[str, float] = {}  # 종목별 보유 수량
        self.cost_basis: Dict[str, float] = {}  # 종목별 평균 매수단가
        self.cash: float = 0.0
        
        # 이벤트 로그
        self.rebalance_events: List[Dict] = []
        self.withdrawal_events: List[Dict] = []
        self.dividend_events: List[Dict] = []
        
        # 누적 거래비용
        self.total_transaction_cost: float = 0.0
        
    def _fetch_data(self, symbols: List[str], start_date: datetime, end_date: datetime) -> None:
        """yfinance로 가격 및 배당금 데이터 수집"""
        # 비교 기준 날짜를 tz-naive로 통일
        start_ts = pd.Timestamp(start_date)
        start_ts = start_ts.tz_convert(None) if start_ts.tz is not None else start_ts.tz_localize(None)
        end_ts = pd.Timestamp(end_date)
        end_ts = end_ts.tz_convert(None) if end_ts.tz is not None else end_ts.tz_localize(None)

        for symbol in symbols:
            logger.info(f"{symbol} 데이터 수집 중...")
            ticker = yf.Ticker(symbol)
            
            # 가격 데이터
            hist = ticker.history(start=start_date, end=end_date, auto_adjust=False)
            if hist.empty:
                raise ValueError(f"{symbol} 가격 데이터를 찾을 수 없습니다.")
            
            # 타임존 제거 (timezone-naive로 변환)
            hist.index = pd.DatetimeIndex(hist.index)
            if hist.index.tz is not None:
                hist.index = hist.index.tz_convert(None)
            
            self._price_data[symbol] = hist[['Close']].copy()
            self._price_data[symbol].columns = ['price']
            
            # 배당금 데이터
            dividends = ticker.dividends
            if not dividends.empty:
                dividends.index = pd.DatetimeIndex(dividends.index)
                if dividends.index.tz is not None:
                    dividends.index = dividends.index.tz_convert(None)
                # 시작/종료일 기준 배당금만 필터링
                dividends = dividends[(dividends.index >= start_ts) & (dividends.index <= end_ts)]
            self._dividend_data[symbol] = dividends
            
            logger.info(f"{symbol}: {len(hist)} 거래일, {len(dividends)} 배당 이벤트")
    
    def _get_price(self, symbol: str, date: pd.Timestamp) -> Optional[float]:
        """특정 날짜의 가격 조회 (없으면 직후 거래일 종가 우선, 그다음 직전)"""
        if symbol not in self._price_data:
            return None
        
        df = self._price_data[symbol]
        
        # 직후(해당일 포함) 첫 거래일 종가를 우선 사용
        future_mask = df.index >= date
        if future_mask.any():
            return df.loc[future_mask, 'price'].iloc[0]
        
        # 미래에 없으면 직전 거래일 종가 사용
        past_mask = df.index <= date
        if past_mask.any():
            return df.loc[past_mask, 'price'].iloc[-1]
        
        return None
    
    def _get_dividends(self, symbol: str, start_date: pd.Timestamp, end_date: pd.Timestamp) -> pd.Series:
        """기간 내 배당금 조회"""
        if symbol not in self._dividend_data:
            return pd.Series(dtype=float)
        
        dividends = self._dividend_data[symbol]
        # 혹시 남아 있을지 모르는 tz 정보 제거
        if hasattr(dividends.index, "tz") and dividends.index.tz is not None:
            dividends.index = dividends.index.tz_convert(None)
        # 비교 기준도 tz-naive로 강제
        start_date = pd.Timestamp(start_date).tz_localize(None)
        end_date = pd.Timestamp(end_date).tz_localize(None)
        mask = (dividends.index >= start_date) & (dividends.index <= end_date)
        return dividends[mask]
    
    def _get_portfolio_value(self, date: pd.Timestamp) -> float:
        """포트폴리오 총 가치 계산"""
        total = self.cash
        for symbol, shares in self.holdings.items():
            price = self._get_price(symbol, date)
            if price:
                total += shares * price
        return total
    
    def _get_rebalance_dates(self, start_date: datetime, end_date: datetime) -> List[pd.Timestamp]:
        """리밸런싱 날짜 목록 생성"""
        dates = []
        current = pd.Timestamp(start_date)
        end = pd.Timestamp(end_date)
        
        if self.rebalance_frequency == 'quarterly':
            # 분기 시작일 (1월, 4월, 7월, 10월 첫날)
            while current <= end:
                month = ((current.month - 1) // 3) * 3 + 1
                quarter_start = pd.Timestamp(year=current.year, month=month, day=1)
                if quarter_start >= pd.Timestamp(start_date) and quarter_start <= end:
                    if quarter_start not in dates:
                        dates.append(quarter_start)
                # 다음 분기로 이동
                if month == 10:
                    current = pd.Timestamp(year=current.year + 1, month=1, day=1)
                else:
                    current = pd.Timestamp(year=current.year, month=month + 3, day=1)
        else:  # yearly
            # 연 시작일 (1월 1일)
            while current <= end:
                year_start = pd.Timestamp(year=current.year, month=1, day=1)
                if year_start >= pd.Timestamp(start_date) and year_start <= end:
                    if year_start not in dates:
                        dates.append(year_start)
                current = pd.Timestamp(year=current.year + 1, month=1, day=1)
        
        return sorted(dates)
    
    def _rebalance(self, date: pd.Timestamp) -> Dict:
        """리밸런싱 실행"""
        total_value = self._get_portfolio_value(date)
        
        trades = []
        total_gain = 0.0
        total_trade_cost = 0.0
        total_traded_value = 0.0  # 거래된 금액 합계 (매수/매도 절대값)
        
        for symbol, target_weight in self.allocation.items():
            price = self._get_price(symbol, date)
            if not price:
                continue
            
            current_shares = self.holdings.get(symbol, 0)
            current_value = current_shares * price
            target_value = total_value * target_weight
            diff_value = target_value - current_value
            
            if abs(diff_value) > 1:  # $1 이상 차이가 있을 때만 거래
                shares_to_trade = diff_value / price
                traded_value = shares_to_trade * price  # 양수=매수, 음수=매도
                
                # 매도 시 양도차익 계산
                if shares_to_trade < 0:
                    avg_cost = self.cost_basis.get(symbol, price)
                    gain = abs(shares_to_trade) * (price - avg_cost)
                    total_gain += gain
                    self.tax_calculator.record_capital_gain(gain, date)
                
                # 현금 업데이트 (매수 시 현금 감소, 매도 시 현금 증가)
                self.cash -= traded_value
                total_traded_value += abs(traded_value)
                
                # 보유량 업데이트
                new_shares = current_shares + shares_to_trade
                self.holdings[symbol] = max(0, new_shares)
                
                # 평균 매수단가 업데이트 (매수 시)
                if shares_to_trade > 0:
                    old_cost = self.cost_basis.get(symbol, 0) * current_shares
                    new_cost = shares_to_trade * price
                    self.cost_basis[symbol] = (old_cost + new_cost) / new_shares if new_shares > 0 else price
                
                # 거래비용(추후 일괄 차감) 계산
                trade_cost = abs(traded_value) * self.transaction_cost_rate
                total_trade_cost += trade_cost
                
                trades.append({
                    'symbol': symbol,
                    'shares': shares_to_trade,
                    'price': price,
                    'value': diff_value,
                    'transaction_cost': trade_cost,
                    'current_shares': current_shares,
                    'target_shares': current_shares + shares_to_trade
                })
        
        # 거래가 있었을 때만 거래비용 차감
        if total_traded_value > 0:
            self.cash -= total_trade_cost
            self.total_transaction_cost += total_trade_cost
        
        event = {
            'date': date,
            'portfolio_value': total_value,
            'trades': trades,
            'capital_gain': total_gain,
            'transaction_cost': total_trade_cost
        }
        self.rebalance_events.append(event)
        return event
    
    def _process_withdrawal(self, date: pd.Timestamp, dividend_cash: float) -> Dict:
        """인출 처리
        
        분기별 인출: 연간 인출률 / 4
        배당금이 있으면 우선 사용, 부족분은 포트폴리오에서 매도
        """
        # 분기별 인출액 (연 5% / 4 = 1.25%)
        if self.rebalance_frequency == 'quarterly':
            withdrawal_rate = self.withdrawal_rate / 4
        else:
            withdrawal_rate = self.withdrawal_rate
        
        portfolio_value = self._get_portfolio_value(date)
        target_withdrawal = portfolio_value * withdrawal_rate
        
        # 인출 전 현금(배당 포함)에서 먼저 사용
        from_cash = min(self.cash, target_withdrawal)
        self.cash -= from_cash
        remaining = target_withdrawal - from_cash
        
        from_portfolio = 0.0
        trade_cost = 0.0
        
        # 부족분은 포트폴리오 비례 매도 → 현금 유입 후 인출
        if remaining > 0:
            for symbol, shares in list(self.holdings.items()):
                if remaining <= 0:
                    break
                
                price = self._get_price(symbol, date)
                if not price or shares <= 0:
                    continue
                
                weight = self.allocation.get(symbol, 0)
                sell_value = remaining * weight
                sell_shares = min(sell_value / price, shares)
                
                if sell_shares > 0:
                    avg_cost = self.cost_basis.get(symbol, price)
                    gain = sell_shares * (price - avg_cost)
                    self.tax_calculator.record_capital_gain(gain, date)
                    
                    sell_amount = sell_shares * price
                    cost = sell_amount * self.transaction_cost_rate
                    trade_cost += cost
                    
                    self.holdings[symbol] -= sell_shares
                    
                    from_portfolio += sell_amount
                    remaining -= sell_amount
                    
                    # 매도 대금을 현금에 더하고, 인출은 전체 target에서 이미 차감됨
                    self.cash += sell_amount
        
        # 인출 금액 차감 (매도/현금 합쳐서 target_withdrawal만큼 감소)
        self.cash -= remaining if remaining > 0 else 0  # 남은 부분도 차감
        
        # 거래비용 차감
        self.cash -= trade_cost
        self.total_transaction_cost += trade_cost
        
        event = {
            'date': date,
            'target_withdrawal': target_withdrawal,
            'from_dividend': from_cash,  # 현금(배당 포함) 사용분
            'from_portfolio': from_portfolio,
            'total_withdrawal': target_withdrawal,
            'transaction_cost': trade_cost
        }
        self.withdrawal_events.append(event)
        return event
    
    def _process_dividends(self, start_date: pd.Timestamp, end_date: pd.Timestamp) -> float:
        """기간 내 배당금 처리
        
        배당소득세를 차감한 순 배당금을 반환합니다.
        """
        total_net_dividend = 0.0
        
        for symbol, shares in self.holdings.items():
            if shares <= 0:
                continue
            
            dividends = self._get_dividends(symbol, start_date, end_date)
            
            for div_date, div_per_share in dividends.items():
                gross_dividend = shares * div_per_share
                tax_event = self.tax_calculator.calculate_dividend_tax(gross_dividend, div_date)
                net_dividend = tax_event.net_amount
                total_net_dividend += net_dividend
                
                self.dividend_events.append({
                    'date': div_date,
                    'symbol': symbol,
                    'shares': shares,
                    'div_per_share': div_per_share,
                    'gross_dividend': gross_dividend,
                    'tax': tax_event.tax_amount,
                    'net_dividend': net_dividend
                })
        
        # 배당금 현금 유입
        self.cash += total_net_dividend
        return total_net_dividend
    
    def _process_year_end_tax(self, year: int, date: pd.Timestamp) -> float:
        """연말 양도소득세 정산"""
        tax = self.tax_calculator.settle_annual_capital_gains_tax(year)
        return tax
    
    def _apply_deferred_tax(self, year: int) -> float:
        """이연된 양도소득세 차감 (1월)
        
        전년도 양도소득세를 포트폴리오에서 현금으로 차감합니다.
        현금이 부족하면 비례 매도합니다.
        """
        tax = self.tax_calculator.get_deferred_tax(year)
        if tax <= 0:
            return 0.0
        
        # 현금에서 우선 차감
        if self.cash >= tax:
            self.cash -= tax
            return tax
        
        # 부족분은 포트폴리오에서 매도
        from_cash = self.cash
        remaining = tax - from_cash
        self.cash = 0
        
        date = pd.Timestamp(year=year, month=1, day=15)  # 1월 중순 가정
        
        for symbol, shares in list(self.holdings.items()):
            if remaining <= 0:
                break
            
            price = self._get_price(symbol, date)
            if not price or shares <= 0:
                continue
            
            weight = self.allocation.get(symbol, 0)
            sell_value = remaining * weight
            sell_shares = min(sell_value / price, shares)
            
            if sell_shares > 0:
                self.holdings[symbol] -= sell_shares
                remaining -= sell_shares * price
        
        return tax
    
    def run(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        years: int = 10
    ) -> BacktestResult:
        """백테스트 실행

        Args:
            start_date: 시작일 (없으면 N년 전 1월 1일)
            end_date: 종료일 (없으면 현재 기준 가장 최근 분기 시작일)
            years: 백테스팅 기간 (start_date가 없을 때 사용)

        Returns:
            백테스트 결과
        """
        # 날짜 설정
        now = datetime.now()

        if end_date is None:
            # 현재 날짜 기준 가장 최근 분기 시작일 (1월, 4월, 7월, 10월 1일)
            current_quarter_month = ((now.month - 1) // 3) * 3 + 1
            end_date = datetime(now.year, current_quarter_month, 1)

        if start_date is None:
            # N년 전 1월 1일
            start_year = end_date.year - years
            start_date = datetime(start_year, 1, 1)

        # 타임존 혼합 방지: tz-naive로 통일
        start_date = pd.Timestamp(start_date)
        start_date = start_date.tz_convert(None) if start_date.tz is not None else start_date.tz_localize(None)
        end_date = pd.Timestamp(end_date)
        end_date = end_date.tz_convert(None) if end_date.tz is not None else end_date.tz_localize(None)
        
        logger.info(f"백테스트 기간: {start_date.date()} ~ {end_date.date()}")
        
        # 데이터 수집
        symbols = list(self.allocation.keys())
        self._fetch_data(symbols, start_date, end_date)
        
        # 초기화
        self.holdings = {}
        self.cost_basis = {}
        self.cash = self.initial_capital
        self.tax_calculator.reset()
        self.rebalance_events = []
        self.withdrawal_events = []
        self.dividend_events = []
        self.total_transaction_cost = 0.0
        
        # 리밸런싱 날짜 생성
        rebalance_dates = self._get_rebalance_dates(start_date, end_date)
        
        # 포트폴리오 히스토리
        portfolio_history: List[PortfolioSnapshot] = []
        
        # 누적 값
        cumulative_withdrawal = 0.0
        cumulative_dividend = 0.0
        cumulative_tax = 0.0

        # 배당 계산 구간 시작일 (이전 리밸런싱 이후 누적)
        last_dividend_processed_date = pd.Timestamp(start_date)
        
        # 시작 시점 스냅샷 (거래 전, 현금 100%)
        start_prices = {s: self._get_price(s, pd.Timestamp(start_date)) for s in symbols}
        start_total_value = self._get_portfolio_value(pd.Timestamp(start_date))
        portfolio_history.append(PortfolioSnapshot(
            date=pd.Timestamp(start_date),
            holdings=dict(self.holdings),
            prices=start_prices,
            cash=self.cash,
            total_value=start_total_value,
            cumulative_withdrawal=cumulative_withdrawal,
            cumulative_dividend=cumulative_dividend,
            cumulative_tax=cumulative_tax
        ))

        # 초기에는 현금만 보유; 첫 리밸런싱까지 매수하지 않음
        if not rebalance_dates:
            return BacktestResult(
                portfolio_history=[],
                rebalance_events=[],
                withdrawal_events=[],
                dividend_events=[],
                tax_events=[],
                initial_value=self.initial_capital,
                final_value=self.initial_capital,
                total_return=0.0,
                cagr=0.0,
                volatility=0.0,
                sharpe_ratio=0.0,
                max_drawdown=0.0,
                total_withdrawal=0.0,
                total_dividend_gross=0.0,
                total_dividend_net=0.0,
                total_tax=0.0,
                total_transaction_cost=0.0
            )
        
        # 모든 거래일 순회
        all_dates = self._price_data[symbols[0]].index
        prev_rebalance_date = None
        prev_year = None
        initial_invested = False
        
        for date in all_dates:
            current_year = date.year
            
            # 연초 양도소득세 납부 (1월)
            if prev_year is not None and current_year != prev_year:
                tax = self._apply_deferred_tax(current_year)
                cumulative_tax += tax
            
            # 리밸런싱 날짜인지 확인
            is_rebalance_date = False
            for rb_date in rebalance_dates:
                if date >= rb_date and (prev_rebalance_date is None or rb_date > prev_rebalance_date):
                    is_rebalance_date = True
                    prev_rebalance_date = rb_date
                    break
            
            # 리밸런싱 시점에 처리 (초기 매수 포함)
            if is_rebalance_date and prev_rebalance_date is not None:
                # 첫 리밸런싱에서 초기 매수 수행
                if not initial_invested:
                    total_invested = 0.0
                    initial_trades = []
                    for symbol, weight in self.allocation.items():
                        price = self._get_price(symbol, date)
                        if price:
                            value = self.initial_capital * weight
                            shares = value / price
                            self.holdings[symbol] = shares
                            self.cost_basis[symbol] = price
                            total_invested += value
                            initial_trades.append({
                                'symbol': symbol,
                                'shares': shares,
                                'price': price,
                                'value': value,
                                'transaction_cost': 0.0,
                                'current_shares': 0.0,
                                'target_shares': shares
                            })
                    self.cash = self.initial_capital - total_invested
                    initial_invested = True

                    # 초기 매수 이벤트 기록
                    self.rebalance_events.append({
                        'date': date,
                        'portfolio_value': self.initial_capital,
                        'trades': initial_trades,
                        'capital_gain': 0.0,
                        'transaction_cost': 0.0,
                        'is_initial_purchase': True
                    })
                
                # 이전 리밸런싱 이후부터 이번 리밸런싱 시점까지 배당금 처리
                dividend_cash = self._process_dividends(last_dividend_processed_date, date)
                cumulative_dividend += dividend_cash
                last_dividend_processed_date = date
                
                # 인출 처리
                withdrawal_event = self._process_withdrawal(date, dividend_cash)
                cumulative_withdrawal += withdrawal_event['total_withdrawal']
                
                # 리밸런싱
                self._rebalance(date)
            
            # 연말 양도소득세 정산
            if prev_year is not None and current_year != prev_year:
                self._process_year_end_tax(prev_year, date)
            
            prev_year = current_year
            
            # 스냅샷 저장 (월별)
            if date.day <= 7:  # 매월 초에 스냅샷
                prices = {s: self._get_price(s, date) for s in symbols}
                total_value = self._get_portfolio_value(date)
                
                snapshot = PortfolioSnapshot(
                    date=date,
                    holdings=dict(self.holdings),
                    prices=prices,
                    cash=self.cash,
                    total_value=total_value,
                    cumulative_withdrawal=cumulative_withdrawal,
                    cumulative_dividend=cumulative_dividend,
                    cumulative_tax=cumulative_tax
                )
                portfolio_history.append(snapshot)
        
        # 종료일이 리밸런싱 날짜인 경우 마지막 리밸런싱 처리 (휴장일인 경우 루프에서 처리되지 않음)
        final_end_date = pd.Timestamp(end_date)
        if final_end_date in rebalance_dates and prev_rebalance_date != final_end_date:
            # 연초 양도소득세 납부 (이전 연도와 다른 경우)
            if prev_year is not None and final_end_date.year != prev_year:
                tax = self._apply_deferred_tax(final_end_date.year)
                cumulative_tax += tax

            # 배당금 처리
            dividend_cash = self._process_dividends(last_dividend_processed_date, final_end_date)
            cumulative_dividend += dividend_cash
            last_dividend_processed_date = final_end_date

            # 인출 처리
            withdrawal_event = self._process_withdrawal(final_end_date, dividend_cash)
            cumulative_withdrawal += withdrawal_event['total_withdrawal']

            # 리밸런싱
            self._rebalance(final_end_date)

            # 연말 세금 정산 (이전 연도와 다른 경우)
            if prev_year is not None and final_end_date.year != prev_year:
                self._process_year_end_tax(prev_year, final_end_date)

            prev_year = final_end_date.year
            prev_rebalance_date = final_end_date

        # 마지막 배당금 처리 (마지막 리밸런싱 이후 ~ 종료일)
        final_dividend = self._process_dividends(last_dividend_processed_date, pd.Timestamp(end_date))
        cumulative_dividend += final_dividend

        # 마지막 연도 세금 정산
        if prev_year:
            self._process_year_end_tax(prev_year, pd.Timestamp(end_date))
            # 마지막 연도의 양도소득세는 다음 해 1월에 차감되므로, 시뮬레이션 종료 시점에 미리 차감
            final_capital_tax = self._apply_deferred_tax(prev_year + 1)
            cumulative_tax += final_capital_tax
        
        # 최종 스냅샷
        final_date = pd.Timestamp(end_date)
        final_prices = {s: self._get_price(s, final_date) for s in symbols}
        final_value = self._get_portfolio_value(final_date)
        
        final_snapshot = PortfolioSnapshot(
            date=final_date,
            holdings=dict(self.holdings),
            prices=final_prices,
            cash=self.cash,
            total_value=final_value,
            cumulative_withdrawal=cumulative_withdrawal,
            cumulative_dividend=cumulative_dividend,
            cumulative_tax=self.tax_calculator.get_total_tax()
        )
        portfolio_history.append(final_snapshot)
        
        # 성과 지표 계산
        values = [s.total_value for s in portfolio_history]
        returns = pd.Series(values).pct_change().dropna()
        
        total_return = (final_value / self.initial_capital - 1) * 100
        
        # CAGR 계산
        years_elapsed = (end_date - start_date).days / 365.25
        cagr = ((final_value / self.initial_capital) ** (1 / years_elapsed) - 1) * 100 if years_elapsed > 0 else 0
        
        # 변동성 (연율화)
        volatility = returns.std() * np.sqrt(12) * 100  # 월별 데이터 기준
        
        # 샤프비율 (무위험수익률 3% 가정)
        risk_free_rate = 0.03
        excess_return = (cagr / 100) - risk_free_rate
        sharpe_ratio = excess_return / (volatility / 100) if volatility > 0 else 0
        
        # 최대 낙폭
        cummax = pd.Series(values).cummax()
        drawdown = (pd.Series(values) - cummax) / cummax
        max_drawdown = drawdown.min() * 100
        
        # 배당금 총계
        total_dividend_gross = sum(e['gross_dividend'] for e in self.dividend_events)
        total_dividend_net = sum(e['net_dividend'] for e in self.dividend_events)
        
        result = BacktestResult(
            portfolio_history=portfolio_history,
            rebalance_events=self.rebalance_events,
            withdrawal_events=self.withdrawal_events,
            dividend_events=self.dividend_events,
            tax_events=self.tax_calculator.tax_history,
            initial_value=self.initial_capital,
            final_value=final_value,
            total_return=total_return,
            cagr=cagr,
            volatility=volatility,
            sharpe_ratio=sharpe_ratio,
            max_drawdown=max_drawdown,
            total_withdrawal=cumulative_withdrawal,
            total_dividend_gross=total_dividend_gross,
            total_dividend_net=total_dividend_net,
            total_tax=self.tax_calculator.get_total_tax(),
            total_transaction_cost=self.total_transaction_cost
        )
        
        return result
    
    def get_portfolio_history_df(self, result: BacktestResult) -> pd.DataFrame:
        """포트폴리오 히스토리 DataFrame 반환"""
        records = []
        for snapshot in result.portfolio_history:
            record = {
                'date': snapshot.date,
                'total_value': snapshot.total_value,
                'cash': snapshot.cash,
                'cumulative_withdrawal': snapshot.cumulative_withdrawal,
                'cumulative_dividend': snapshot.cumulative_dividend,
                'cumulative_tax': snapshot.cumulative_tax
            }
            # 종목별 가치 추가
            for symbol, shares in snapshot.holdings.items():
                price = snapshot.prices.get(symbol, 0)
                record[f'{symbol}_shares'] = shares
                record[f'{symbol}_value'] = shares * price if price else 0
            records.append(record)
        
        return pd.DataFrame(records)
    
    def get_annual_summary_df(self, result: BacktestResult) -> pd.DataFrame:
        """연간 요약 DataFrame 반환"""
        history_df = self.get_portfolio_history_df(result)
        history_df['year'] = history_df['date'].dt.year

        # 세금 집계: 배당세는 해당 연도, 양도소득세는 다음 연도(이연 납부)로 매핑
        dividend_tax_by_year: Dict[int, float] = {}
        capital_tax_payment_by_year: Dict[int, float] = {}
        for event in result.tax_events:
            event_year = event.date.year
            if event.tax_type == 'dividend':
                dividend_tax_by_year[event_year] = dividend_tax_by_year.get(event_year, 0.0) + event.tax_amount
            elif event.tax_type == 'capital_gains':
                payment_year = event_year + 1  # 다음 연도에 납부
                capital_tax_payment_by_year[payment_year] = capital_tax_payment_by_year.get(payment_year, 0.0) + event.tax_amount

        annual_data = []
        years = sorted(history_df['year'].unique())
        prev_year_end_value = None

        for year in years:
            year_data = history_df[history_df['year'] == year]

            if len(year_data) < 1:
                continue

            # 시작값: 해당 연도 첫 스냅샷 또는 이전 연도 종료값 사용
            if len(year_data) >= 2:
                start_value = year_data['total_value'].iloc[0]
                end_value = year_data['total_value'].iloc[-1]
            elif prev_year_end_value is not None:
                # 마지막 연도: 스냅샷이 1개뿐이면 이전 연도 종료값을 시작값으로 사용
                start_value = prev_year_end_value
                end_value = year_data['total_value'].iloc[-1]
            else:
                # 첫 연도인데 스냅샷이 1개뿐이면 스킵
                continue

            prev_year_end_value = end_value
            
            # 전년도 양도소득세 납부액을 차감한 시작 가치
            capital_tax_paid = capital_tax_payment_by_year.get(year, 0.0)
            start_value_after_capital_tax = start_value - capital_tax_paid

            year_return = (end_value / start_value_after_capital_tax - 1) * 100 if start_value_after_capital_tax != 0 else 0
            
            # 연간 인출금
            withdrawals = [e for e in result.withdrawal_events 
                         if e['date'].year == year]
            year_withdrawal = sum(e['total_withdrawal'] for e in withdrawals)
            
            # 연간 배당금
            dividends = [e for e in result.dividend_events
                        if e['date'].year == year]
            year_dividend_gross = sum(e['gross_dividend'] for e in dividends)
            year_dividend_net = sum(e['net_dividend'] for e in dividends)

            year_dividend_tax = dividend_tax_by_year.get(year, 0.0)
            year_capital_tax = capital_tax_payment_by_year.get(year, 0.0)
            
            # 연간 거래비용: 리밸런싱/인출에서 누적된 total_transaction_cost가 없으므로
            # 연간 현금 흐름으로 추정할 수 없어서 별도 추적 필요.
            # 여기서는 연도별 리밸런싱 이벤트의 transaction_cost 합계를 사용.
            year_trade_cost = sum(
                e['transaction_cost'] for e in self.rebalance_events
                if pd.Timestamp(e['date']).year == year
            )
            
            annual_data.append({
                'year': year,
                'start_value': start_value,
                'start_value_after_capital_tax': start_value_after_capital_tax,
                'end_value': end_value,
                'return_pct': year_return,
                'withdrawal': year_withdrawal,
                'dividend_gross': year_dividend_gross,
                'dividend_net': year_dividend_net,
                'tax_dividend': year_dividend_tax,
                'tax_capital_gains': year_capital_tax,
                'transaction_cost': year_trade_cost
            })
        
        return pd.DataFrame(annual_data)

