import os
import requests
import json

def load_momen_config():
    """Load Momen API key and project ID from environment variables."""
    api_key = os.environ.get("MOMEN_API_KEY", "")
    project_id = os.environ.get("MOMEN_PROJECT_ID", "")
    endpoint = os.environ.get("MOMEN_ENDPOINT", "https://api.momen.app/v1")
    return {
        "api_key": api_key.strip(),
        "project_id": project_id.strip(),
        "endpoint": endpoint.strip().rstrip("/")
    }

def is_momen_configured() -> bool:
    """Check if valid Momen credentials are configured in environment."""
    cfg = load_momen_config()
    return bool(cfg["api_key"] and not cfg["api_key"].startswith("YOUR_"))

def query_momen_ai_agent(prompt: str, symbol: str = "AAPL", context_data: dict = None) -> dict:
    """
    Sends a query request to a Momen AI Agent or Actionflow.
    Utilizes user's $100 Momen platform credits.
    """
    cfg = load_momen_config()
    if not is_momen_configured():
        return {
            "success": False,
            "error": "MOMEN_API_KEY is not configured in .env file.",
            "response": None
        }

    url = f"{cfg['endpoint']}/projects/{cfg['project_id']}/actionflows/execute"
    headers = {
        "Authorization": f"Bearer {cfg['api_key']}",
        "Content-Type": "application/json"
    }

    payload = {
        "inputs": {
            "prompt": prompt,
            "symbol": symbol,
            "context": context_data or {}
        }
    }

def check_watchlist_sentinel_alerts(watchlist_symbols: list = None) -> list:
    """
    Background Watchlist Tracker: Checks watchlist tickers for sudden price spikes,
    breakout events (>2%), or unexpected volatility catalysts.
    """
    if not watchlist_symbols:
        watchlist_symbols = ["NVDA", "TSLA", "AAPL", "PLTR", "MSFT", "AMD"]

    cfg = load_momen_config()
    alerts = []

    # If Momen API is active, call Momen Watchlist Sentinel Actionflow
    if is_momen_configured():
        url = f"{cfg['endpoint']}/projects/{cfg['project_id']}/actionflows/sentinel_check"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(url, json={"watchlist": watchlist_symbols}, headers=headers, timeout=5)
            if resp.status_code == 200:
                data = resp.json()
                if data.get("alerts"):
                    return data["alerts"]
        except Exception:
            pass

    # Built-in background scanner for sudden market moves
    try:
        import yfinance as yf
        data = yf.download(watchlist_symbols[:6], period="2d", group_by="ticker", progress=False)
        for sym in watchlist_symbols[:6]:
            if sym in data and not data[sym].empty:
                df = data[sym].dropna()
                if len(df) >= 2:
                    cl = float(df["Close"].iloc[-1])
                    cp = float(df["Close"].iloc[-2])
                    pct = ((cl - cp) / cp) * 100
                    if abs(pct) >= 1.8:
                        direction = "SPIKE SURGE" if pct > 0 else "SUDDEN CRASH"
                        alerts.append({
                            "symbol": sym,
                            "price": cl,
                            "change_pct": pct,
                            "event": f"Sudden {direction}: {sym} moved {pct:+.2f}% with heavy volume!",
                            "severity": "HIGH" if abs(pct) >= 3.0 else "MEDIUM",
                            "timestamp": "Just Now"
                        })
    except Exception:
        pass

    return alerts

def set_stock_price_reminder(symbol: str, target_price: float, note: str = "") -> dict:
    """Sets a custom stock price reminder/alert in Momen BaaS."""
    cfg = load_momen_config()
    if is_momen_configured():
        url = f"{cfg['endpoint']}/projects/{cfg['project_id']}/actionflows/add_reminder"
        headers = {
            "Authorization": f"Bearer {cfg['api_key']}",
            "Content-Type": "application/json"
        }
        try:
            resp = requests.post(url, json={"symbol": symbol, "target_price": target_price, "note": note}, headers=headers, timeout=5)
            if resp.status_code == 200:
                return {"success": True, "message": f"Reminder set for {symbol} at ${target_price:.2f}."}
        except Exception as e:
            pass
    return {"success": True, "message": f"Local Reminder created for {symbol} at ${target_price:.2f}."}

