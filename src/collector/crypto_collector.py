"""
암호화폐 데이터 수집기
"""
import ccxt
import requests
import pandas as pd
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta

from .base_collector import BaseCollector
from config.settings import CRYPTOCURRENCIES

logger = logging.getLogger(__name__)

class CryptoCollector(BaseCollector):
    """암호화폐 데이터 수집기 (업비트/CCXT 기반)"""
    
    def __init__(self):
        super().__init__("CryptoCollector")
        self.upbit_base_url = "https://api.upbit.com/v1"
        
    def collect_symbol_data(self, symbol: str, period: str = "1y", 
                           interval: str = "days") -> pd.DataFrame:
        """
        업비트에서 암호화폐 데이터 수집
        
        Args:
            symbol: 암호화폐 심볼 (예: 'BTC-KRW')
            period: 데이터 수집 기간
            interval: 데이터 간격 ('minutes', 'hours', 'days', 'weeks', 'months')
            
        Returns:
            OHLCV 데이터 DataFrame
        """
        try:
            # 업비트 API 사용
            if '-KRW' not in symbol:
                symbol = f"{symbol}-KRW"
                
            # 기간을 날짜로 변환
            start_date, end_date = self.get_date_range(period)
            
            # 업비트 API 호출
            data = self._fetch_upbit_candles(symbol, interval, start_date, end_date)
            
            if data.empty:
                logger.warning(f"{symbol}: 수집된 데이터가 없습니다.")
                return pd.DataFrame()
                
            logger.info(f"{symbol}: {len(data)}개 데이터 포인트 수집 완료")
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 데이터 수집 중 오류 발생: {str(e)}")
            raise
    
    def _fetch_upbit_candles(self, symbol: str, interval: str, 
                           start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame:
        """
        업비트 캔들 데이터 가져오기
        
        Args:
            symbol: 암호화폐 심볼
            interval: 시간 간격
            start_date: 시작 날짜
            end_date: 종료 날짜
            
        Returns:
            OHLCV DataFrame
        """
        # 간격별 엔드포인트 설정
        interval_mapping = {
            'minutes': 'minutes/1',
            'hours': 'hours',
            'days': 'days',
            'weeks': 'weeks',
            'months': 'months'
        }
        
        if interval not in interval_mapping:
            interval = 'days'  # 기본값
            
        endpoint = f"{self.upbit_base_url}/candles/{interval_mapping[interval]}"
        
        all_data = []
        current_date = end_date
        
        while current_date >= start_date:
            params = {
                'market': symbol,
                'to': current_date.strftime('%Y-%m-%d %H:%M:%S'),
                'count': 200  # 한 번에 최대 200개
            }
            
            response = requests.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            candles = response.json()
            
            if not candles:
                break
                
            # DataFrame으로 변환
            df = pd.DataFrame(candles)
            
            if df.empty:
                break
                
            # 컬럼명 변경 및 정규화
            column_mapping = {
                'candle_date_time_utc': 'datetime',
                'opening_price': 'open',
                'high_price': 'high',
                'low_price': 'low',
                'trade_price': 'close',
                'candle_acc_trade_volume': 'volume'
            }
            
            df = df.rename(columns=column_mapping)
            
            # 날짜 변환
            df['datetime'] = pd.to_datetime(df['datetime'])
            df['date'] = df['datetime'].dt.date
            
            # 필요한 컬럼만 선택
            df = df[['date', 'open', 'high', 'low', 'close', 'volume']]
            
            all_data.append(df)
            
            # 다음 배치를 위한 날짜 업데이트
            oldest_date = df['date'].min()
            current_date = oldest_date - timedelta(days=1)
            
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            result = result.drop_duplicates(subset=['date'], keep='first')
            result = result.sort_values('date').reset_index(drop=True)
            
            # 날짜 범위 필터링
            result = result[
                (result['date'] >= start_date) & (result['date'] <= end_date)
            ]
            
            return result
        
        return pd.DataFrame()
    
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        암호화폐 정보 조회
        
        Args:
            symbol: 암호화폐 심볼
            
        Returns:
            암호화폐 정보 딕셔너리
        """
        try:
            if '-KRW' not in symbol:
                symbol = f"{symbol}-KRW"
                
            # 업비트 마켓 정보 조회
            endpoint = f"{self.upbit_base_url}/market/all"
            response = requests.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            
            markets = response.json()
            
            for market in markets:
                if market['market'] == symbol:
                    # 기본 정보
                    base_symbol = symbol.split('-')[0]
                    
                    return {
                        'symbol': symbol,
                        'name': market['korean_name'],
                        'market': 'crypto',
                        'currency': 'KRW',
                        'sector': 'Cryptocurrency',
                        'industry': 'Digital Asset',
                        'base_currency': base_symbol,
                        'quote_currency': 'KRW'
                    }
            
            # 마켓 정보를 찾지 못한 경우 기본값 반환
            base_symbol = symbol.split('-')[0] if '-' in symbol else symbol
            
            return {
                'symbol': symbol,
                'name': base_symbol,
                'market': 'crypto',
                'currency': 'KRW',
                'sector': 'Cryptocurrency',
                'industry': 'Digital Asset',
                'base_currency': base_symbol,
                'quote_currency': 'KRW'
            }
            
        except Exception as e:
            logger.error(f"{symbol} 정보 조회 중 오류 발생: {str(e)}")
            base_symbol = symbol.split('-')[0] if '-' in symbol else symbol
            
            return {
                'symbol': symbol,
                'name': base_symbol,
                'market': 'crypto',
                'currency': 'KRW',
                'sector': 'Cryptocurrency',
                'industry': 'Digital Asset',
                'base_currency': base_symbol,
                'quote_currency': 'KRW'
            }
    
    def collect_major_cryptos(self, period: str = "1y") -> pd.DataFrame:
        """
        주요 암호화폐 데이터 수집
        
        Args:
            period: 수집 기간
            
        Returns:
            전체 암호화폐 데이터 DataFrame
        """
        logger.info(f"주요 암호화폐 {len(CRYPTOCURRENCIES)}개 종목 데이터 수집 시작")
        return self.collect_multiple_symbols(CRYPTOCURRENCIES, period)
    
    def get_available_markets(self) -> List[Dict[str, Any]]:
        """
        업비트에서 거래 가능한 모든 마켓 조회
        
        Returns:
            마켓 정보 리스트
        """
        try:
            endpoint = f"{self.upbit_base_url}/market/all"
            response = requests.get(endpoint, timeout=self.timeout)
            response.raise_for_status()
            
            markets = response.json()
            
            # KRW 마켓만 필터링
            krw_markets = [
                {
                    'symbol': market['market'],
                    'name': market['korean_name'],
                    'market': 'crypto',
                    'currency': 'KRW',
                    'base_currency': market['market'].split('-')[0],
                    'quote_currency': 'KRW'
                }
                for market in markets 
                if market['market'].endswith('-KRW')
            ]
            
            return krw_markets
            
        except Exception as e:
            logger.error(f"마켓 정보 조회 실패: {str(e)}")
            return []
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        최신 가격 조회
        
        Args:
            symbol: 암호화폐 심볼
            
        Returns:
            최신 가격 또는 None
        """
        try:
            if '-KRW' not in symbol:
                symbol = f"{symbol}-KRW"
                
            endpoint = f"{self.upbit_base_url}/ticker"
            params = {'markets': symbol}
            
            response = requests.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            tickers = response.json()
            
            if tickers and len(tickers) > 0:
                return float(tickers[0]['trade_price'])
                
        except Exception as e:
            logger.error(f"{symbol} 최신 가격 조회 실패: {str(e)}")
            
        return None
    
    def get_price_change(self, symbol: str) -> Optional[Dict[str, float]]:
        """
        가격 변화 조회
        
        Args:
            symbol: 암호화폐 심볼
            
        Returns:
            가격 변화 정보 딕셔너리
        """
        try:
            if '-KRW' not in symbol:
                symbol = f"{symbol}-KRW"
                
            endpoint = f"{self.upbit_base_url}/ticker"
            params = {'markets': symbol}
            
            response = requests.get(endpoint, params=params, timeout=self.timeout)
            response.raise_for_status()
            
            tickers = response.json()
            
            if tickers and len(tickers) > 0:
                ticker = tickers[0]
                
                return {
                    'current_price': float(ticker['trade_price']),
                    'previous_price': float(ticker['prev_closing_price']),
                    'price_change': float(ticker['change_price']),
                    'price_change_pct': float(ticker['change_rate']) * 100
                }
                
        except Exception as e:
            logger.error(f"{symbol} 가격 변화 조회 실패: {str(e)}")
            
        return None
