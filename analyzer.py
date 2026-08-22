import pandas as pd
import numpy as np
from predictive_model import train_predictive_model


def calculate_price_metrics(df: pd.DataFrame) -> dict:
    """
    Calculates technical indicators, moving averages, Bollinger Bands, and historical performance changes.
    Expected columns: 'Close'
    """
    metrics = {}
    
    if df.empty or 'Close' not in df.columns:
        return metrics
        
    df = df.sort_index()
    clean_series = df['Close'].dropna()
    close_prices = clean_series.values
    if len(close_prices) == 0:
        return metrics
        
    last_close = float(close_prices[-1])
    metrics['last_close'] = last_close
    
    # Historical percentage changes
    if len(close_prices) > 1:
        prev_close = float(close_prices[-2])
        metrics['day_change_pct'] = ((last_close - prev_close) / prev_close) * 100 if prev_close > 0 else 0.0
    else:
        metrics['day_change_pct'] = 0.0
        
    if len(close_prices) >= 6:
        close_5d = float(close_prices[-6])
        metrics['change_5d_pct'] = ((last_close - close_5d) / close_5d) * 100 if close_5d > 0 else 0.0
    else:
        metrics['change_5d_pct'] = 0.0
        
    if len(close_prices) >= 21:
        close_20d = float(close_prices[-21])
        metrics['change_20d_pct'] = ((last_close - close_20d) / close_20d) * 100 if close_20d > 0 else 0.0
    else:
        metrics['change_20d_pct'] = 0.0
        
    if len(close_prices) >= 61:
        close_60d = float(close_prices[-61])
        metrics['change_60d_pct'] = ((last_close - close_60d) / close_60d) * 100 if close_60d > 0 else 0.0
    else:
        metrics['change_60d_pct'] = 0.0
        
    # Moving Averages (SMAs & EMAs)
    def _safe_mean(ser):
        val = float(ser.mean())
        return val if not np.isnan(val) else last_close

    metrics['sma_5'] = _safe_mean(clean_series.tail(5)) if len(clean_series) >= 5 else last_close
    metrics['sma_20'] = _safe_mean(clean_series.tail(20)) if len(clean_series) >= 20 else last_close
    metrics['sma_50'] = _safe_mean(clean_series.tail(50)) if len(clean_series) >= 50 else last_close
    metrics['sma_60'] = _safe_mean(clean_series.tail(60)) if len(clean_series) >= 60 else last_close
    metrics['sma_200'] = _safe_mean(clean_series.tail(200)) if len(clean_series) >= 200 else last_close

    # Exponential Moving Averages (EMA 9 & EMA 21)
    if len(clean_series) >= 9:
        ema_9_val = float(clean_series.ewm(span=9, adjust=False).mean().iloc[-1])
        metrics['ema_9'] = ema_9_val if not np.isnan(ema_9_val) else last_close
    else:
        metrics['ema_9'] = last_close
        
    if len(clean_series) >= 21:
        ema_21_val = float(clean_series.ewm(span=21, adjust=False).mean().iloc[-1])
        metrics['ema_21'] = ema_21_val if not np.isnan(ema_21_val) else last_close
    else:
        metrics['ema_21'] = last_close

    # Bollinger Bands (20-day, 2 std dev)
    if len(clean_series) >= 20:
        roll20 = clean_series.tail(20)
        m20 = float(roll20.mean())
        std20 = float(roll20.std())
        metrics['bb_middle'] = m20
        metrics['bb_upper'] = m20 + (2.0 * std20)
        metrics['bb_lower'] = m20 - (2.0 * std20)
    else:
        metrics['bb_middle'] = last_close
        metrics['bb_upper'] = last_close * 1.05
        metrics['bb_lower'] = last_close * 0.95

    return metrics

def calculate_volatility(df: pd.DataFrame) -> dict:
    """
    Calculates annualized volatility using daily returns over the last 20 trading days.
    """
    if df.empty or 'Close' not in df.columns or len(df) < 2:
        return {"volatility_pct": 0.0, "level": "Low"}
        
    daily_returns = df['Close'].dropna().pct_change().dropna()
    lookback_returns = daily_returns.tail(20)
    
    if len(lookback_returns) < 2:
        return {"volatility_pct": 0.0, "level": "Low"}
        
    daily_std = float(lookback_returns.std())
    if np.isnan(daily_std):
        return {"volatility_pct": 0.0, "level": "Low"}
        
    annualized_vol = daily_std * np.sqrt(252) * 100
    if np.isnan(annualized_vol):
        annualized_vol = 0.0
        
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
    """
    if not news_articles:
        return {
            "score": 0.0,
            "label": "Neutral (No News)",
            "description": "No recent headlines available to compute sentiment rating."
        }
        
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
        headline = (article.get("headline", "") + " " + article.get("summary", "")).lower()
        words = headline.replace("'", "").replace('"', '').replace(',', ' ').replace('.', ' ').split()
        
        pos_count = sum(1 for w in words if w in positive_words)
        neg_count = sum(1 for w in words if w in negative_words)
        
        if pos_count == 0 and neg_count == 0:
            score = 0.0
        else:
            score = (pos_count - neg_count) / (pos_count + neg_count)
            
        article_scores.append(score)
        
    avg_score = float(np.mean(article_scores)) if article_scores else 0.0
    
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

def run_analysis(symbol_or_data, data: dict = None) -> dict:
    """
    Main entry point for analytics. Combines price metrics, indicators, volatility, sentiment, and fundamentals.
    Supports both run_analysis(symbol, data) and run_analysis(data).
    """
    if isinstance(symbol_or_data, dict) and data is None:
        data = symbol_or_data
        symbol = data.get("symbol", "UNKNOWN")
    else:
        symbol = symbol_or_data
        if data is None:
            data = {"success": False, "error_message": "No market data provided."}

    if not data.get("success", False):
        return {
            "symbol": symbol,
            "success": False,
            "error_message": data.get("error_message", "Failed to retrieve stock data.")
        }

        
    df = data["prices"]
    news = data["news"]
    fundamentals = data.get("fundamentals", {})

    price_metrics = calculate_price_metrics(df)
    vol_metrics = calculate_volatility(df)
    sent_metrics = analyze_sentiment(news)
    ml_res = train_predictive_model(symbol, df)

    
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
        "sma_50": price_metrics.get("sma_50"),
        "sma_60": price_metrics.get("sma_60"),
        "sma_200": price_metrics.get("sma_200"),
        "ema_9": price_metrics.get("ema_9"),
        "ema_21": price_metrics.get("ema_21"),
        "bb_middle": price_metrics.get("bb_middle"),
        "bb_upper": price_metrics.get("bb_upper"),
        "bb_lower": price_metrics.get("bb_lower"),
        "volatility_pct": vol_metrics["volatility_pct"],
        "volatility_level": vol_metrics["level"],
        "sentiment_score": sent_metrics["score"],
        "sentiment_label": sent_metrics["label"],
        "sentiment_desc": sent_metrics["description"],
        "news": news,
        "fundamentals": fundamentals,
        "ml_model_result": ml_res,
        "ml_prediction": ml_res.get("prediction", "Neutral"),
        "ml_bullish_prob": ml_res.get("bullish_probability", 50.0),
        "ml_confidence_pct": ml_res.get("confidence_pct", 60),
        "ml_accuracy_pct": ml_res.get("backtest_accuracy_pct", 60.0),
        "ml_feature_importances": ml_res.get("feature_importances", []),
        "ml_forecast": ml_res.get("forecast", [])
    }

