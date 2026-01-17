"""
주식 데이터 수집기
"""
import yfinance as yf
import pandas as pd
import logging
from typing import List, Dict, Any, Optional

from .base_collector import BaseCollector
from config.settings import KOREAN_STOCKS

logger = logging.getLogger(__name__)

class StockCollector(BaseCollector):
    """주식 데이터 수집기 (Yahoo Finance 기반)"""
    
    def __init__(self):
        super().__init__("StockCollector")
        
    def collect_symbol_data(self, symbol: str, period: str = "1y", 
                           interval: str = "1d") -> pd.DataFrame:
        """
        Yahoo Finance에서 주식 데이터 수집
        
        Args:
            symbol: 주식 종목 코드
            period: 데이터 수집 기간 ('1d', '5d', '1mo', '3mo', '6mo', '1y', '2y', '5y', '10y', 'ytd', 'max')
            interval: 데이터 간격 ('1m', '2m', '5m', '15m', '30m', '60m', '90m', '1h', '1d', '5d', '1wk', '1mo', '3mo')
            
        Returns:
            OHLCV 데이터 DataFrame
        """
        try:
            # 한국 주식의 경우 .KS 접미사 추가
            if symbol.isdigit() and len(symbol) == 6:
                yf_symbol = f"{symbol}.KS"
            else:
                yf_symbol = symbol
                
            ticker = yf.Ticker(yf_symbol)
            data = ticker.history(period=period, interval=interval)
            
            if data.empty:
                logger.warning(f"{symbol}: 수집된 데이터가 없습니다.")
                return pd.DataFrame()
            
            # 타임존 제거 (timezone-naive로 변환)
            if data.index.tz is not None:
                data.index = data.index.tz_convert(None)
                
            # 날짜 인덱스를 컬럼으로 변환
            data = data.reset_index()
            
            # 컬럼명 정규화
            data.columns = data.columns.str.lower()
            
            # 필요한 컬럼만 선택 및 이름 변경
            column_mapping = {
                'adj close': 'adj_close'
            }
            
            data = data.rename(columns=column_mapping)
            
            # 날짜 컬럼이 있는지 확인하고 정규화
            if 'date' in data.columns:
                data['date'] = pd.to_datetime(data['date']).dt.date
            
            # 불필요한 컬럼 제거 (dividends, stock splits, capital gains 등)
            keep_columns = ['date', 'open', 'high', 'low', 'close', 'volume', 'adj_close']
            data = data[[col for col in keep_columns if col in data.columns]]
            
            logger.info(f"{symbol}: {len(data)}개 데이터 포인트 수집 완료")
            return data
            
        except Exception as e:
            logger.error(f"{symbol} 데이터 수집 중 오류 발생: {str(e)}")
            raise
    
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        종목 정보 조회
        
        Args:
            symbol: 종목 코드
            
        Returns:
            종목 정보 딕셔너리
        """
        try:
            # 한국 주식의 경우 .KS 접미사 추가
            if symbol.isdigit() and len(symbol) == 6:
                yf_symbol = f"{symbol}.KS"
            else:
                yf_symbol = symbol
                
            ticker = yf.Ticker(yf_symbol)
            info = ticker.info
            
            # 필요한 정보만 추출
            symbol_info = {
                'symbol': symbol,
                'name': info.get('longName', info.get('shortName', symbol)),
                'market': 'stock',
                'currency': info.get('currency', 'KRW'),
                'sector': info.get('sector', ''),
                'industry': info.get('industry', ''),
                'market_cap': info.get('marketCap', 0),
                'country': info.get('country', 'South Korea')
            }
            
            return symbol_info
            
        except Exception as e:
            logger.error(f"{symbol} 정보 조회 중 오류 발생: {str(e)}")
            return {
                'symbol': symbol,
                'name': symbol,
                'market': 'stock',
                'currency': 'KRW',
                'sector': '',
                'industry': '',
                'market_cap': 0,
                'country': 'Unknown'
            }
    
    def collect_korean_top_stocks(self, period: str = "1y") -> pd.DataFrame:
        """
        한국 주요 주식 데이터 수집
        
        Args:
            period: 수집 기간
            
        Returns:
            전체 주식 데이터 DataFrame
        """
        logger.info(f"한국 주요 주식 {len(KOREAN_STOCKS)}개 종목 데이터 수집 시작")
        return self.collect_multiple_symbols(KOREAN_STOCKS, period)
    
    def search_symbols(self, query: str) -> List[Dict[str, Any]]:
        """
        종목 검색 (제한된 기능)
        
        Args:
            query: 검색 쿼리
            
        Returns:
            검색 결과 리스트
        """
        # Yahoo Finance는 직접적인 검색 API를 제공하지 않음
        # 기본적인 한국 주식 리스트에서 검색
        results = []
        query_lower = query.lower()
        
        for symbol in KOREAN_STOCKS:
            try:
                info = self.get_symbol_info(symbol)
                if (query_lower in symbol.lower() or 
                    query_lower in info['name'].lower()):
                    results.append(info)
            except Exception as e:
                logger.debug(f"검색 중 {symbol} 정보 조회 실패: {str(e)}")
                continue
                
        return results
    
    def get_latest_price(self, symbol: str) -> Optional[float]:
        """
        최신 가격 조회
        
        Args:
            symbol: 종목 코드
            
        Returns:
            최신 가격 또는 None
        """
        try:
            data = self.collect_symbol_data(symbol, period="1d")
            if not data.empty:
                return float(data['close'].iloc[-1])
        except Exception as e:
            logger.error(f"{symbol} 최신 가격 조회 실패: {str(e)}")
        return None
    
    def get_price_change(self, symbol: str, days: int = 1) -> Optional[Dict[str, float]]:
        """
        가격 변화 조회
        
        Args:
            symbol: 종목 코드
            days: 비교할 일수
            
        Returns:
            가격 변화 정보 딕셔너리
        """
        try:
            period = f"{days + 5}d"  # 여유분 포함
            data = self.collect_symbol_data(symbol, period=period)
            
            if len(data) < 2:
                return None
                
            current_price = float(data['close'].iloc[-1])
            previous_price = float(data['close'].iloc[-(days + 1)])
            
            price_change = current_price - previous_price
            price_change_pct = (price_change / previous_price) * 100
            
            return {
                'current_price': current_price,
                'previous_price': previous_price,
                'price_change': price_change,
                'price_change_pct': price_change_pct
            }
            
        except Exception as e:
            logger.error(f"{symbol} 가격 변화 조회 실패: {str(e)}")
            return None
