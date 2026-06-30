# AI Investment Bot - Complete Implementation

## 📋 Overview

This is a **fully-functional paper trading bot** with:
- ✅ Real trading agents (crypto & equity)
- ✅ Intelligent signal aggregation
- ✅ Portfolio monitoring and risk management
- ✅ Complete REST API with web dashboard
- ✅ Real-time control and monitoring

---

## 🚀 Quick Start

### 1. **Install Dependencies**
```bash
pip install -r requirements.txt
```

### 2. **Start the Bot**
```bash
python main.py
```

**Output:**
```
2024-01-15 14:30:00 INFO: Starting AI Investment Bot
2024-01-15 14:30:00 INFO: Dashboard API started at http://127.0.0.1:8000
```

### 3. **Access Dashboard**
Open in browser: `http://127.0.0.1:8000`

---

## 📊 Dashboard Features

### Real-Time Monitoring
- **Portfolio Value**: Total equity and cash
- **P&L Metrics**: Realized and unrealized gains/losses
- **Drawdown**: Current drawdown from peak equity
- **Active Positions**: Number of open trades
- **Bot Status**: Running/stopped indicator

### Control Buttons
- 🔄 **Refresh**: Update all metrics
- ⏸ **Pause**: Stop generating new signals
- ▶ **Resume**: Resume trading
- ⏹ **Stop**: Graceful bot shutdown

### Trade History
- Recent executed trades
- Symbol, side (BUY/SELL), quantity, price
- Execution timestamp
- Auto-updates every 5 seconds

---

## 🔌 REST API Endpoints

### Health & Status
```bash
curl http://127.0.0.1:8000/health
```

### Portfolio
```bash
curl http://127.0.0.1:8000/portfolio
```

### Risk Metrics
```bash
curl http://127.0.0.1:8000/risk
```

### Recent Trades
```bash
curl "http://127.0.0.1:8000/trades?limit=50"
```

### Session Summary
```bash
curl http://127.0.0.1:8000/session/summary
```

### Control Bot
```bash
# Pause trading
curl -X POST http://127.0.0.1:8000/bot/pause

# Resume trading
curl -X POST http://127.0.0.1:8000/bot/resume

# Stop bot
curl -X POST http://127.0.0.1:8000/bot/stop
```

---

## 🤖 Trading Agents

### CryptoTradingAgent
- **Updates**: Every 60 seconds
- **Symbols**: BTC/USDT, ETH/USDT
- **Operation**: 24/7

### EquityTradingAgent
- **Updates**: 60 seconds during market hours, 300 seconds outside
- **Symbols**: AAPL, MSFT, GOOG
- **Operation**: US market hours (9:30 AM - 4:00 PM ET, Mon-Fri)

---

## ⚙️ Configuration

### Initial Cash
```python
initial_cash: float = 100000.0
```

### Risk Limits
```python
max_drawdown_pct: float = 20.0
max_position_size_pct: float = 10.0
max_leverage: float = 2.0
```

---

## 📈 Trading Workflow

```
MarketRegimeAgent → Analyzes market
   ↓ publishes: regime_change
   
CryptoTradingAgent & EquityTradingAgent:
   - Fetch OHLCV data
   - Generate signals
   - Aggregate with regime weights
   ↓ publish: crypto_signal, equity_signal
   
PaperTradingBot Orchestrator:
   - Receives signals
   - Validates via RiskAgent
   - Executes trade
   ↓ record in TradingSession
   
PortfolioMonitor:
   - Tracks metrics
   - Detects alerts
   
Dashboard API:
   - Exposes metrics via REST
   - WebSocket updates
   - HTML visualization
```

---

## 🛑 Stopping the Bot

### Method 1: Dashboard
Click the **⏹ Stop** button

### Method 2: API
```bash
curl -X POST http://127.0.0.1:8000/bot/stop
```

### Method 3: Console
Press `Ctrl+C`

---

## ✅ Implementation Status

**COMPLETE AND OPERATIONAL** ✅

All components implemented:
- [x] CryptoTradingAgent with full trading logic
- [x] EquityTradingAgent with market hours awareness
- [x] PaperTradingBot orchestration
- [x] PortfolioMonitor with alerts
- [x] TradingSession tracking
- [x] REST API with 15+ endpoints
- [x] WebSocket support
- [x] Embedded HTML dashboard
- [x] Risk management system
- [x] Event-driven architecture

---

**Status**: ✅ COMPLETE  
**Version**: 1.0.0
