"""
수익률 분석 모듈 - 주가수익률, 배당수익률, 세후수익률 계산
"""
import pandas as pd
import numpy as np
import yfinance as yf
from typing import Dict, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger(__name__)

class ReturnAnalyzer:
    """투자 수익률 분석 클래스"""
    
    def __init__(self, symbol: str):
        """
        분석기 초기화
        
        Args:
            symbol: 분석할 종목 코드
        """
        self.symbol = symbol
        self.ticker = yf.Ticker(symbol)
        
    def get_dividend_data(self, period: str = "2y") -> pd.DataFrame:
        """
        배당 데이터 수집
        
        Args:
            period: 데이터 수집 기간
            
        Returns:
            배당 데이터 DataFrame
        """
        try:
            # 배당 데이터 가져오기
            dividends = self.ticker.dividends
            
            if dividends.empty:
                logger.warning(f"{self.symbol}: 배당 데이터가 없습니다.")
                return pd.DataFrame()
            
            # 기간 필터링
            if period != "max":
                end_date = datetime.now()
                if period.endswith('y'):
                    years = int(period[:-1])
                    start_date = end_date - timedelta(days=years * 365)
                elif period.endswith('m'):
                    months = int(period[:-1])
                    start_date = end_date - timedelta(days=months * 30)
                else:
                    start_date = end_date - timedelta(days=365)  # 기본 1년
                
                # 타임존을 제거하고 naive datetime으로 변환해서 비교
                if hasattr(dividends.index, 'tz') and dividends.index.tz is not None:
                    dividends.index = dividends.index.tz_localize(None)
                
                dividends = dividends[dividends.index >= start_date]
            
            # DataFrame으로 변환
            div_df = pd.DataFrame(dividends).reset_index()
            div_df.columns = ['date', 'dividend']
            div_df['date'] = pd.to_datetime(div_df['date']).dt.date
            
            logger.info(f"{self.symbol}: {len(div_df)}개의 배당 데이터 수집 완료")
            return div_df
            
        except Exception as e:
            logger.error(f"{self.symbol} 배당 데이터 수집 실패: {str(e)}")
            return pd.DataFrame()
    
    def calculate_price_returns(self, price_data: pd.DataFrame) -> pd.DataFrame:
        """
        주가 수익률 계산
        
        Args:
            price_data: 가격 데이터 DataFrame
            
        Returns:
            수익률이 추가된 DataFrame
        """
        df = price_data.copy()
        df = df.sort_values('date').reset_index(drop=True)
        
        # 일일 수익률 계산
        df['daily_return'] = df['close'].pct_change()
        
        # 누적 수익률 계산
        df['cumulative_return'] = (1 + df['daily_return']).cumprod() - 1
        
        # 기간별 수익률 계산
        first_price = df['close'].iloc[0]
        df['total_return'] = (df['close'] / first_price - 1) * 100
        
        return df
    
    def calculate_dividend_yield(self, price_data: pd.DataFrame, 
                               dividend_data: pd.DataFrame) -> pd.DataFrame:
        """
        배당 수익률 계산
        
        Args:
            price_data: 가격 데이터
            dividend_data: 배당 데이터
            
        Returns:
            배당 수익률이 포함된 DataFrame
        """
        df = price_data.copy()
        
        # 연간 배당금 계산 (최근 12개월)
        if not dividend_data.empty:
            # 최근 12개월 배당금 합계
            recent_date = max(dividend_data['date'])
            one_year_ago = recent_date - timedelta(days=365)
            
            recent_dividends = dividend_data[
                dividend_data['date'] > one_year_ago
            ]
            
            annual_dividend = recent_dividends['dividend'].sum()
            
            # 배당 수익률 계산
            df['annual_dividend'] = annual_dividend
            df['dividend_yield'] = (annual_dividend / df['close']) * 100
            
            # 분기별 배당 예상 (보통 SCHD는 분기배당)
            df['quarterly_dividend'] = annual_dividend / 4
            
        else:
            df['annual_dividend'] = 0
            df['dividend_yield'] = 0
            df['quarterly_dividend'] = 0
        
        return df
    
    def calculate_total_return(self, price_data: pd.DataFrame,
                             dividend_data: pd.DataFrame,
                             start_date: Optional[str] = None) -> Dict[str, float]:
        """
        총 수익률 계산 (주가상승 + 배당)
        
        Args:
            price_data: 가격 데이터
            dividend_data: 배당 데이터  
            start_date: 시작 날짜 (없으면 전체 기간)
            
        Returns:
            총 수익률 정보 딕셔너리
        """
        df = price_data.copy()
        
        if start_date:
            start_date = pd.to_datetime(start_date).date()
            # 날짜 타입 통일
            df_copy = df.copy()
            df_copy['date'] = pd.to_datetime(df_copy['date']).dt.date
            df = df_copy[df_copy['date'] >= start_date]
            
            if not dividend_data.empty:
                div_copy = dividend_data.copy()
                div_copy['date'] = pd.to_datetime(div_copy['date']).dt.date
                dividend_data = div_copy[div_copy['date'] >= start_date]
        
        if df.empty:
            return {}
        
        # 기간 정보
        start_price = df['close'].iloc[0]
        end_price = df['close'].iloc[-1]
        start_date_actual = df['date'].iloc[0]
        end_date_actual = df['date'].iloc[-1]
        
        # 날짜 타입 확인 및 변환
        if isinstance(start_date_actual, str):
            start_date_actual = pd.to_datetime(start_date_actual).date()
        if isinstance(end_date_actual, str):
            end_date_actual = pd.to_datetime(end_date_actual).date()
        
        # 보유 기간 (일수)
        holding_period = (end_date_actual - start_date_actual).days
        
        # 주가 수익률
        price_return = (end_price / start_price - 1) * 100
        
        # 배당 수익률
        total_dividends = dividend_data['dividend'].sum() if not dividend_data.empty else 0
        dividend_return = (total_dividends / start_price) * 100
        
        # 총 수익률
        total_return = price_return + dividend_return
        
        # 연율화 수익률
        years = holding_period / 365.25
        if years > 0:
            annualized_return = ((1 + total_return/100) ** (1/years) - 1) * 100
        else:
            annualized_return = 0
        
        return {
            'start_date': start_date_actual,
            'end_date': end_date_actual,
            'holding_period_days': holding_period,
            'start_price': round(start_price, 2),
            'end_price': round(end_price, 2),
            'price_return_pct': round(price_return, 2),
            'dividend_return_pct': round(dividend_return, 2),
            'total_return_pct': round(total_return, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'total_dividends': round(total_dividends, 2)
        }
    
    def calculate_after_tax_return(self, total_return: float, dividend_return: float,
                                 dividend_tax_rate: float = 0.15,
                                 capital_gains_tax_rate: float = 0.0) -> Dict[str, float]:
        """
        세후 수익률 계산
        
        Args:
            total_return: 총 수익률 (%)
            dividend_return: 배당 수익률 (%)
            dividend_tax_rate: 배당세율 (기본: 15% - 미국 배당세)
            capital_gains_tax_rate: 양도소득세율 (기본: 0% - 1년 이상 보유시)
            
        Returns:
            세후 수익률 정보
        """
        price_return = total_return - dividend_return
        
        # 세후 배당 수익률
        after_tax_dividend = dividend_return * (1 - dividend_tax_rate)
        
        # 세후 주가 수익률 (양도소득세 적용)
        after_tax_price = price_return * (1 - capital_gains_tax_rate)
        
        # 세후 총 수익률
        after_tax_total = after_tax_dividend + after_tax_price
        
        return {
            'before_tax_total_return': round(total_return, 2),
            'before_tax_dividend_return': round(dividend_return, 2),
            'before_tax_price_return': round(price_return, 2),
            'after_tax_dividend_return': round(after_tax_dividend, 2),
            'after_tax_price_return': round(after_tax_price, 2),
            'after_tax_total_return': round(after_tax_total, 2),
            'dividend_tax_rate': dividend_tax_rate * 100,
            'capital_gains_tax_rate': capital_gains_tax_rate * 100,
            'tax_impact': round(total_return - after_tax_total, 2)
        }
    
    def get_performance_metrics(self, price_data: pd.DataFrame) -> Dict[str, float]:
        """
        성과 지표 계산
        
        Args:
            price_data: 가격 데이터
            
        Returns:
            성과 지표 딕셔너리
        """
        df = price_data.copy()
        df['daily_return'] = df['close'].pct_change()
        
        returns = df['daily_return'].dropna()
        
        if len(returns) < 2:
            return {}
        
        # 연율화를 위한 기간
        years = len(returns) / 252  # 252 = 연간 거래일 수
        
        # 기본 통계
        total_return = (df['close'].iloc[-1] / df['close'].iloc[0] - 1) * 100
        annualized_return = ((1 + total_return/100) ** (1/years) - 1) * 100 if years > 0 else 0
        
        volatility = returns.std() * np.sqrt(252) * 100  # 연율화된 변동성
        
        # 샤프 비율 (무위험 수익률 2% 가정)
        risk_free_rate = 2.0
        excess_return = annualized_return - risk_free_rate
        sharpe_ratio = excess_return / volatility if volatility != 0 else 0
        
        # 최대 낙폭 계산
        cumulative = (1 + returns).cumprod()
        rolling_max = cumulative.expanding().max()
        drawdown = (cumulative - rolling_max) / rolling_max
        max_drawdown = drawdown.min() * 100
        
        return {
            'total_return_pct': round(total_return, 2),
            'annualized_return_pct': round(annualized_return, 2),
            'volatility_pct': round(volatility, 2),
            'sharpe_ratio': round(sharpe_ratio, 2),
            'max_drawdown_pct': round(max_drawdown, 2),
            'total_trading_days': len(returns)
        }
    
    def calculate_dividend_growth_metrics(self, dividend_data: pd.DataFrame) -> Dict[str, float]:
        """
        배당 성장 지표 계산
        
        Args:
            dividend_data: 배당 데이터
            
        Returns:
            배당 성장 지표 딕셔너리
        """
        if dividend_data.empty or len(dividend_data) < 4:
            return {
                'dividend_growth_rate': 0,
                'avg_dividend_growth_rate': 0,
                'dividend_years': 0,
                'consecutive_increases': 0,
                'current_yield': 0,
                'five_year_yield_avg': 0
            }
        
        # 날짜 기준으로 정렬
        df = dividend_data.sort_values('date').copy()
        
        # 연도별 배당금 합계 계산
        df['year'] = pd.to_datetime(df['date']).dt.year
        yearly_dividends = df.groupby('year')['dividend'].sum().reset_index()
        yearly_dividends = yearly_dividends.sort_values('year')
        
        if len(yearly_dividends) < 2:
            return {
                'dividend_growth_rate': 0,
                'avg_dividend_growth_rate': 0,
                'dividend_years': len(yearly_dividends),
                'consecutive_increases': 0,
                'current_yield': yearly_dividends['dividend'].iloc[-1] if len(yearly_dividends) > 0 else 0,
                'five_year_yield_avg': yearly_dividends['dividend'].mean() if len(yearly_dividends) > 0 else 0
            }
        
        # 최신 연도와 이전 연도 배당 성장률
        current_year_dividend = yearly_dividends['dividend'].iloc[-1]
        previous_year_dividend = yearly_dividends['dividend'].iloc[-2]
        
        if previous_year_dividend > 0:
            recent_growth_rate = ((current_year_dividend - previous_year_dividend) / previous_year_dividend) * 100
        else:
            recent_growth_rate = 0
        
        # 평균 배당 성장률 계산 (연평균 성장률)
        first_dividend = yearly_dividends['dividend'].iloc[0]
        last_dividend = yearly_dividends['dividend'].iloc[-1]
        years = len(yearly_dividends) - 1
        
        if first_dividend > 0 and years > 0:
            avg_growth_rate = ((last_dividend / first_dividend) ** (1/years) - 1) * 100
        else:
            avg_growth_rate = 0
        
        # 연속 배당 증가 횟수
        consecutive_increases = 0
        for i in range(len(yearly_dividends) - 1, 0, -1):
            if yearly_dividends['dividend'].iloc[i] > yearly_dividends['dividend'].iloc[i-1]:
                consecutive_increases += 1
            else:
                break
        
        # 5년 평균 배당률 (최근 5년)
        recent_5_years = yearly_dividends.tail(min(5, len(yearly_dividends)))
        five_year_avg = recent_5_years['dividend'].mean()
        
        return {
            'dividend_growth_rate': round(recent_growth_rate, 2),
            'avg_dividend_growth_rate': round(avg_growth_rate, 2),
            'dividend_years': len(yearly_dividends),
            'consecutive_increases': consecutive_increases,
            'current_annual_dividend': round(current_year_dividend, 2),
            'five_year_dividend_avg': round(five_year_avg, 2)
        }
    
    def get_dividend_yield_over_time(self, price_data: pd.DataFrame, 
                                   dividend_data: pd.DataFrame) -> pd.DataFrame:
        """
        시계열별 배당 수익률 계산
        
        Args:
            price_data: 가격 데이터
            dividend_data: 배당 데이터
            
        Returns:
            시계열별 배당 수익률 DataFrame
        """
        if dividend_data.empty:
            return pd.DataFrame()
        
        price_df = price_data.copy().sort_values('date')
        
        # 날짜 타입 통일
        price_df['date'] = pd.to_datetime(price_df['date']).dt.date
        dividend_data_copy = dividend_data.copy()
        dividend_data_copy['date'] = pd.to_datetime(dividend_data_copy['date']).dt.date
        
        # 연간 배당금 계산 (각 날짜 기준으로 이전 12개월 배당금 합계)
        result = []
        
        for _, row in price_df.iterrows():
            current_date = row['date']
            one_year_ago = current_date - timedelta(days=365)
            
            # 해당 날짜 기준 이전 12개월 배당금
            trailing_12m_dividends = dividend_data_copy[
                (dividend_data_copy['date'] > one_year_ago) & 
                (dividend_data_copy['date'] <= current_date)
            ]['dividend'].sum()
            
            # 배당 수익률 계산
            if trailing_12m_dividends > 0:
                dividend_yield = (trailing_12m_dividends / row['close']) * 100
            else:
                dividend_yield = 0
            
            result.append({
                'date': current_date,
                'price': row['close'],
                'trailing_12m_dividend': trailing_12m_dividends,
                'dividend_yield': dividend_yield
            })
        
        return pd.DataFrame(result)
