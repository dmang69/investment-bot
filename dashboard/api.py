"""FastAPI dashboard for bot monitoring and control."""

import time
import asyncio
from typing import List, Dict, Any, Optional
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel
from datetime import datetime
from execution.order_models import Portfolio
from core.logger import get_logger


logger = get_logger(__name__)


# Request/Response models
class RiskConfigRequest(BaseModel):
    """Risk configuration update request."""

    max_drawdown_pct: Optional[float] = None
    max_position_size_pct: Optional[float] = None
    max_leverage: Optional[float] = None


class HealthResponse(BaseModel):
    """Health check response."""

    status: str
    version: str
    uptime: float
    bot_running: bool


class PortfolioResponse(BaseModel):
    """Portfolio snapshot response."""

    cash: float
    total_value: float
    unrealized_pnl: float
    realized_pnl: float
    num_positions: int
    timestamp: str


class PositionResponse(BaseModel):
    """Position details response."""

    symbol: str
    quantity: float
    entry_price: float
    current_value: float
    unrealized_pnl: float


class SignalResponse(BaseModel):
    """Trading signal response."""

    timestamp: str
    symbol: str
    action: str
    confidence: float
    regime: Optional[str] = None


class RiskMetricsResponse(BaseModel):
    """Risk metrics response."""

    current_drawdown_pct: float
    max_drawdown_pct: float
    max_position_size_pct: float
    max_leverage: float
    active_positions: int
    total_exposure: float
    risk_limit_breach: bool


class AgentStatusResponse(BaseModel):
    """Agent status response."""

    agent_name: str
    running: bool
    last_update: Optional[str] = None


class TradeResponse(BaseModel):
    """Trade record response."""

    symbol: str
    side: str
    quantity: float
    price: float
    timestamp: str
    order_id: str
    commission: float


class SessionSummaryResponse(BaseModel):
    """Session summary response."""

    session_duration: int
    total_trades: int
    buy_trades: int
    sell_trades: int
    gross_pnl: float
    net_pnl: float
    win_rate: float
    start_time: str
    end_time: Optional[str] = None


def create_app(
    executor=None, event_bus=None, risk_agent=None, bot=None
) -> FastAPI:
    """
    Create FastAPI application instance.

    Args:
        executor: Order executor for portfolio access
        event_bus: Event bus for signal history
        risk_agent: Risk agent for metrics
        bot: PaperTradingBot instance for full access

    Returns:
        FastAPI application
    """
    app = FastAPI(
        title="AI Investment Bot API",
        version="1.0.0",
        description="Real-time monitoring and control API for AI investment bot",
    )

    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Store startup time
    startup_time = time.time()

    # In-memory signal history (queue-like, max 1000 signals)
    signal_history: List[Dict[str, Any]] = []
    MAX_SIGNAL_HISTORY = 1000

    # WebSocket connections for real-time updates
    class ConnectionManager:
        def __init__(self):
            self.active_connections: List[WebSocket] = []

        async def connect(self, websocket: WebSocket):
            await websocket.accept()
            self.active_connections.append(websocket)

        def disconnect(self, websocket: WebSocket):
            self.active_connections.remove(websocket)

        async def broadcast(self, message: Dict[str, Any]):
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception:
                    pass

    manager = ConnectionManager()

    @app.get("/health", response_model=HealthResponse)
    async def health_check() -> HealthResponse:
        """
        Health check endpoint.

        Returns:
            Health status with uptime and bot state
        """
        uptime = time.time() - startup_time
        bot_running = bot.running if bot else False
        
        return HealthResponse(
            status="healthy",
            version="1.0.0",
            uptime=uptime,
            bot_running=bot_running,
        )

    @app.get("/portfolio", response_model=PortfolioResponse)
    async def get_portfolio() -> PortfolioResponse:
        """
        Get current portfolio status.

        Returns:
            Portfolio snapshot with positions and P&L

        Raises:
            HTTPException: If executor not available
        """
        if executor is None:
            raise HTTPException(status_code=503, detail="Executor not available")

        portfolio = await executor.get_portfolio()

        return PortfolioResponse(
            cash=portfolio.cash,
            total_value=portfolio.total_value,
            unrealized_pnl=portfolio.unrealized_pnl,
            realized_pnl=portfolio.realized_pnl,
            num_positions=len(portfolio.positions),
            timestamp=datetime.utcnow().isoformat(),
        )

    @app.get("/positions", response_model=List[PositionResponse])
    async def get_positions() -> List[PositionResponse]:
        """
        Get detailed position information.

        Returns:
            List of open positions with detailed metrics

        Raises:
            HTTPException: If executor not available
        """
        if executor is None:
            raise HTTPException(status_code=503, detail="Executor not available")

        positions = await executor.get_positions()
        portfolio = await executor.get_portfolio()

        result = []
        for pos in positions:
            # Estimate current value (simplified)
            current_value = pos.quantity * pos.entry_price
            unrealized_pnl = current_value - (pos.quantity * pos.entry_price)

            result.append(
                PositionResponse(
                    symbol=pos.symbol,
                    quantity=pos.quantity,
                    entry_price=pos.entry_price,
                    current_value=current_value,
                    unrealized_pnl=unrealized_pnl,
                )
            )

        return result

    @app.get("/signals", response_model=List[SignalResponse])
    async def get_signals(limit: int = 20) -> List[SignalResponse]:
        """
        Get recent trading signals.

        Args:
            limit: Maximum number of signals to return (default 20)

        Returns:
            List of recent signals
        """
        # Return last N signals from history
        recent_signals = signal_history[-limit:]
        return [
            SignalResponse(
                timestamp=sig["timestamp"],
                symbol=sig["symbol"],
                action=sig["action"],
                confidence=sig.get("confidence", 0.0),
                regime=sig.get("regime"),
            )
            for sig in recent_signals
        ]

    @app.get("/risk", response_model=RiskMetricsResponse)
    async def get_risk_metrics() -> RiskMetricsResponse:
        """
        Get current risk metrics.

        Returns:
            Risk metrics including drawdown and exposure

        Raises:
            HTTPException: If risk agent not available
        """
        if risk_agent is None or executor is None:
            raise HTTPException(
                status_code=503, detail="Risk monitoring not available"
            )

        portfolio = await executor.get_portfolio()
        positions = await executor.get_positions()

        # Calculate current drawdown
        current_drawdown = 0.0
        if bot and hasattr(bot, "monitor"):
            metrics = bot.monitor.get_current_metrics()
            if metrics:
                current_drawdown = metrics.current_drawdown_pct

        # Calculate total exposure
        total_exposure = sum(pos.quantity * pos.entry_price for pos in positions)

        # Check if risk limit breached
        risk_limit_breach = (
            current_drawdown > risk_agent.max_drawdown_pct
            if hasattr(risk_agent, "max_drawdown_pct")
            else False
        )

        return RiskMetricsResponse(
            current_drawdown_pct=current_drawdown,
            max_drawdown_pct=(
                risk_agent.max_drawdown_pct
                if hasattr(risk_agent, "max_drawdown_pct")
                else 0.0
            ),
            max_position_size_pct=(
                risk_agent.max_position_size_pct
                if hasattr(risk_agent, "max_position_size_pct")
                else 0.0
            ),
            max_leverage=(
                risk_agent.max_leverage if hasattr(risk_agent, "max_leverage") else 0.0
            ),
            active_positions=len(positions),
            total_exposure=total_exposure,
            risk_limit_breach=risk_limit_breach,
        )

    @app.get("/agents/status", response_model=List[AgentStatusResponse])
    async def get_agents_status() -> List[AgentStatusResponse]:
        """
        Get status of all trading agents.

        Returns:
            List of agent statuses

        Raises:
            HTTPException: If bot not available
        """
        if bot is None or not hasattr(bot, "agents"):
            raise HTTPException(status_code=503, detail="Bot not available")

        agents_status = []
        for agent in bot.agents:
            status = AgentStatusResponse(
                agent_name=agent.name if hasattr(agent, "name") else "Unknown",
                running=agent._running if hasattr(agent, "_running") else False,
                last_update=None,
            )
            agents_status.append(status)

        return agents_status

    @app.get("/trades", response_model=List[TradeResponse])
    async def get_trades(limit: int = 50) -> List[TradeResponse]:
        """
        Get recent executed trades.

        Args:
            limit: Maximum number of trades to return

        Returns:
            List of recent trades

        Raises:
            HTTPException: If bot not available
        """
        if bot is None or not hasattr(bot, "session"):
            raise HTTPException(status_code=503, detail="Session not available")

        trades = bot.session.trades[-limit:]
        return [
            TradeResponse(
                symbol=t.symbol,
                side=t.side,
                quantity=t.quantity,
                price=t.price,
                timestamp=t.timestamp.isoformat(),
                order_id=t.order_id,
                commission=t.commission,
            )
            for t in trades
        ]

    @app.get("/session/summary", response_model=SessionSummaryResponse)
    async def get_session_summary() -> SessionSummaryResponse:
        """
        Get trading session summary.

        Returns:
            Session summary with statistics

        Raises:
            HTTPException: If session not available
        """
        if bot is None or not hasattr(bot, "session"):
            raise HTTPException(status_code=503, detail="Session not available")

        stats = bot.session.get_session_stats()

        return SessionSummaryResponse(
            session_duration=int(stats.get("duration_seconds", 0)),
            total_trades=stats.get("total_trades", 0),
            buy_trades=stats.get("buy_trades", 0),
            sell_trades=stats.get("sell_trades", 0),
            gross_pnl=stats.get("gross_pnl", 0.0),
            net_pnl=stats.get("net_pnl", 0.0),
            win_rate=stats.get("win_rate", 0.0),
            start_time=stats.get("start_time", ""),
            end_time=stats.get("end_time"),
        )

    @app.post("/config/risk")
    async def update_risk_config(config: RiskConfigRequest) -> Dict[str, str]:
        """
        Update risk configuration at runtime.

        Args:
            config: New risk configuration

        Returns:
            Confirmation message

        Raises:
            HTTPException: If risk agent not available
        """
        if risk_agent is None:
            raise HTTPException(
                status_code=503, detail="Risk agent not available"
            )

        # Update risk limits (only non-None values)
        if config.max_drawdown_pct is not None and hasattr(risk_agent, "max_drawdown_pct"):
            risk_agent.max_drawdown_pct = config.max_drawdown_pct
        if config.max_position_size_pct is not None and hasattr(risk_agent, "max_position_size_pct"):
            risk_agent.max_position_size_pct = config.max_position_size_pct
        if config.max_leverage is not None and hasattr(risk_agent, "max_leverage"):
            risk_agent.max_leverage = config.max_leverage

        logger.info(
            "risk_config_updated",
            max_drawdown=config.max_drawdown_pct,
            max_position_size=config.max_position_size_pct,
            max_leverage=config.max_leverage,
        )

        return {
            "status": "success",
            "message": "Risk configuration updated",
        }

    @app.post("/bot/stop")
    async def stop_bot() -> Dict[str, str]:
        """
        Stop the trading bot gracefully.

        Returns:
            Confirmation message

        Raises:
            HTTPException: If bot not available
        """
        if bot is None:
            raise HTTPException(status_code=503, detail="Bot not available")

        try:
            logger.info("Stop request received via API")
            asyncio.create_task(bot.stop())
            return {
                "status": "success",
                "message": "Bot stop signal sent",
            }
        except Exception as e:
            logger.error("Error stopping bot", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/bot/pause")
    async def pause_bot() -> Dict[str, str]:
        """
        Pause the trading bot (stop generating new signals).

        Returns:
            Confirmation message

        Raises:
            HTTPException: If bot not available
        """
        if bot is None:
            raise HTTPException(status_code=503, detail="Bot not available")

        try:
            bot._signal_received = True
            logger.info("Pause signal sent to bot")
            return {
                "status": "success",
                "message": "Bot paused",
            }
        except Exception as e:
            logger.error("Error pausing bot", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.post("/bot/resume")
    async def resume_bot() -> Dict[str, str]:
        """
        Resume the trading bot.

        Returns:
            Confirmation message

        Raises:
            HTTPException: If bot not available
        """
        if bot is None:
            raise HTTPException(status_code=503, detail="Bot not available")

        try:
            bot._signal_received = False
            logger.info("Resume signal sent to bot")
            return {
                "status": "success",
                "message": "Bot resumed",
            }
        except Exception as e:
            logger.error("Error resuming bot", error=str(e))
            raise HTTPException(status_code=500, detail=str(e))

    @app.get("/", response_class=HTMLResponse)
    async def serve_dashboard() -> str:
        """Serve the web dashboard HTML."""
        return DASHBOARD_HTML

    @app.websocket("/ws/portfolio")
    async def websocket_portfolio(websocket: WebSocket):
        """WebSocket endpoint for real-time portfolio updates."""
        await manager.connect(websocket)
        try:
            while True:
                # Keep connection alive
                await websocket.receive_text()
        except WebSocketDisconnect:
            manager.disconnect(websocket)

    @app.post("/api/signal")
    async def record_signal(signal: Dict[str, Any]) -> Dict[str, str]:
        """
        Record a trading signal for history tracking.
        (Internal endpoint for event bus integration)

        Args:
            signal: Signal data

        Returns:
            Confirmation
        """
        # Add to history
        signal_history.append(signal)

        # Maintain max size
        while len(signal_history) > MAX_SIGNAL_HISTORY:
            signal_history.pop(0)

        # Broadcast to WebSocket clients
        await manager.broadcast({"type": "new_signal", "signal": signal})

        logger.debug("Signal recorded", symbol=signal.get("symbol"))
        return {"status": "recorded"}

    @app.on_event("startup")
    async def startup_event():
        """Initialize dashboard on startup."""
        logger.info("Dashboard API started on http://127.0.0.1:8000")

    @app.on_event("shutdown")
    async def shutdown_event():
        """Clean up on shutdown."""
        logger.info("Dashboard API shutdown")

    return app


# Embedded HTML Dashboard
DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI Investment Bot Dashboard</title>
    <style>
        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }
        
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        
        .container {
            max-width: 1400px;
            margin: 0 auto;
            background: white;
            border-radius: 10px;
            box-shadow: 0 10px 40px rgba(0,0,0,0.2);
            overflow: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }
        
        .header h1 {
            font-size: 2.5em;
            margin-bottom: 10px;
        }
        
        .header p {
            font-size: 1.1em;
            opacity: 0.9;
        }
        
        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 20px;
            padding: 30px;
        }
        
        .card {
            background: #f8f9fa;
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s, box-shadow 0.2s;
        }
        
        .card:hover {
            transform: translateY(-5px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.15);
        }
        
        .card h3 {
            color: #667eea;
            margin-bottom: 15px;
            font-size: 1.1em;
        }
        
        .metric {
            font-size: 2em;
            font-weight: bold;
            color: #333;
            margin: 10px 0;
        }
        
        .metric.positive {
            color: #28a745;
        }
        
        .metric.negative {
            color: #dc3545;
        }
        
        .label {
            color: #666;
            font-size: 0.9em;
            margin-top: 10px;
        }
        
        .status {
            display: inline-block;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 0.9em;
            font-weight: bold;
            margin: 10px 0;
        }
        
        .status.running {
            background: #d4edda;
            color: #155724;
        }
        
        .status.stopped {
            background: #f8d7da;
            color: #721c24;
        }
        
        .controls {
            padding: 20px 30px;
            background: #f8f9fa;
            border-top: 1px solid #e0e0e0;
            display: flex;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        button {
            background: #667eea;
            color: white;
            border: none;
            padding: 12px 24px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 1em;
            font-weight: 500;
            transition: all 0.2s;
        }
        
        button:hover {
            background: #764ba2;
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0,0,0,0.2);
        }
        
        button.danger {
            background: #dc3545;
        }
        
        button.danger:hover {
            background: #c82333;
        }
        
        .trades-list {
            padding: 20px 30px;
            background: white;
            max-height: 400px;
            overflow-y: auto;
        }
        
        .trade-item {
            padding: 10px;
            border-bottom: 1px solid #e0e0e0;
            display: grid;
            grid-template-columns: 80px 80px 100px 100px 1fr;
            gap: 10px;
            font-size: 0.9em;
        }
        
        .trade-item.buy {
            background: rgba(40, 167, 69, 0.1);
        }
        
        .trade-item.sell {
            background: rgba(220, 53, 69, 0.1);
        }
        
        .trade-symbol {
            font-weight: bold;
        }
        
        .trade-side {
            font-weight: bold;
        }
        
        .trade-side.buy {
            color: #28a745;
        }
        
        .trade-side.sell {
            color: #dc3545;
        }
        
        .refresh-time {
            text-align: center;
            padding: 10px;
            color: #999;
            font-size: 0.9em;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🤖 AI Investment Bot</h1>
            <p>Real-Time Trading Dashboard & Control Center</p>
        </div>
        
        <div class="grid">
            <div class="card">
                <h3>Portfolio Value</h3>
                <div class="metric" id="portfolio-value">$0.00</div>
                <div class="label">Total Equity</div>
            </div>
            
            <div class="card">
                <h3>Available Cash</h3>
                <div class="metric" id="cash">$0.00</div>
                <div class="label">Buying Power</div>
            </div>
            
            <div class="card">
                <h3>P&L</h3>
                <div class="metric" id="pnl">$0.00</div>
                <div class="label">Realized + Unrealized</div>
            </div>
            
            <div class="card">
                <h3>Drawdown</h3>
                <div class="metric" id="drawdown">0.00%</div>
                <div class="label">From Peak Equity</div>
            </div>
            
            <div class="card">
                <h3>Active Positions</h3>
                <div class="metric" id="positions">0</div>
                <div class="label">Open Trades</div>
            </div>
            
            <div class="card">
                <h3>Bot Status</h3>
                <div id="bot-status" class="status running">Running</div>
                <div class="label">Trading System</div>
            </div>
        </div>
        
        <div class="controls">
            <button onclick="refreshData()">🔄 Refresh</button>
            <button onclick="pauseBot()">⏸ Pause</button>
            <button onclick="resumeBot()">▶ Resume</button>
            <button class="danger" onclick="stopBot()">⏹ Stop</button>
        </div>
        
        <div class="trades-list">
            <strong>Recent Trades:</strong>
            <div id="trades-container" style="margin-top: 10px;"></div>
        </div>
        
        <div class="refresh-time">
            Last updated: <span id="last-update">--:--:--</span>
        </div>
    </div>
    
    <script>
        async function refreshData() {
            try {
                // Get portfolio
                const portfolio = await fetch('/portfolio').then(r => r.json());
                document.getElementById('portfolio-value').textContent = '$' + portfolio.total_value.toFixed(2);
                document.getElementById('cash').textContent = '$' + portfolio.cash.toFixed(2);
                const totalPnL = portfolio.unrealized_pnl + portfolio.realized_pnl;
                document.getElementById('pnl').textContent = '$' + totalPnL.toFixed(2);
                document.getElementById('positions').textContent = portfolio.num_positions;
                
                // Get risk metrics
                const risk = await fetch('/risk').then(r => r.json());
                document.getElementById('drawdown').textContent = risk.current_drawdown_pct.toFixed(2) + '%';
                
                // Get health
                const health = await fetch('/health').then(r => r.json());
                const statusEl = document.getElementById('bot-status');
                statusEl.textContent = health.bot_running ? 'Running' : 'Stopped';
                statusEl.className = 'status ' + (health.bot_running ? 'running' : 'stopped');
                
                // Get trades
                const trades = await fetch('/trades?limit=10').then(r => r.json());
                const tradesHtml = trades.map(t => `
                    <div class="trade-item ${t.side.toLowerCase()}">
                        <div class="trade-symbol">${t.symbol}</div>
                        <div class="trade-side ${t.side.toLowerCase()}">${t.side}</div>
                        <div>${t.quantity}</div>
                        <div>$${t.price.toFixed(2)}</div>
                        <div>${new Date(t.timestamp).toLocaleTimeString()}</div>
                    </div>
                `).join('');
                
                document.getElementById('trades-container').innerHTML = tradesHtml || '<p style="color: #999;">No trades yet</p>';
                
                // Update timestamp
                document.getElementById('last-update').textContent = new Date().toLocaleTimeString();
                
            } catch(e) {
                console.error('Error refreshing data:', e);
            }
        }
        
        async function stopBot() {
            if (confirm('Are you sure you want to stop the bot? This cannot be undone immediately.')) {
                try {
                    await fetch('/bot/stop', {method: 'POST'});
                    alert('Bot stop signal sent');
                    setTimeout(refreshData, 1000);
                } catch(e) {
                    alert('Error: ' + e.message);
                }
            }
        }
        
        async function pauseBot() {
            try {
                await fetch('/bot/pause', {method: 'POST'});
                alert('Bot paused');
            } catch(e) {
                alert('Error: ' + e.message);
            }
        }
        
        async function resumeBot() {
            try {
                await fetch('/bot/resume', {method: 'POST'});
                alert('Bot resumed');
            } catch(e) {
                alert('Error: ' + e.message);
            }
        }
        
        // Initial load and auto-refresh
        refreshData();
        setInterval(refreshData, 5000);
    </script>
</body>
</html>
"""
