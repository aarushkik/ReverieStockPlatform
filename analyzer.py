import pandas as pd
import numpy as np

def calculate_price_metrics(df: pd.DataFrame) -> dict:
    """
    Calculates technical indicators and historical performance changes.
    Expected columns: 'Close'
    """
    metrics = {}
    
    # Clean the index and ensure sorting by date asc
    df = df.sort_index()
    
    # 1. Prices
    close_prices = df['Close'].values
    if len(close_prices) == 0:
        return {}
        
    last_close = float(close_prices[-1])
    metrics['last_close'] = last_close
    
    # 2. Historical changes
    # Day Change (1-day change)
    if len(close_prices) > 1:
        prev_close = float(close_prices[-2])
        metrics['day_change_pct'] = ((last_close - prev_close) / prev_close) * 100
    else:
        metrics['day_change_pct'] = 0.0
        
    # 5-day change
    if len(close_prices) >= 6:
        close_5d_ago = float(close_prices[-6])
        metrics['change_5d_pct'] = ((last_close - close_5d_ago) / close_5d_ago) * 100
    else:
        metrics['change_5d_pct'] = None
        
    # 20-day change
    if len(close_prices) >= 21:
        close_20d_ago = float(close_prices[-21])
        metrics['change_20d_pct'] = ((last_close - close_20d_ago) / close_20d_ago) * 100
    else:
        metrics['change_20d_pct'] = None
        
    # 60-day change
    if len(close_prices) >= 61:
        close_60d_ago = float(close_prices[-61])
        metrics['change_60d_pct'] = ((last_close - close_60d_ago) / close_60d_ago) * 100
    else:
        metrics['change_60d_pct'] = None
        
    # 3. Simple Moving Averages
    # 5-day SMA
    metrics['sma_5'] = float(df['Close'].tail(5).mean()) if len(df) >= 5 else float(df['Close'].mean())
    
    # 20-day SMA
    metrics['sma_20'] = float(df['Close'].tail(20).mean()) if len(df) >= 20 else float(df['Close'].mean())
    
    # 60-day SMA
    metrics['sma_60'] = float(df['Close'].tail(60).mean()) if len(df) >= 60 else float(df['Close'].mean())
    
    return metrics

def calculate_volatility(df: pd.DataFrame) -> dict:
    """
    Calculates annualized volatility using daily returns over the last 20 trading days.
    """
    if len(df) < 2:
        return {"volatility_pct": 0.0, "level": "Low"}
        
    # Calculate daily returns
    daily_returns = df['Close'].pct_change().dropna()
    
    # Take the last 20 days (or all if fewer than 20)
    lookback_returns = daily_returns.tail(20)
    
    if len(lookback_returns) < 2:
        return {"volatility_pct": 0.0, "level": "Low"}
        
    # Standard deviation of daily returns
    daily_std = float(lookback_returns.std())
    
    # Annualize (assuming 252 trading days per year)
    annualized_vol = daily_std * np.sqrt(252) * 100
    
    # Volatility category threshold based on historical index/equity behaviors
    # Low: < 15%, Medium: 15% - 30%, High: > 30%
    if annualized_vol < 15:
        level = "Low"
    elif annualized_vol <= 30:
        level = "Moderate"
    else:
        level = "High"
        
    return {
        "volatility_pct": annualized_vol,
        "level": level
    }

def analyze_sentiment(news_articles: list) -> dict:
    """
    Performs a lexicon-based sentiment analysis on top news articles.
    Returns a score between -1.0 (strongly bearish) and +1.0 (strongly bullish),
    along with a label.
    """
    if not news_articles:
        return {
            "score": 0.0,
            "label": "Neutral (No News)",
            "description": "No recent headlines available to compute sentiment rating."
        }
        
    # Standard financial sentiment indicators
    positive_words = {
        'bullish', 'buy', 'growth', 'upgrade', 'beat', 'outperform', 'profit', 
        'gain', 'positive', 'surge', 'rise', 'soar', 'strong', 'record', 
        'dividend', 'optimistic', 'expansion', 'jump', 'rally', 'beat', 
        'ahead', 'succeed', 'demand', 'highest', 'climbs', 'recovery'
    }
    
    negative_words = {
        'bearish', 'sell', 'drop', 'downgrade', 'miss', 'underperform', 'loss', 
        'decline', 'negative', 'slump', 'fall', 'plunge', 'weak', 'deficit', 
        'pessimistic', 'shrink', 'risk', 'warning', 'concern', 'debt', 
        'slowdown', 'investigation', 'lawsuit', 'cut', 'slashes', 'worst'
    }
    
    total_articles = len(news_articles)
    article_scores = []
    
    for article in news_articles:
        headline = article.get("headline", "").lower()
        
        # Word tokenization & matching
        words = headline.replace("'", "").replace('"', '').replace(',', ' ').replace('.', ' ').split()
        
        pos_count = sum(1 for w in words if w in positive_words)
        neg_count = sum(1 for w in words if w in negative_words)
        
        # Compute individual article score
        if pos_count == 0 and neg_count == 0:
            score = 0.0
        else:
            score = (pos_count - neg_count) / (pos_count + neg_count)
            
        article_scores.append(score)
        
    # Average the scores
    avg_score = float(np.mean(article_scores)) if article_scores else 0.0
    
    # Categorize label
    if avg_score > 0.15:
        label = "Bullish"
    elif avg_score < -0.15:
        label = "Bearish"
    else:
        label = "Neutral"
        
    return {
        "score": avg_score,
        "label": label,
        "description": f"{label} sentiment calculated across {total_articles} recent articles (Score: {avg_score:.2f})."
    }

def run_analysis(symbol: str, data: dict) -> dict:
    """
    Main entry point for analytics. Combines prices, volatility, and sentiment.
    """
    if not data["success"]:
        return {
            "symbol": symbol,
            "success": False,
            "error_message": data["error_message"]
        }
        
    df = data["prices"]
    news = data["news"]
    
    price_metrics = calculate_price_metrics(df)
    vol_metrics = calculate_volatility(df)
    sent_metrics = analyze_sentiment(news)
    
    return {
        "symbol": symbol,
        "success": True,
        "last_close": price_metrics.get("last_close"),
        "day_change_pct": price_metrics.get("day_change_pct"),
        "change_5d_pct": price_metrics.get("change_5d_pct"),
        "change_20d_pct": price_metrics.get("change_20d_pct"),
        "change_60d_pct": price_metrics.get("change_60d_pct"),
        "sma_5": price_metrics.get("sma_5"),
        "sma_20": price_metrics.get("sma_20"),
        "sma_60": price_metrics.get("sma_60"),
        "volatility_pct": vol_metrics["volatility_pct"],
        "volatility_level": vol_metrics["level"],
        "sentiment_score": sent_metrics["score"],
        "sentiment_label": sent_metrics["label"],
        "sentiment_desc": sent_metrics["description"],
        "news": news
    }
