# CLAUDE.md

ETF 포트폴리오 백테스트 대시보드 - 한국 세금 규정을 반영한 투자 전략 시뮬레이션 도구

## 핵심 기능

- **자산 배분 백테스트**: ETF 포트폴리오의 과거 성과 시뮬레이션
- **포트폴리오 비교**: 최대 3개 자산 배분 전략 간 성과 비교
- **세금 계산**: 배당소득세(15%), 양도소득세(22%) 반영
- **리밸런싱**: 분기별/연간 리밸런싱 시뮬레이션
- **인출 시뮬레이션**: 은퇴 후 인출 전략 테스트

## 명령어

```bash
# 환경 설정
git clone https://github.com/SamLee0130/Kquant.git
cd Kquant
python -m venv venv
source venv/bin/activate         # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 실행
streamlit run app.py             # localhost:8501
```

## 아키텍처

**기술 스택**: Python 3.10+, Streamlit, yfinance, Pandas/NumPy, Plotly

```
Kquant/
├── app.py                         # 진입점
├── config/settings.py             # 기본값 (자본금, 세율, ETF 배분)
└── src/
    ├── backtest/
    │   ├── portfolio_backtest.py  # 핵심 시뮬레이션 엔진
    │   └── tax_calculator.py      # 세금 계산 모듈
    └── dashboard/
        ├── main_app.py                  # 페이지 라우팅
        ├── allocation_backtest_page.py  # 단일 포트폴리오 백테스트
        └── portfolio_comparison_page.py # 포트폴리오 비교 (최대 3개)
```

## 핵심 컴포넌트

### 백테스트 엔진 (`portfolio_backtest.py`)

- **PortfolioBacktester**: 메인 시뮬레이션 클래스
  - yfinance로 ETF 가격/배당 데이터 조회
  - 일별 포트폴리오 상태 추적 (보유량, 현금, 평가액)
  - 리밸런싱 처리 (분기/연간)
  - 배당금 및 인출 처리
  - 성과 지표 계산 (CAGR, 샤프비율, MDD)

- **PortfolioSnapshot**: 월말 포트폴리오 스냅샷 (효율성을 위해 월별 기록)
- **BacktestResult**: 시뮬레이션 결과 집계 (히스토리, 지표, 이벤트 로그)

### 세금 계산기 (`tax_calculator.py`)

한국 세법 기반 이중 과세 시스템:

| 세금 유형 | 세율 | 적용 시점 |
|-----------|------|-----------|
| 배당소득세 | 15% | 배당 수령 즉시 |
| 양도소득세 | 22% | 연말 정산 → 다음해 1월 납부 |

- 양도소득 기본공제: $2,000
- 연간 양도차익 누적 추적
- 이연 납부 방식 (year-end settlement → January payment)

### 대시보드 페이지

**allocation_backtest_page.py**: 단일 포트폴리오 분석
- 사이드바: 초기자본, 기간, 세율, 거래비용, ETF 배분 설정
- 탭: 포트폴리오 가치 차트, 자산배분 추이, 연간 성과, 배당/세금 내역, 거래 로그

**portfolio_comparison_page.py**: 다중 포트폴리오 비교
- 최대 3개 포트폴리오 동시 비교
- 공통 설정으로 일관된 비교
- 나란히 성과 시각화

## 시뮬레이션 흐름

```
사용자 입력 → yfinance 데이터 조회 → 일별 시뮬레이션 루프:
  ├── 리밸런싱 체크 (분기/연간)
  ├── 배당금 처리 + 배당세 즉시 적용
  ├── 인출 처리
  ├── 양도차익 기록 (리밸런싱/인출 시)
  └── 월말 스냅샷 저장
→ 연말: 양도소득세 정산
→ 1월: 이연 세금 납부
→ 결과 생성 (지표, 시각화, 로그)
```

## 기본 설정 (`config/settings.py`)

| 항목 | 기본값 |
|------|--------|
| 초기 자본금 | $1,000,000 |
| 백테스트 기간 | 10년 |
| 리밸런싱 주기 | 분기 |
| 연간 인출률 | 5% |
| 배당소득세 | 15% |
| 양도소득세 | 22% |
| 양도차익 공제 | $2,000 |
| 거래비용 | 0.2% |

### 기본 포트폴리오

| ETF | 배분 | 설명 |
|-----|------|------|
| SPY | 60% | S&P 500 Index |
| QQQ | 30% | Nasdaq 100 Index |
| BIL | 10% | 단기 국채 |

## 데이터 흐름

- **입력**: ETF 심볼, 배분 비율, 백테스트 파라미터
- **외부 데이터**: yfinance API (실시간 가격, 배당) - 로컬 DB 없음
- **처리**: 전체 이벤트 추적 포함 포트폴리오 시뮬레이션
- **출력**: 성과 지표, Plotly 시각화, 상세 거래 로그

## 코드 컨벤션

- 클래스명: PascalCase (`PortfolioBacktester`, `TaxCalculator`)
- 함수/변수: snake_case (`calculate_cagr`, `dividend_tax_rate`)
- 타입 힌트 사용
- 한글 주석 허용 (UI 문자열은 한글)

## Git 컨벤션

- PR 설명(description)은 한국어로 작성
- 커밋 메시지는 영어 또는 한국어 허용

## 면책조항

이 도구는 교육 및 연구 목적으로 제작되었습니다. 실제 투자 결정에는 신중을 기하시기 바라며, 투자로 인한 손실에 대해서는 책임지지 않습니다.

## 라이선스

MIT
