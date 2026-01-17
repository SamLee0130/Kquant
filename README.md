# 📈 Kquant - 백테스트 & 투자 분석 플랫폼

주식과 암호화폐 데이터를 활용한 백테스트 및 투자 전략 분석 도구입니다.

## 🎯 주요 기능

- **📊 데이터 수집**: 주식(Yahoo Finance) 및 암호화폐(업비트) 데이터 자동 수집
- **🔬 백테스트**: 다양한 투자 전략의 성과 분석 및 비교
- **💼 포트폴리오 관리**: 포트폴리오 구성 및 리밸런싱 분석
- **📈 대시보드**: Streamlit 기반 직관적인 웹 대시보드
- **💾 데이터 저장**: SQLite 기반 로컬 데이터베이스

## 🛠️ 기술 스택

- **Backend**: Python, SQLite
- **Frontend**: Streamlit
- **데이터 처리**: Pandas, NumPy
- **시각화**: Plotly, Matplotlib
- **데이터 수집**: yfinance, ccxt, requests

## 🚀 빠른 시작

### 1. 환경 설정

```bash
# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\\Scripts\\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정 (선택적)
cp config/env_template.txt .env
# .env 파일을 편집하여 API 키들을 입력하세요
```

### 2. 데이터베이스 초기화

```python
from src.database_manager import db_manager
db_manager.initialize_database()
```

### 3. 대시보드 실행

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501`로 접속하세요.

## 📁 프로젝트 구조

```
Kquant/
├── app.py                      # 메인 실행 파일
├── requirements.txt            # Python 의존성
├── project.md                  # 프로젝트 개요
├── README.md                   # 프로젝트 문서
├── config/                     # 설정 파일들
│   ├── settings.py            # 기본 설정값들
│   └── env_template.txt       # 환경변수 템플릿
├── data/                      # 데이터베이스 파일 저장소
│   └── kquant.db             # SQLite 데이터베이스
├── sql/                       # SQL 스키마 및 쿼리
│   └── create_tables.sql     # 테이블 생성 스크립트
├── src/                       # 소스 코드
│   ├── database_manager.py   # 데이터베이스 관리
│   ├── collector/            # 데이터 수집 모듈
│   │   ├── base_collector.py
│   │   ├── stock_collector.py
│   │   └── crypto_collector.py
│   ├── analyzer/             # 백테스트 분석 모듈
│   └── dashboard/            # Streamlit 대시보드
│       └── main_app.py
├── notebooks/                 # Jupyter 노트북 (분석용)
└── logs/                     # 로그 파일들
```

## 💡 사용 예시

### 데이터 수집

```python
from src.collector.stock_collector import StockCollector
from src.collector.crypto_collector import CryptoCollector

# 주식 데이터 수집
stock_collector = StockCollector()
samsung_data = stock_collector.collect_symbol_data('005930', period='1y')

# 암호화폐 데이터 수집
crypto_collector = CryptoCollector()
bitcoin_data = crypto_collector.collect_symbol_data('BTC-KRW', period='6m')
```

### 데이터베이스 조작

```python
from src.database_manager import db_manager

# 종목 정보 조회
symbols = db_manager.get_symbols()

# 가격 데이터 조회
price_data = db_manager.get_price_data('005930', start_date='2023-01-01')

# 백테스트 결과 조회
results = db_manager.get_backtest_results()
```

## 📊 데이터베이스 스키마

주요 테이블들:
- `symbols`: 종목 정보
- `daily_prices`: 일일 가격 데이터 (OHLCV)
- `strategies`: 투자 전략 정보
- `backtest_runs`: 백테스트 실행 정보
- `backtest_results`: 백테스트 결과 요약
- `portfolio_history`: 포트폴리오 일별 변화
- `trades`: 거래 내역

## 🔧 개발 계획

### Phase 1: 기본 기능 (현재)
- [x] 프로젝트 구조 설정
- [x] 데이터 수집 모듈
- [x] 기본 대시보드
- [ ] 간단한 백테스트 엔진

### Phase 2: 고급 기능
- [ ] 다양한 투자 전략 구현
- [ ] 기술적 분석 지표
- [ ] 포트폴리오 최적화
- [ ] 리스크 관리 도구

### Phase 3: 확장 기능
- [ ] 머신러닝 기반 예측 모델
- [ ] 자동 리밸런싱
- [ ] 알림 시스템
- [ ] API 서버 구축

## 🤝 기여하기

1. Fork the project
2. Create your feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## 📄 라이선스

This project is licensed under the MIT License.

## ⚠️ 면책 조항

이 도구는 교육 및 연구 목적으로 제작되었습니다. 실제 투자 결정에는 신중을 기하시기 바라며, 투자로 인한 손실에 대해서는 책임지지 않습니다.
