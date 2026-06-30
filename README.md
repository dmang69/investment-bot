# AI Investment Bot

A production-ready, multi-asset investment bot framework supporting cryptocurrency and equities trading with intelligent agents, adaptive strategies, and real-time risk management.

## Features

- **Multi-Agent Architecture**: Market regime detection, crypto/equity trading, and risk management agents
- **Adaptive Strategies**: Trend-following and mean-reversion strategies with real-time signal generation
- **Risk Management**: Drawdown limits, position sizing, and portfolio exposure controls
- **Paper Trading**: Full simulation environment for backtesting and live paper trading
- **Real-time Dashboard**: FastAPI-based monitoring and configuration API
- **Event-Driven**: Async pub/sub architecture for loosely-coupled agent coordination
- **Production Logging**: Structured JSON logging with context tracking

## Quick Start

### Installation

```bash
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your API keys
```

### Running

```bash
python main.py
```

The bot will:
1. Initialize all agents and strategies
2. Start the market regime detection agent
3. Begin trading signal generation
4. Launch the FastAPI dashboard on http://localhost:8000

### Dashboard

- Health Check: `GET /health`
- Portfolio Status: `GET /portfolio`
- Signal History: `GET /signals`
- Risk Metrics: `GET /risk`
- Update Risk Config: `POST /config/risk`

## Architecture

### Core Components

- **Config**: Environment-based settings with Pydantic validation
- **Logger**: Structured logging with JSON formatter
- **Event Bus**: Async pub/sub for agent communication
- **Data Providers**: Abstract interfaces for crypto and stock data

### Agents

- **MarketRegimeAgent**: Classifies market conditions (trending, choppy, volatile)
- **CryptoTradingAgent**: Generates crypto trading signals
- **EquityTradingAgent**: Generates equity trading signals
- **RiskAgent**: Enforces portfolio risk constraints

### Strategies

- **TrendFollowingStrategy**: EMA crossover-based trend detection
- **MeanReversionStrategy**: Z-score based mean reversion

### Execution

- **PaperExecutor**: Full in-memory portfolio simulation with P&L tracking

## Configuration

See `.env.example` for all available settings. Key configurations:

- **Exchange APIs**: Binance, Alpaca credentials
- **Risk Limits**: Max drawdown, position size, leverage
- **Trading Mode**: Paper trading (simulated) or live
- **Logging**: Structured logs with configurable level

## Development

```bash
# Install dev dependencies
pip install pytest pytest-asyncio pytest-cov

# Run tests
pytest

# Format code
black .

# Lint
flake8 .

# Type checking
mypy .
```

## Production Deployment

1. Set environment variables for all API keys
2. Configure risk limits appropriately
3. Run backtests on historical data
4. Deploy with process manager (systemd, supervisor)
5. Monitor logs and dashboard continuously
6. Implement alerting on risk breach events

## Safety & Risk

⚠️ **WARNING**: This bot can execute real trades. Always:
- Start in paper trading mode
- Backtest thoroughly
- Use conservative position sizing
- Monitor risk metrics continuously
- Test on small amounts before scaling
- Have a kill-switch ready

## License

Proprietary - AI Investment Bot Framework
