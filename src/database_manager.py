"""
SQLite 데이터베이스 관리 유틸리티
"""
import sqlite3
import pandas as pd
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging

from config.settings import DATABASE_PATH, SQL_DIR

logger = logging.getLogger(__name__)

class DatabaseManager:
    """SQLite 데이터베이스 관리 클래스"""
    
    def __init__(self, db_path: Path = DATABASE_PATH):
        """
        데이터베이스 매니저 초기화
        
        Args:
            db_path: 데이터베이스 파일 경로
        """
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        
    def get_connection(self) -> sqlite3.Connection:
        """데이터베이스 연결 반환"""
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys = ON")  # 외래키 제약조건 활성화
        return conn
        
    def initialize_database(self) -> None:
        """데이터베이스 테이블 초기화"""
        schema_file = SQL_DIR / "create_tables.sql"
        
        if not schema_file.exists():
            logger.error(f"스키마 파일을 찾을 수 없습니다: {schema_file}")
            raise FileNotFoundError(f"Schema file not found: {schema_file}")
            
        with open(schema_file, 'r', encoding='utf-8') as f:
            schema_sql = f.read()
            
        with self.get_connection() as conn:
            conn.executescript(schema_sql)
            logger.info("데이터베이스 테이블이 성공적으로 생성되었습니다.")
    
    def execute_query(self, query: str, params: tuple = ()) -> pd.DataFrame:
        """
        쿼리 실행 및 결과를 DataFrame으로 반환
        
        Args:
            query: 실행할 SQL 쿼리
            params: 쿼리 파라미터
            
        Returns:
            쿼리 결과 DataFrame
        """
        with self.get_connection() as conn:
            return pd.read_sql_query(query, conn, params=params)
    
    def execute_script(self, script: str) -> None:
        """SQL 스크립트 실행"""
        with self.get_connection() as conn:
            conn.executescript(script)
            
    def insert_dataframe(self, df: pd.DataFrame, table_name: str, 
                        if_exists: str = 'append') -> None:
        """
        DataFrame을 테이블에 삽입
        
        Args:
            df: 삽입할 DataFrame
            table_name: 테이블 명
            if_exists: 'fail', 'replace', 'append' 중 하나
        """
        with self.get_connection() as conn:
            df.to_sql(table_name, conn, if_exists=if_exists, index=False)
            logger.info(f"{len(df)}개 행이 {table_name} 테이블에 삽입되었습니다.")
    
    def insert_symbol(self, symbol: str, name: str, market: str, 
                     currency: str = 'KRW', sector: str = None, 
                     industry: str = None) -> None:
        """종목 정보 삽입"""
        query = """
        INSERT OR REPLACE INTO symbols (symbol, name, market, currency, sector, industry)
        VALUES (?, ?, ?, ?, ?, ?)
        """
        with self.get_connection() as conn:
            conn.execute(query, (symbol, name, market, currency, sector, industry))
            
    def insert_daily_prices(self, prices_df: pd.DataFrame) -> None:
        """일일 가격 데이터 삽입"""
        required_columns = ['symbol', 'date', 'open', 'high', 'low', 'close']
        if not all(col in prices_df.columns for col in required_columns):
            raise ValueError(f"필수 컬럼이 누락되었습니다: {required_columns}")
            
        self.insert_dataframe(prices_df, 'daily_prices', if_exists='replace')
    
    def get_symbols(self, market: Optional[str] = None) -> pd.DataFrame:
        """종목 목록 조회"""
        query = "SELECT * FROM symbols"
        params = ()
        
        if market:
            query += " WHERE market = ?"
            params = (market,)
            
        return self.execute_query(query, params)
    
    def get_price_data(self, symbol: str, start_date: str = None, 
                      end_date: str = None) -> pd.DataFrame:
        """가격 데이터 조회"""
        query = """
        SELECT * FROM daily_prices 
        WHERE symbol = ?
        """
        params = [symbol]
        
        if start_date:
            query += " AND date >= ?"
            params.append(start_date)
            
        if end_date:
            query += " AND date <= ?"
            params.append(end_date)
            
        query += " ORDER BY date"
        
        return self.execute_query(query, tuple(params))
    
    def get_backtest_results(self, strategy_id: str = None) -> pd.DataFrame:
        """백테스트 결과 조회"""
        if strategy_id:
            query = """
            SELECT * FROM portfolio_performance 
            WHERE strategy_id = ?
            ORDER BY run_date DESC
            """
            return self.execute_query(query, (strategy_id,))
        else:
            query = "SELECT * FROM portfolio_performance ORDER BY run_date DESC"
            return self.execute_query(query)
    
    def cleanup_old_data(self, days: int = 365) -> None:
        """오래된 데이터 정리"""
        query = """
        DELETE FROM daily_prices 
        WHERE date < date('now', '-{} days')
        """.format(days)
        
        with self.get_connection() as conn:
            cursor = conn.execute(query)
            logger.info(f"{cursor.rowcount}개의 오래된 가격 데이터가 삭제되었습니다.")
    
    def get_table_info(self, table_name: str) -> pd.DataFrame:
        """테이블 정보 조회"""
        query = f"PRAGMA table_info({table_name})"
        return self.execute_query(query)
    
    def list_tables(self) -> List[str]:
        """데이터베이스의 모든 테이블 목록 반환"""
        query = """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name NOT LIKE 'sqlite_%'
        ORDER BY name
        """
        result = self.execute_query(query)
        return result['name'].tolist()

# 전역 데이터베이스 매니저 인스턴스
db_manager = DatabaseManager()
