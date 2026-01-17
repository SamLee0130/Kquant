"""
기본 데이터 수집기 클래스
"""
from abc import ABC, abstractmethod
import pandas as pd
import logging
from typing import List, Optional, Dict, Any
import time
from datetime import datetime, timedelta

from config.settings import DATA_COLLECTION

logger = logging.getLogger(__name__)

class BaseCollector(ABC):
    """데이터 수집기 기본 클래스"""
    
    def __init__(self, name: str):
        """
        데이터 수집기 초기화
        
        Args:
            name: 수집기 이름
        """
        self.name = name
        self.retry_count = DATA_COLLECTION['retry_count']
        self.timeout = DATA_COLLECTION['timeout']
        self.delay = DATA_COLLECTION['delay_between_requests']
        
    @abstractmethod
    def collect_symbol_data(self, symbol: str, period: str = "1y", 
                           interval: str = "1d") -> pd.DataFrame:
        """
        단일 종목 데이터 수집 (추상 메서드)
        
        Args:
            symbol: 종목 코드
            period: 데이터 수집 기간
            interval: 데이터 간격
            
        Returns:
            OHLCV 데이터 DataFrame
        """
        pass
    
    @abstractmethod
    def get_symbol_info(self, symbol: str) -> Dict[str, Any]:
        """
        종목 정보 조회 (추상 메서드)
        
        Args:
            symbol: 종목 코드
            
        Returns:
            종목 정보 딕셔너리
        """
        pass
    
    def collect_multiple_symbols(self, symbols: List[str], 
                                period: str = "1y") -> pd.DataFrame:
        """
        여러 종목 데이터 수집
        
        Args:
            symbols: 종목 코드 리스트
            period: 데이터 수집 기간
            
        Returns:
            전체 종목 OHLCV 데이터 DataFrame
        """
        all_data = []
        
        for i, symbol in enumerate(symbols):
            try:
                logger.info(f"수집 중: {symbol} ({i+1}/{len(symbols)})")
                
                data = self._retry_collect(symbol, period)
                if not data.empty:
                    data['symbol'] = symbol
                    all_data.append(data)
                    
                # API 요청 제한을 위한 딜레이
                if i < len(symbols) - 1:
                    time.sleep(self.delay)
                    
            except Exception as e:
                logger.error(f"{symbol} 데이터 수집 실패: {str(e)}")
                continue
                
        if all_data:
            result = pd.concat(all_data, ignore_index=True)
            logger.info(f"총 {len(all_data)}개 종목의 데이터를 수집했습니다.")
            return result
        else:
            logger.warning("수집된 데이터가 없습니다.")
            return pd.DataFrame()
    
    def _retry_collect(self, symbol: str, period: str) -> pd.DataFrame:
        """
        재시도 로직이 포함된 데이터 수집
        
        Args:
            symbol: 종목 코드
            period: 수집 기간
            
        Returns:
            OHLCV 데이터 DataFrame
        """
        last_exception = None
        
        for attempt in range(self.retry_count):
            try:
                data = self.collect_symbol_data(symbol, period)
                return self._validate_and_clean_data(data)
                
            except Exception as e:
                last_exception = e
                if attempt < self.retry_count - 1:
                    wait_time = (attempt + 1) * 2  # 지수 백오프
                    logger.warning(f"{symbol} 수집 실패 (시도 {attempt + 1}/{self.retry_count}): {str(e)}. "
                                 f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"{symbol} 수집 최종 실패: {str(e)}")
                    
        raise last_exception or Exception(f"{symbol} 데이터 수집에 실패했습니다.")
    
    def _validate_and_clean_data(self, data: pd.DataFrame) -> pd.DataFrame:
        """
        데이터 유효성 검사 및 정제
        
        Args:
            data: 원본 DataFrame
            
        Returns:
            정제된 DataFrame
        """
        if data.empty:
            return data
            
        # 필수 컬럼 체크
        required_columns = ['open', 'high', 'low', 'close']
        missing_columns = [col for col in required_columns if col not in data.columns]
        
        if missing_columns:
            raise ValueError(f"필수 컬럼이 누락되었습니다: {missing_columns}")
        
        # 데이터 타입 변환
        numeric_columns = ['open', 'high', 'low', 'close', 'volume']
        for col in numeric_columns:
            if col in data.columns:
                data[col] = pd.to_numeric(data[col], errors='coerce')
        
        # 날짜 인덱스를 컬럼으로 변환
        if isinstance(data.index, pd.DatetimeIndex):
            data = data.reset_index()
            if 'Date' in data.columns:
                data.rename(columns={'Date': 'date'}, inplace=True)
            elif data.index.name:
                data.rename(columns={data.index.name: 'date'}, inplace=True)
        
        # 날짜 컬럼 정규화
        if 'date' in data.columns:
            data['date'] = pd.to_datetime(data['date']).dt.date
            
        # 컬럼명 소문자로 통일
        data.columns = data.columns.str.lower()
        
        # 결측값 제거
        data = data.dropna(subset=['open', 'high', 'low', 'close'])
        
        # 중복 제거
        if 'date' in data.columns:
            data = data.drop_duplicates(subset=['date'], keep='last')
            data = data.sort_values('date').reset_index(drop=True)
        
        return data
    
    def get_date_range(self, period: str) -> tuple:
        """
        기간 문자열을 시작/종료 날짜로 변환
        
        Args:
            period: 기간 문자열 (예: '1y', '6m', '1d')
            
        Returns:
            (start_date, end_date) 튜플
        """
        end_date = datetime.now().date()
        
        if period.endswith('y'):
            years = int(period[:-1])
            start_date = end_date - timedelta(days=years * 365)
        elif period.endswith('m'):
            months = int(period[:-1])
            start_date = end_date - timedelta(days=months * 30)
        elif period.endswith('d'):
            days = int(period[:-1])
            start_date = end_date - timedelta(days=days)
        else:
            # 기본값: 1년
            start_date = end_date - timedelta(days=365)
            
        return start_date, end_date
