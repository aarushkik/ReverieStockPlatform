import os
import time
import requests
import pandas as pd
from datetime import datetime, timedelta
import yfinance as yf

def load_env_file():
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        try:
            with open(env_path, "r") as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        key, val = line.split("=", 1)
                        if key.strip() not in os.environ:
                            os.environ[key.strip()] = val.strip()
        except Exception:
            pass

load_env_file()

def fetch_yfinance_data(symbol: str) -> dict:
    """
    Fetches historical stock prices and recent news using yfinance.
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Fetch 1 year of historical daily data to support the web UI period filters
        history = ticker.history(period="1y")
        
        if history.empty:
            return {
                "symbol": symbol,
                "prices": pd.DataFrame(),
                "news": [],
                "success": False,
                "error_message": f"No data found for symbol '{symbol}'. It may be invalid or delisted."
            }
        
        # Extract news and normalize structure
        yf_news = ticker.news or []
        news_list = []
        for article in yf_news:
            if not article:
                continue
            # Check for new nested schema
            content = article.get("content") or {}
            if content:
                title = content.get("title") or content.get("headline") or ""
                provider_info = content.get("provider") or {}
                publisher = provider_info.get("displayName") or provider_info.get("sourceId") or "Unknown Source"
                
                click_info = content.get("clickThroughUrl") or {}
                canon_info = content.get("canonicalUrl") or {}
                link = click_info.get("url") or canon_info.get("url") or ""
                
                # Parse pubDate ISO string (e.g. '2026-07-09T21:31:36Z')
                pub_date_str = content.get("pubDate")
                if pub_date_str:
                    try:
                        if pub_date_str.endswith('Z'):
                            pub_date_str = pub_date_str[:-1]
                        dt = datetime.fromisoformat(pub_date_str)
                    except Exception:
                        dt = datetime.now()
                else:
                    dt = datetime.now()
            else:
                # Fall back to older flat schema
                title = article.get("title") or article.get("headline") or ""
                publisher = article.get("publisher") or article.get("source") or "Unknown Source"
                link = article.get("link") or article.get("url") or ""
                
                pub_time = article.get("providerPublishTime")
                if pub_time:
                    try:
                        dt = datetime.fromtimestamp(pub_time)
                    except Exception:
                        dt = datetime.now()
                else:
                    dt = datetime.now()
                
            news_list.append({
                "headline": title,
                "source": publisher,
                "url": link,
                "time": dt
            })
            
        return {
            "symbol": symbol,
            "prices": history,
            "news": news_list,
            "success": True,
            "error_message": None
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "prices": pd.DataFrame(),
            "news": [],
            "success": False,
            "error_message": str(e)
        }

def fetch_finnhub_data(symbol: str, api_key: str) -> dict:
    """
    Fetches historical stock prices (candles) and company news using Finnhub API.
    """
    symbol = symbol.upper()
    try:
        # Calculate time range: last 12 months (approx 365 days)
        end_time = int(time.time())
        start_time = int((datetime.now() - timedelta(days=365)).timestamp())
        
        # 1. Fetch Price Candles
        candle_url = "https://finnhub.io/api/v1/stock/candle"
        params = {
            "symbol": symbol,
            "resolution": "D",
            "from": start_time,
            "to": end_time,
            "token": api_key
        }
        
        response = requests.get(candle_url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if data.get("s") != "ok":
            return {
                "symbol": symbol,
                "prices": pd.DataFrame(),
                "news": [],
                "success": False,
                "error_message": f"Finnhub API returned status: {data.get('s', 'error')}. Verify if symbol is valid."
            }
        
        # Convert candle to pandas DataFrame
        # Finnhub candle fields: c = Close, h = High, l = Low, o = Open, v = Volume, t = Timestamp
        df = pd.DataFrame({
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"]
        }, index=pd.to_datetime(data["t"], unit="s"))
        
        # 2. Fetch Company News
        # Fetch news from last 30 days
        news_start = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
        news_end = datetime.now().strftime("%Y-%m-%d")
        
        news_url = "https://finnhub.io/api/v1/company-news"
        news_params = {
            "symbol": symbol,
            "from": news_start,
            "to": news_end,
            "token": api_key
        }
        
        news_response = requests.get(news_url, params=news_params, timeout=10)
        news_response.raise_for_status()
        news_data = news_response.json()
        
        news_list = []
        for article in news_data[:15]:  # limit to top 15 news items
            headline = article.get("headline") or article.get("summary") or ""
            source = article.get("source") or "Unknown"
            url = article.get("url") or ""
            pub_time = article.get("datetime")
            
            if pub_time:
                dt = datetime.fromtimestamp(pub_time)
            else:
                dt = datetime.now()
                
            news_list.append({
                "headline": headline,
                "source": source,
                "url": url,
                "time": dt
            })
            
        return {
            "symbol": symbol,
            "prices": df,
            "news": news_list,
            "success": True,
            "error_message": None
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "prices": pd.DataFrame(),
            "news": [],
            "success": False,
            "error_message": f"Finnhub API Error: {str(e)}"
        }

def get_stock_data(symbol: str) -> dict:
    """
    Orchestrator that fetches stock data using Finnhub if key is available,
    otherwise falls back to yfinance.
    """
    symbol = symbol.strip().upper()
    api_key = os.environ.get("FINNHUB_API_KEY")
    
    if api_key:
        # User specified Finnhub, attempt it
        res = fetch_finnhub_data(symbol, api_key)
        if res["success"]:
            return res
        else:
            # If Finnhub fails, try yfinance as a fallback
            fallback_res = fetch_yfinance_data(symbol)
            if fallback_res["success"]:
                fallback_res["error_message"] = f"Finnhub failed: {res['error_message']}. Fallback to yfinance succeeded."
                return fallback_res
            return res  # Return original Finnhub error if yfinance also fails
    else:
        # Standard yfinance
        return fetch_yfinance_data(symbol)
