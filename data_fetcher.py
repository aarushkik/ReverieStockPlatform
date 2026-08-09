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

# Fallback financial stock images for cards without an explicit thumbnail
FALLBACK_NEWS_IMAGES = [
    "https://images.unsplash.com/photo-1611974789855-9c2a0a7236a3?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1590283603385-17ffb3a7f29f?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1642543492481-44e81e3914a7?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1535320903710-d993d3d77d29?w=800&auto=format&fit=crop&q=80",
    "https://images.unsplash.com/photo-1507679799987-c73779587ccf?w=800&auto=format&fit=crop&q=80"
]

def fetch_firecrawl_news(symbol: str, api_key: str) -> list:
    """
    Uses Firecrawl API to search for fresh stock market news and scrape article content & lead images.
    """
    if not api_key:
        return []
    url = "https://api.firecrawl.dev/v1/search"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "query": f"{symbol} stock price forecast earnings news market update",
        "limit": 6,
        "scrapeOptions": {
            "formats": ["markdown"],
            "onlyMainContent": True
        }
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=12)
        if res.status_code == 200:
            data = res.json()
            results = data.get("data") or []
            news_items = []
            for idx, item in enumerate(results):
                title = item.get("title") or item.get("metadata", {}).get("title") or f"{symbol} Financial Update"
                desc = item.get("description") or item.get("metadata", {}).get("description") or item.get("markdown", "")[:250]
                link = item.get("url") or ""
                metadata = item.get("metadata") or {}
                og_img = metadata.get("ogImage") or metadata.get("image") or ""
                if not og_img:
                    og_img = FALLBACK_NEWS_IMAGES[idx % len(FALLBACK_NEWS_IMAGES)]
                source = metadata.get("sourceURL") or metadata.get("publisher") or "Firecrawl Market Scraper"
                news_items.append({
                    "headline": title,
                    "summary": desc.strip(),
                    "source": source,
                    "url": link,
                    "time": datetime.now(),
                    "image_url": og_img
                })
            return news_items
    except Exception:
        pass
    return []

def scrape_article_firecrawl(article_url: str, api_key: str) -> dict:
    """
    Scrapes a single news URL using Firecrawl API to extract markdown body & lead image.
    """
    if not api_key or not article_url:
        return {}
    url = "https://api.firecrawl.dev/v1/scrape"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "url": article_url,
        "formats": ["markdown"],
        "onlyMainContent": True
    }
    try:
        res = requests.post(url, headers=headers, json=payload, timeout=10)
        if res.status_code == 200:
            data = res.json().get("data") or {}
            metadata = data.get("metadata") or {}
            return {
                "title": metadata.get("title") or "",
                "description": metadata.get("description") or "",
                "markdown": data.get("markdown") or "",
                "image_url": metadata.get("ogImage") or metadata.get("image") or ""
            }
    except Exception:
        pass
    return {}

def fetch_yfinance_data(symbol: str) -> dict:
    """
    Fetches historical stock prices, key fundamentals (Yahoo Finance style), and news with image resolution.
    """
    try:
        ticker = yf.Ticker(symbol)
        
        # Fetch 2 years of historical daily data to support 5Y / Max and deep moving average calculations
        history = ticker.history(period="2y")
        
        if history.empty:
            return {
                "symbol": symbol,
                "prices": pd.DataFrame(),
                "news": [],
                "fundamentals": {},
                "success": False,
                "error_message": f"No price history found for symbol '{symbol}'."
            }
        
        # 1. Extract Fundamental Data (Yahoo Finance metrics)
        info = {}
        try:
            info = ticker.info or {}
        except Exception:
            info = {}
            
        fundamentals = {
            "market_cap": info.get("marketCap"),
            "enterprise_value": info.get("enterpriseValue"),
            "trailing_pe": info.get("trailingPE"),
            "forward_pe": info.get("forwardPE"),
            "peg_ratio": info.get("pegRatio"),
            "price_to_book": info.get("priceToBook"),
            "ev_to_ebitda": info.get("enterpriseToEbitda"),
            "profit_margin": info.get("profitMargins"),
            "operating_margin": info.get("operatingMargins"),
            "return_on_assets": info.get("returnOnAssets"),
            "return_on_equity": info.get("returnOnEquity"),
            "revenue_growth": info.get("revenueGrowth"),
            "target_mean_price": info.get("targetMeanPrice"),
            "target_high_price": info.get("targetHighPrice"),
            "target_low_price": info.get("targetLowPrice"),
            "recommendation_key": info.get("recommendationKey", "N/A"),
            "num_analysts": info.get("numberOfAnalystOpinions"),
            "fifty_two_week_high": info.get("fiftyTwoWeekHigh"),
            "fifty_two_week_low": info.get("fiftyTwoWeekLow"),
            "fifty_day_average": info.get("fiftyDayAverage"),
            "two_hundred_day_average": info.get("twoHundredDayAverage"),
            "beta": info.get("beta"),
            "short_ratio": info.get("shortRatio"),
            "float_shares": info.get("floatShares"),
            "average_volume": info.get("averageVolume"),
            "dividend_rate": info.get("dividendRate"),
            "dividend_yield": info.get("dividendYield"),
            "ex_dividend_date": info.get("exDividendDate"),
            "earnings_date": info.get("earningsDate"),
            "sector": info.get("sector", "N/A"),
            "industry": info.get("industry", "N/A"),
            "summary": info.get("longBusinessSummary", ""),
            "website": info.get("website", "")
        }
        
        # 2. Extract news and resolve thumbnail image URLs
        yf_news = ticker.news or []
        news_list = []
        for idx, article in enumerate(yf_news):
            if not article:
                continue
            
            content = article.get("content") or {}
            img_url = ""
            
            if content:
                title = content.get("title") or content.get("headline") or ""
                summary = content.get("summary") or content.get("description") or ""
                provider_info = content.get("provider") or {}
                publisher = provider_info.get("displayName") or provider_info.get("sourceId") or "Unknown Source"
                
                click_info = content.get("clickThroughUrl") or {}
                canon_info = content.get("canonicalUrl") or {}
                link = click_info.get("url") or canon_info.get("url") or ""
                
                # Image thumbnail resolution
                thumb = content.get("thumbnail") or {}
                resolutions = thumb.get("resolutions") or []
                if resolutions and isinstance(resolutions, list) and len(resolutions) > 0:
                    img_url = resolutions[0].get("url") or ""
                elif thumb.get("originalUrl"):
                    img_url = thumb.get("originalUrl")
                    
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
                title = article.get("title") or article.get("headline") or ""
                summary = article.get("summary") or ""
                publisher = article.get("publisher") or article.get("source") or "Unknown Source"
                link = article.get("link") or article.get("url") or ""
                
                thumb = article.get("thumbnail") or {}
                resolutions = thumb.get("resolutions") or []
                if resolutions and isinstance(resolutions, list) and len(resolutions) > 0:
                    img_url = resolutions[0].get("url") or ""
                elif thumb.get("originalUrl"):
                    img_url = thumb.get("originalUrl")
                    
                pub_time = article.get("providerPublishTime")
                if pub_time:
                    try:
                        dt = datetime.fromtimestamp(pub_time)
                    except Exception:
                        dt = datetime.now()
                else:
                    dt = datetime.now()
                    
            if not img_url:
                img_url = FALLBACK_NEWS_IMAGES[idx % len(FALLBACK_NEWS_IMAGES)]
                
            news_list.append({
                "headline": title,
                "summary": summary,
                "source": publisher,
                "url": link,
                "time": dt,
                "image_url": img_url
            })
            
        return {
            "symbol": symbol,
            "prices": history,
            "news": news_list,
            "fundamentals": fundamentals,
            "success": True,
            "error_message": None
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "prices": pd.DataFrame(),
            "news": [],
            "fundamentals": {},
            "success": False,
            "error_message": str(e)
        }

def fetch_finnhub_data(symbol: str, api_key: str) -> dict:
    """
    Fetches historical stock prices and news via Finnhub API.
    """
    symbol = symbol.upper()
    try:
        end_time = int(time.time())
        start_time = int((datetime.now() - timedelta(days=365)).timestamp())
        
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
                "fundamentals": {},
                "success": False,
                "error_message": f"Finnhub API status: {data.get('s', 'error')}"
            }
            
        df = pd.DataFrame({
            "Open": data["o"],
            "High": data["h"],
            "Low": data["l"],
            "Close": data["c"],
            "Volume": data["v"]
        }, index=pd.to_datetime(data["t"], unit="s"))
        
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
        for idx, article in enumerate(news_data[:15]):
            headline = article.get("headline") or ""
            summary = article.get("summary") or ""
            source = article.get("source") or "Finnhub Wires"
            url = article.get("url") or ""
            image_url = article.get("image") or FALLBACK_NEWS_IMAGES[idx % len(FALLBACK_NEWS_IMAGES)]
            pub_time = article.get("datetime")
            
            if pub_time:
                dt = datetime.fromtimestamp(pub_time)
            else:
                dt = datetime.now()
                
            news_list.append({
                "headline": headline,
                "summary": summary,
                "source": source,
                "url": url,
                "time": dt,
                "image_url": image_url
            })
            
        return {
            "symbol": symbol,
            "prices": df,
            "news": news_list,
            "fundamentals": {},
            "success": True,
            "error_message": None
        }
        
    except Exception as e:
        return {
            "symbol": symbol,
            "prices": pd.DataFrame(),
            "news": [],
            "fundamentals": {},
            "success": False,
            "error_message": f"Finnhub API Error: {str(e)}"
        }

def get_stock_data(symbol: str) -> dict:
    """
    Orchestrator that fetches data using Finnhub or yfinance, and enriches fundamentals.
    """
    symbol = symbol.strip().upper()
    finnhub_key = os.environ.get("FINNHUB_API_KEY")
    
    main_res = None
    if finnhub_key and not finnhub_key.startswith("YOUR_"):
        res = fetch_finnhub_data(symbol, finnhub_key)
        if res["success"]:
            main_res = res
            
    if not main_res:
        main_res = fetch_yfinance_data(symbol)
        
    # Ensure fundamentals are populated from yfinance if missing
    if main_res["success"] and not main_res.get("fundamentals"):
        yf_fallback = fetch_yfinance_data(symbol)
        if yf_fallback["success"]:
            main_res["fundamentals"] = yf_fallback.get("fundamentals", {})
            if not main_res["news"]:
                main_res["news"] = yf_fallback.get("news", [])

    return main_res

