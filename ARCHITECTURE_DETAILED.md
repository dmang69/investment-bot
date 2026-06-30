# Paper Trading Bot - Architecture & Component Interaction

## System Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     PAPER TRADING BOT ORCHESTRATOR                       │
│                          (PaperTradingBot)                              │
│                                                                         │
│  ┌─────────────────┐  ┌─────────────────┐  ┌──────────────────────┐   │
│  │  Event Bus      │  │  Paper Executor │  │  Portfolio Monitor   │   │
│  │  (pub/sub)      │  │  (in-memory)    │  │  (real-time metrics) │   │
│  │                 │  │  - Positions    │  │  - Equity tracking   │   │
│  │  Topics:        │  │  - Cash balance │  │  - Drawdown calc     │   │
│  │  - regime_*     │  │  - Trade hist   │  │  - Alert system      │   │
│  │  - signal_*     │  │  - P&L calcs    │  │                      │   │
│  │  - trade_*      │  └─────────────────┘  └──────────────────────┘   │
│  │  - alert_*      │                                                    │
│  │  - portfolio_*  │  ┌──────────────────────────────────────────────┐ │
│  │                 │  │  Trading Session                             │ │
│  └────────┬────────┘  │  - Tracks all trades                         │ │
│           │           │  - Calculates statistics                     │ │
│           │           │  - Generates reports                         │ │
│           │           │  - Exports to JSON                           │ │
│           │           └──────────────────────────────────────────────┘ │
└───────────┼─────────────────────────────────────────────────────────────┘
            │
            │ publishes/subscribes
            │
    ┌───────┴─────────────────────────────────────────────┐
    │                                                     │
    ▼                                                     ▼
┌──────────────────┐          ┌────────────────┐    ┌────────────────┐
│  REGIME AGENT    │          │  RISK AGENT    │    │  MONITORING    │
│                  │          │                │    │  & ALERTS      │
│ Detects:         │          │ Validates:     │    │                │
│ - Trend up/down  │          │ - Position sz  │    │ Emits:         │
│ - Volatility     │          │ - Leverage     │    │ - Drawdown     │
│ - Choppy/smooth  │          │ - Drawdown     │    │ - Position sz  │
│                  │          │                │    │ - Returns      │
│ Emits:           │          │ Emits:         │    │                │
│ regime_change    │          │ signal_*       │    │ (Auto-alerts)  │
└──────────────────┘          └────────────────┘    └────────────────┘
    ▲                               ▲
    │                               │
    │      ┌──────────────────┐     │
    │      │   STRATEGIES     │     │
    │      │                  │     │
    │      │ - TrendFollowing │     │
    │      │   (EMA cross)    │     │
    │      │                  │     │
    │      │ - MeanReversion  │     │
    │      │   (Z-score)      │     │
    │      │                  │     │
    │      └─────────┬────────┘     │
    │              │                │
    └──────────────┼────────────────┘
                   │
    ┌──────────────┴────────────────────┐
    │                                   │
    ▼                                   ▼
┌──────────────────────────┐   ┌──────────────────────────┐
│  CRYPTO TRADING AGENT    │   │ EQUITY TRADING AGENT     │
│                          │   │                          │
│ Monitors: BTC, ETH, etc  │   │ Monitors: AAPL, MSFT... │
│                          │   │                          │
│ Data Source:             │   │ Data Source:             │
│ CryptoDataProvider       │   │ StockDataProvider        │
│ (CCXT/Binance)          │   │ (Alpaca)                 │
│                          │   │                          │
│ Updates: Every 60sec     │   │ Updates: 60sec (open)    │
│ Continuous              │   │ 300sec (closed)          │
│                          │   │ (Market hours aware)     │
│                          │   │                          │
│ Emits: crypto_signal     │   │ Emits: equity_signal     │
└──────────────┬───────────┘   └──────────────┬───────────┘
               │                              │
               └──────────────┬───────────────┘
                              │
                              ▼
                    ┌──────────────────┐
                    │  BOT ORCHESTRATOR │
                    │                   │
                    │  Routes signals to│
                    │  execution layer  │
                    │                   │
                    │  Flow:            │
                    │  1. Receive signal│
                    │  2. Create Order  │
                    │  3. Execute       │
                    │  4. Record trade  │
                    │  5. Emit event    │
                    │                   │
                    └───────────────────┘
```

## Data Flow - Signal to Execution

### 1. Signal Generation Phase
```
Crypto Agent / Equity Agent
├── Fetch OHLCV data via provider
├── Apply Trend Following Strategy
│   └── Calculate EMA(20) and EMA(50)
│       └── Generate BUY/SELL/HOLD + confidence
├── Apply Mean Reversion Strategy
│   └── Calculate Z-score
│       └── Generate BUY/SELL/HOLD + confidence
└── Aggregate Signals
    ├── Get regime from current_regime dict
    ├── Look up strategy weights for regime
    │   (Trending: trend=70%, mean=30%)
    │   (Choppy:   trend=30%, mean=70%)
    ├── Calculate weighted buy/sell confidence
    └── Emit crypto_signal or equity_signal event
```

### 2. Risk Validation Phase
```
Risk Agent (subscribes to trading_signal)
├── Check current drawdown vs limit (20%)
├── Check position size vs limit (10%)
├── Check leverage vs limit (2x)
└── If all pass:
    └── Emit signal_approved
    If any fail:
    └── Emit signal_rejected
```

### 3. Execution Phase
```
Bot Orchestrator (subscribes to signal_approved)
├── Create Order object
│   ├── Symbol from signal
│   ├── Side (BUY or SELL)
│   ├── Quantity (risk-sized)
│   └── Limit price
├── Execute via PaperExecutor.place_order()
│   ├── Validate order
│   ├── Add simulated slippage (+5 bps)
│   ├── Calculate commission (0.1%)
│   └── Return Fill
├── Record in TradingSession
│   └── Store trade details for reporting
└── Emit trade_executed event
```

### 4. Monitoring Phase
```
Portfolio Monitor (continuous background)
├── Every 30 seconds:
│   ├── Get portfolio state from executor
│   ├── Calculate metrics
│   │   ├── Current equity
│   │   ├── Cash balance
│   │   ├── Total P&L
│   │   ├── Return %
│   │   └── Drawdown %
│   └── Check alerts
│       ├── Drawdown warning (>16%)
│       ├── Position size warning (>10%)
│       └── Return alerts (>10% or <-10%)
└── Emit portfolio_updated event
```

## Regime-Based Strategy Weighting

```
Market Regime          Trend Following    Mean Reversion     Rationale
─────────────────────  ────────────────    ──────────────     ──────────
TRENDING_UP/DOWN              70%                30%          Follow momentum
CHOPPY                        30%                70%          Bounce back trades
HIGH_VOL                      50%                50%          Both useful
LOW_VOL                       40%                60%          Range-bound
DEFAULT                       50%                50%          Neutral stance
```

## Component Interactions

### MarketRegimeAgent
```
Input:  OHLCV data (via event from data providers)
Logic:  Calculate EMA slope + ATR for regime classification
Output: regime_change event {symbol, regime, timestamp}
Listen: ohlcv_update events
```

### CryptoTradingAgent
```
Input:  regime_change events + Fresh OHLCV data (fetched)
Logic:  Apply strategies with regime-weighted allocation
Output: crypto_signal event {symbol, action, confidence}
Listen: regime_change events
Period: Every 60 seconds (default)
```

### EquityTradingAgent
```
Input:  regime_change events + Fresh OHLCV data (fetched)
Logic:  Apply strategies with regime-weighted allocation
Output: equity_signal event {symbol, action, confidence}
Listen: regime_change events
Period: 60s (9:30-16:00 ET), 300s (off-hours)
```

### RiskAgent
```
Input:  trading_signal events {signal, portfolio}
Logic:  Validate against max_drawdown, max_position, max_leverage
Output: signal_approved OR signal_rejected events
Listen: trading_signal events
```

### PaperTradingBot (Orchestrator)
```
Input:  signal_approved events {signal}
Logic:  Create Order + Execute + Record + Track
Output: trade_executed event {symbol, qty, price, timestamp}
Listen: crypto_signal, equity_signal, signal_approved, kill_switch
```

### PortfolioMonitor
```
Input:  portfolio_updated events OR polling executor
Logic:  Calculate metrics + detect violations
Output: portfolio_updated events, alert_* events
Listen: Continuous monitoring (every 30s)
```

### TradingSession
```
Input:  record_trade() calls from orchestrator
Logic:  Accumulate trades + calculate statistics
Output: Session report + JSON export
```

## State Management

### Global State (Bot Level)
```python
bot._running: bool                      # Bot lifecycle state
bot._kill_switch_triggered: bool       # Emergency halt flag
bot._signal_received: bool             # SIGINT/SIGTERM received
```

### Agent State
```python
crypto_agent._running: bool            # Agent lifecycle
crypto_agent._current_regime: Dict     # symbol → regime mapping
crypto_agent._strategy_weights: Dict   # symbol → StrategyWeights
crypto_agent._ohlcv_cache: Dict        # symbol → List[OHLCV]

equity_agent._running: bool            # Same as crypto
equity_agent._current_regime: Dict
equity_agent._strategy_weights: Dict
equity_agent._ohlcv_cache: Dict
```

### Portfolio State
```python
executor._cash: float                  # Available cash
executor._positions: Dict              # symbol → Position
executor._trade_history: List[Fill]    # All fills

monitor.metrics_history: List[Metrics] # Historical snapshots
monitor.peak_equity: float             # For drawdown calc

session.trades: List[TradeRecord]      # All trades executed
session.portfolio_snapshots: List      # Portfolio timeline
```

## Message Passing

### Topics and Payloads

#### regime_change
```json
{
  "symbol": "BTC/USDT",
  "regime": "TRENDING_UP",
  "timestamp": "2026-06-30T12:00:00Z"
}
```

#### crypto_signal / equity_signal
```json
{
  "symbol": "BTC/USDT",
  "signal": {
    "symbol": "BTC/USDT",
    "action": "BUY",
    "confidence": 0.85,
    "metadata": {...}
  },
  "timestamp": "2026-06-30T12:00:00Z"
}
```

#### trading_signal
```json
{
  "signal": {
    "symbol": "BTC/USDT",
    "action": "BUY",
    "quantity": 0.5,
    "entry_price": 50000,
    "metadata": {...}
  },
  "portfolio": {
    "cash": 100000,
    "positions": {"ETH/USDT": 1.0},
    "entry_prices": {"ETH/USDT": 3000}
  }
}
```

#### signal_approved / signal_rejected
```json
{
  "signal": {...},
  "reason": "optional rejection reason"
}
```

#### trade_executed
```json
{
  "symbol": "BTC/USDT",
  "side": "BUY",
  "quantity": 0.5,
  "fill_price": 50002.50,
  "timestamp": "2026-06-30T12:00:01Z",
  "order_id": "ORDER-1-abc123de"
}
```

#### portfolio_updated
```json
{
  "metrics": {
    "timestamp": "2026-06-30T12:00:30Z",
    "equity": 105000.50,
    "cash": 60000.00,
    "total_positions": 2,
    "unrealized_pnl": 5000.50,
    "realized_pnl": 0.00,
    "total_pnl": 5000.50,
    "return_pct": 5.00,
    "current_drawdown_pct": 0.00
  },
  "positions": [...]
}
```

#### kill_switch
```json
{
  "reason": "drawdown_breach|leverage_breach|manual_halt"
}
```

## Concurrency Model

```
Main Event Loop (asyncio.run)
├── Bot.execute_bot_lifecycle()
│   ├── Bot.start()
│   │   ├── Agent.start() × 4 (parallel)
│   │   │   ├── RegimeAgent.start()
│   │   │   ├── CryptoAgent.start()
│   │   │   ├── EquityAgent.start()
│   │   │   └── RiskAgent.start()
│   │   └── Subscribe to events
│   │
│   └── Bot.run()
│       └── Main coordination loop (while self._running)
│           ├── await monitor.monitor_portfolio()
│           └── await asyncio.sleep(30)
│
├── Background Thread
│   └── API Server (uvicorn)
│       └── Dashboard REST API
│
└── All Agents Running Concurrently
    ├── CryptoAgent.run() [async, sleeps 60s]
    ├── EquityAgent.run() [async, sleeps 60-300s]
    ├── RegimeAgent.run() [async, sleeps 60s]
    └── RiskAgent.run() [async, sleeps 30s]
```

All agents process events asynchronously via event bus without blocking each other.

## Performance Characteristics

| Component | Frequency | Latency Impact |
|-----------|-----------|----------------|
| Crypto Agent | 60s | Low - background |
| Equity Agent | 60-300s | Low - market-aware |
| Regime Agent | 60s | Low - background |
| Risk Agent | On-demand | Low - validation |
| Portfolio Monitor | 30s | Minimal - monitoring |
| Event Bus | Sub-millisecond | Negligible |

Total latency from signal to execution: **<1 second** (constrained by API calls)

## Error Recovery

```
Error Handling Flow:

Data Fetch Error
└── Log warning
└── Skip symbol
└── Continue loop

Signal Generation Error
└── Log error
└── Mark as HOLD
└── Try next strategy
└── Continue

Execution Error
└── Log error
└── Publish to event bus
└── Continue monitoring

Risk Validation Error
└── Log error
└── Reject signal
└── Continue

Critical Error (Kill Switch)
└── Log critical
└── Stop all agents
└── Finalize session
└── Save results
```

**No crashes** - all operations wrapped in try-catch with proper logging and continuation.
