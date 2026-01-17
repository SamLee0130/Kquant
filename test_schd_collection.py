"""
SCHD 데이터 수집 테스트 스크립트
"""
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).parent))

from src.database_manager import db_manager
from src.collector.stock_collector import StockCollector
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)

def main():
    print("🚀 SCHD 데이터 수집 테스트 시작")
    
    # 데이터베이스 초기화
    try:
        print("📊 데이터베이스 초기화...")
        db_manager.initialize_database()
        print("✅ 데이터베이스 초기화 완료")
    except Exception as e:
        print(f"❌ 데이터베이스 초기화 실패: {e}")
        return
    
    # SCHD 데이터 수집
    try:
        print("📥 SCHD 데이터 수집 중...")
        collector = StockCollector()
        
        # SCHD 데이터 수집 (2년치)
        data = collector.collect_symbol_data('SCHD', period='2y')
        
        if not data.empty:
            print(f"✅ {len(data)}개의 데이터 포인트 수집 완료")
            print("📊 데이터 샘플:")
            print(data.head())
            
            # 데이터베이스에 저장
            data['symbol'] = 'SCHD'
            db_manager.insert_daily_prices(data)
            print("💾 데이터베이스 저장 완료")
            
            # 종목 정보 저장
            symbol_info = collector.get_symbol_info('SCHD')
            db_manager.insert_symbol(
                symbol=symbol_info['symbol'],
                name=symbol_info['name'],
                market=symbol_info['market'],
                currency=symbol_info['currency'],
                sector=symbol_info.get('sector', ''),
                industry=symbol_info.get('industry', '')
            )
            print("✅ 종목 정보 저장 완료")
            
        else:
            print("❌ 수집된 데이터가 없습니다.")
            
    except Exception as e:
        print(f"❌ 데이터 수집 실패: {e}")
        import traceback
        traceback.print_exc()
    
    # 저장된 데이터 확인
    try:
        print("\n🔍 저장된 데이터 확인:")
        saved_data = db_manager.get_price_data('SCHD')
        print(f"📈 총 {len(saved_data)}개의 데이터 포인트가 저장되었습니다.")
        print("최근 5개 데이터:")
        print(saved_data.tail())
        
    except Exception as e:
        print(f"❌ 데이터 확인 실패: {e}")

if __name__ == "__main__":
    main()
