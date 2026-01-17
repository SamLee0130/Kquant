-- Kquant 백테스트 데이터베이스 스키마
-- SQLite용 테이블 생성 스크립트

-- 1. 종목 정보 테이블
CREATE TABLE IF NOT EXISTS symbols (
    symbol TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT NOT NULL,  -- 'stock', 'crypto', 'forex'
    currency TEXT DEFAULT 'KRW',
    sector TEXT,
    industry TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. 일일 가격 데이터 테이블 (OHLCV)
CREATE TABLE IF NOT EXISTS daily_prices (
    symbol TEXT,
    date DATE,
    open REAL NOT NULL,
    high REAL NOT NULL,
    low REAL NOT NULL,
    close REAL NOT NULL,
    volume INTEGER DEFAULT 0,
    adj_close REAL,  -- 조정 종가 (주식용)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (symbol, date),
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- 3. 투자 전략 정보 테이블
CREATE TABLE IF NOT EXISTS strategies (
    strategy_id TEXT PRIMARY KEY,
    strategy_name TEXT NOT NULL,
    description TEXT,
    parameters TEXT,  -- JSON 형태로 파라미터 저장
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 4. 백테스트 실행 정보 테이블
CREATE TABLE IF NOT EXISTS backtest_runs (
    run_id TEXT PRIMARY KEY,
    strategy_id TEXT NOT NULL,
    symbols TEXT NOT NULL,  -- 쉼표로 구분된 종목 리스트
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    initial_capital REAL NOT NULL DEFAULT 1000000,
    run_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT DEFAULT 'completed',
    FOREIGN KEY (strategy_id) REFERENCES strategies(strategy_id)
);

-- 5. 백테스트 결과 요약 테이블
CREATE TABLE IF NOT EXISTS backtest_results (
    run_id TEXT,
    total_return REAL,
    annual_return REAL,
    volatility REAL,
    sharpe_ratio REAL,
    max_drawdown REAL,
    max_drawdown_duration INTEGER,
    total_trades INTEGER,
    win_rate REAL,
    profit_factor REAL,
    final_capital REAL,
    PRIMARY KEY (run_id),
    FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
);

-- 6. 포트폴리오 일별 이력 테이블
CREATE TABLE IF NOT EXISTS portfolio_history (
    run_id TEXT,
    date DATE,
    total_value REAL,
    cash REAL,
    positions_value REAL,
    daily_return REAL,
    cumulative_return REAL,
    drawdown REAL,
    PRIMARY KEY (run_id, date),
    FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id)
);

-- 7. 거래 내역 테이블
CREATE TABLE IF NOT EXISTS trades (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    symbol TEXT NOT NULL,
    trade_type TEXT NOT NULL,  -- 'BUY', 'SELL'
    quantity REAL NOT NULL,
    price REAL NOT NULL,
    trade_date DATE NOT NULL,
    commission REAL DEFAULT 0,
    total_amount REAL NOT NULL,
    signal_reason TEXT,  -- 매매 신호 이유
    FOREIGN KEY (run_id) REFERENCES backtest_runs(run_id),
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- 8. 기술지표 데이터 테이블 (선택적)
CREATE TABLE IF NOT EXISTS technical_indicators (
    symbol TEXT,
    date DATE,
    indicator_name TEXT,
    value REAL,
    PRIMARY KEY (symbol, date, indicator_name),
    FOREIGN KEY (symbol) REFERENCES symbols(symbol)
);

-- 인덱스 생성 (성능 향상)
CREATE INDEX IF NOT EXISTS idx_daily_prices_date ON daily_prices(date);
CREATE INDEX IF NOT EXISTS idx_daily_prices_symbol_date ON daily_prices(symbol, date);
CREATE INDEX IF NOT EXISTS idx_portfolio_history_date ON portfolio_history(date);
CREATE INDEX IF NOT EXISTS idx_trades_date ON trades(trade_date);
CREATE INDEX IF NOT EXISTS idx_trades_symbol ON trades(symbol);

-- 뷰 생성 (편의를 위한 자주 사용되는 쿼리)
CREATE VIEW IF NOT EXISTS latest_prices AS
SELECT 
    symbol,
    date,
    close as latest_price,
    volume
FROM daily_prices dp1
WHERE date = (
    SELECT MAX(date) 
    FROM daily_prices dp2 
    WHERE dp2.symbol = dp1.symbol
);

CREATE VIEW IF NOT EXISTS portfolio_performance AS
SELECT 
    br.run_id,
    s.strategy_name,
    br.symbols,
    br.start_date,
    br.end_date,
    br.initial_capital,
    br.run_date,
    res.total_return,
    res.annual_return,
    res.sharpe_ratio,
    res.max_drawdown,
    res.total_trades,
    res.win_rate,
    res.final_capital
FROM backtest_runs br
LEFT JOIN strategies s ON br.strategy_id = s.strategy_id
LEFT JOIN backtest_results res ON br.run_id = res.run_id;
