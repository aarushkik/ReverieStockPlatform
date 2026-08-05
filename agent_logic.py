import os
import json
import logging
from google import genai

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("stock_agent.agent_logic")

def run_heuristics(metrics: dict) -> dict:
    """
    Fallback deterministic heuristic reasoning engine based on technical indicators
    and news sentiment score.
    """
    symbol = metrics["symbol"]
    close = metrics.get("last_close", 0.0)
    sma5 = metrics.get("sma_5", 0.0)
    sma20 = metrics.get("sma_20", 0.0)
    sma60 = metrics.get("sma_60", 0.0)
    change_5d = metrics.get("change_5d_pct")
    change_20d = metrics.get("change_20d_pct")
    change_60d = metrics.get("change_60d_pct")
    volatility = metrics.get("volatility_pct", 0.0)
    vol_level = metrics.get("volatility_level", "Low")
    sentiment_score = metrics.get("sentiment_score", 0.0)
    
    # 1. Compute a technical and momentum rating score (0 - 100)
    # Neutral starting point
    score = 50
    
    # Trend alignment (Max +20 / -20)
    if close > 0:
        if close > sma5: score += 5
        else: score -= 5
        if close > sma20: score += 7
        else: score -= 7
        if close > sma60: score += 8
        else: score -= 8
        
    # Moving Average crossovers (Max +10 / -10)
    if sma5 > sma20: score += 5
    else: score -= 5
    if sma20 > sma60: score += 5
    else: score -= 5
    
    # Historical changes/Momentum (Max +15 / -15)
    if change_5d is not None:
        score += 5 if change_5d > 0 else -5
    if change_20d is not None:
        score += 5 if change_20d > 0 else -5
    if change_60d is not None:
        score += 5 if change_60d > 0 else -5
        
    # News Sentiment impact (Max +20 / -20)
    score += int(sentiment_score * 20)
    
    # Clip score between 0 and 100
    score = max(0, min(100, score))
    metrics["bullish_score"] = score
    
    # 2. Determine Directional Prediction and Confidence
    if score >= 60:
        prediction = "Bullish"
        confidence = score
    elif score <= 40:
        prediction = "Bearish"
        confidence = 100 - score
    else:
        prediction = "Neutral"
        confidence = int(100 - abs(score - 50) * 4)  # 60% to 100% confidence in neutral trend
        
    # 3. Heuristic Reasoning generation
    reasons = []
    risks = []
    
    # Generating Reasons
    if close > sma20 and close > sma60:
        reasons.append(f"Price is trading above key support levels (20-day SMA of ${sma20:.2f} and 60-day SMA of ${sma60:.2f}), signaling a strong medium-to-long term technical uptrend.")
    if sma5 > sma20:
        reasons.append("Short-term moving average (5-day) is above the 20-day SMA, indicating upward crossover momentum.")
    if change_5d and change_5d > 2.0:
        reasons.append(f"Strong short-term buyer momentum with a +{change_5d:.2f}% gain over the last 5 trading days.")
    if sentiment_score > 0.15:
        reasons.append(f"Favorable news coverage with positive news sentiment of {sentiment_score:.2f} across recent headlines.")
    
    # Ensure we have at least 2 reasons
    if len(reasons) < 2:
        if close > sma5:
            reasons.append(f"Price sits above its 5-day SMA of ${sma5:.2f}, indicating positive short-term trading pressure.")
        else:
            reasons.append("Stock exhibits price stabilization near recent support zones.")
    if len(reasons) < 2:
        reasons.append("Price action is trading inside historical ranges, indicating market consolidation.")
        
    # Limit reasons to top 3
    reasons = reasons[:3]
    
    # Generating Risks
    if vol_level == "High":
        risks.append(f"Elevated price volatility (annualized at {volatility:.1f}%) signals high potential for sudden, unpredictable price swings.")
    if sentiment_score < -0.15:
        risks.append(f"Recent headlines show negative market sentiment ({sentiment_score:.2f}), pointing to adverse news cycle risks.")
    if close < sma20 and close < sma60:
        risks.append(f"Price is trading below major moving averages (20-day SMA of ${sma20:.2f} and 60-day SMA of ${sma60:.2f}), confirming technical downward pressure.")
    if change_5d and change_5d < -2.0:
        risks.append(f"Recent short-term selling pressure is high with a decline of {change_5d:.2f}% over the last 5 trading days.")
    if change_5d and change_5d > 12.0:
        risks.append(f"Stock is heavily overextended in the short term (+{change_5d:.2f}% in 5 days), presenting increased consolidation or pullback risk.")
        
    # Ensure we have at least 1 risk
    if not risks:
        risks.append("Subject to standard equity market headwinds, sector competition, and macroeconomic cycles.")
    if len(risks) < 2 and vol_level == "Moderate":
        risks.append(f"Moderate volatility profile ({volatility:.1f}%) suggests typical stock fluctuations should be expected.")
        
    risks = risks[:2]
    
    # Simple plain text summary
    summary = f"{symbol} exhibits a {prediction.lower()} technical structure. "
    if prediction == "Bullish":
        summary += "Key technical indicators are aligned to the upside with favorable short-to-medium term moving averages."
    elif prediction == "Bearish":
        summary += "Prices are exhibiting a breakdown below key support levels with persistent downward momentum."
    else:
        summary += "The stock is consolidating without a strong directional catalyst in either technical indicators or recent news."
        
    return {
        "prediction": prediction,
        "confidence_pct": confidence,
        "reasons": reasons,
        "risks": risks,
        "summary": summary
    }

def run_llm_agent(metrics: dict, api_key: str) -> dict:
    """
    Uses Gemini LLM to analyze stock indicators and news to write natural-sounding
    predictions, summaries, reasons, and risks.
    """
    symbol = metrics["symbol"]
    headlines = [n["headline"] for n in metrics.get("news", [])[:10]]
    headlines_str = "\n".join([f"- {h}" for h in headlines]) if headlines else "No recent headlines."
    
    prompt = f"""
You are a professional Stock Market Research and Prediction Agent.
Analyze the following stock market data for ticker: {symbol}

### TECHNICAL AND FINANCIAL DATA:
- Last Close Price: ${metrics.get('last_close', 'N/A')}
- 1-Day Price Change: {metrics.get('day_change_pct', 0.0):.2f}%
- 5-Day Price Change: {metrics.get('change_5d_pct', 0.0):.2f}% if available
- 20-Day Price Change: {metrics.get('change_20d_pct', 0.0):.2f}% if available
- 60-Day Price Change: {metrics.get('change_60d_pct', 0.0):.2f}% if available
- 5-Day SMA: ${metrics.get('sma_5', 'N/A')}
- 20-Day SMA: ${metrics.get('sma_20', 'N/A')}
- 60-Day SMA: ${metrics.get('sma_60', 'N/A')}
- Annualized Volatility: {metrics.get('volatility_pct', 0.0):.1f}% (Level: {metrics.get('volatility_level', 'Unknown')})
- Sentiment Rating: {metrics.get('sentiment_label', 'Neutral')} (Score: {metrics.get('sentiment_score', 0.0):.2f})

### RECENT NEWS HEADLINES:
{headlines_str}

### INSTRUCTIONS:
Evaluate this stock and provide your output in valid JSON format.
Your output must contain exactly these keys:
1. "prediction": Must be exactly one of "Bullish", "Bearish", or "Neutral".
2. "confidence_pct": An integer between 0 and 100 representing your prediction confidence.
3. "reasons": An array of 2 to 3 sentences explaining the primary reasons behind your prediction. Focus heavily on price action, moving averages, and news sentiment.
4. "risks": An array of 1 to 2 sentences explaining key potential risks or warning signs for the stock (such as high volatility, trend breaks, or negative headline issues).
5. "summary": A 2-3 sentence beginner-friendly overview summarizing the current status and near-term outlook for this stock.

Respond with raw JSON only. Do not wrap in markdown blocks or write anything else.
"""
    try:
        # Initialize Google GenAI client
        client = genai.Client(api_key=api_key)
        
        # Call Gemini model
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        
        # Clean response string to parse JSON
        text = response.text.strip()
        if text.startswith("```json"):
            text = text[7:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        evaluation = json.loads(text)
        
        # Verify required keys
        required_keys = ["prediction", "confidence_pct", "reasons", "risks", "summary"]
        if not all(key in evaluation for key in required_keys):
            raise ValueError("LLM response missing required JSON keys.")
            
        # Ensure correct formatting
        evaluation["confidence_pct"] = int(evaluation["confidence_pct"])
        if evaluation["prediction"] not in ["Bullish", "Bearish", "Neutral"]:
            evaluation["prediction"] = "Neutral"
            
        return evaluation
        
    except Exception as e:
        logger.warning(f"Failed to use LLM pipeline for {symbol}: {str(e)}. Falling back to rules engine.")
        # Fall back to deterministic rules
        return run_heuristics(metrics)

def evaluate_ticker(metrics: dict) -> dict:
    """
    Main orchestrator for evaluating a single ticker.
    Checks environment for GEMINI_API_KEY (or allows passing it in),
    and calls run_llm_agent or run_heuristics.
    Also ensures the deterministic 'bullish_score' is generated for watchlist ranking.
    """
    # 1. Run heuristics to guarantee the deterministic 'bullish_score' is set on metrics
    heuristics_result = run_heuristics(metrics)
    
    # 2. Check for Gemini Key
    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key:
        # User has Gemini API setup, run LLM reasoning
        llm_result = run_llm_agent(metrics, gemini_key)
        # Retain the deterministic bullish_score from heuristics for ranking
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    else:
        # Rule-based heuristics only
        return heuristics_result
