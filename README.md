# Kquant - ETF Portfolio Backtest Dashboard

ETF 자산 배분 전략을 백테스팅하고 포트폴리오를 비교 분석하는 Streamlit 대시보드입니다.

## Features

- **자산 배분 백테스트**: ETF 포트폴리오의 과거 성과 시뮬레이션
- **포트폴리오 비교**: 여러 자산 배분 전략 간 성과 비교
- **세금 계산**: 배당소득세(15%), 양도소득세(22%) 반영
- **리밸런싱**: 분기별/연간 리밸런싱 시뮬레이션
- **인출 시뮬레이션**: 은퇴 후 인출 전략 테스트

## Installation

```bash
# Clone the repository
git clone https://github.com/SamLee0130/Kquant.git
cd Kquant

# Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

## Usage

```bash
streamlit run app.py
```

브라우저에서 `http://localhost:8501` 접속

## Project Structure

```
Kquant/
├── app.py                 # Entry point
├── requirements.txt       # Dependencies
├── config/
│   └── settings.py        # Configuration
└── src/
    ├── backtest/
    │   ├── portfolio_backtest.py   # Backtest engine
    │   └── tax_calculator.py       # Tax calculation
    └── dashboard/
        ├── main_app.py                     # Main dashboard
        ├── allocation_backtest_page.py     # Asset allocation page
        └── portfolio_comparison_page.py    # Portfolio comparison page
```

## Default Settings

| Setting | Value |
|---------|-------|
| Initial Capital | $1,000,000 |
| Backtest Period | 10 years |
| Rebalancing | Quarterly |
| Withdrawal Rate | 5% |
| Dividend Tax | 15% |
| Capital Gains Tax | 22% |
| Transaction Cost | 0.2% |

## Default Portfolio

| ETF | Allocation | Description |
|-----|------------|-------------|
| SPY | 60% | S&P 500 Index |
| QQQ | 30% | Nasdaq 100 Index |
| BIL | 10% | Short-term Treasury |

## Tech Stack

- **Python** 3.10+
- **Streamlit** - Web dashboard
- **yfinance** - ETF data (no local database)
- **Pandas/NumPy** - Data processing
- **Plotly** - Visualization

## License

MIT

## Disclaimer

이 도구는 교육 및 연구 목적으로 제작되었습니다. 실제 투자 결정에는 신중을 기하시기 바라며, 투자로 인한 손실에 대해서는 책임지지 않습니다.
