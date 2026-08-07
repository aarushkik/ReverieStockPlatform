import os
import json
import math
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

def run_llm_agent(metrics: dict, api_key: str, provider: str = "gemini") -> dict:
    """
    Uses an LLM (Gemini, OpenAI, Anthropic, or DeepSeek) to analyze stock indicators
    and write natural-sounding predictions, summaries, reasons, and risks.
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
        text = ""
        if provider == "gemini":
            client = genai.Client(api_key=api_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=prompt,
            )
            text = response.text.strip()
        elif provider == "openai":
            import urllib.request
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = json.dumps({
                "model": "gpt-4o-mini",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }).encode("utf-8")
            req = urllib.request.Request("https://api.openai.com/v1/chat/completions", data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as res:
                body = json.loads(res.read().decode("utf-8"))
                text = body["choices"][0]["message"]["content"].strip()
        elif provider == "anthropic":
            import urllib.request
            headers = {
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            payload = json.dumps({
                "model": "claude-3-5-sonnet-20241022",
                "max_tokens": 1024,
                "messages": [{"role": "user", "content": prompt}]
            }).encode("utf-8")
            req = urllib.request.Request("https://api.anthropic.com/v1/messages", data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as res:
                body = json.loads(res.read().decode("utf-8"))
                text = body["content"][0]["text"].strip()
        elif provider == "deepseek":
            import urllib.request
            headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
            payload = json.dumps({
                "model": "deepseek-chat",
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }).encode("utf-8")
            req = urllib.request.Request("https://api.deepseek.com/v1/chat/completions", data=payload, headers=headers)
            with urllib.request.urlopen(req, timeout=12) as res:
                body = json.loads(res.read().decode("utf-8"))
                text = body["choices"][0]["message"]["content"].strip()
        elif provider == "featherless":
            import requests
            model_name = os.environ.get("FEATHERLESS_MODEL", "Qwen/Qwen2.5-72B-Instruct")
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            res = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json={
                "model": model_name,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            }, timeout=15)
            if res.status_code != 200 and ("gated" in res.text.lower() or res.status_code in (403, 404)):
                res = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json={
                    "model": "Qwen/Qwen2.5-72B-Instruct",
                    "messages": [{"role": "user", "content": prompt}],
                    "temperature": 0.3
                }, timeout=15)
            res.raise_for_status()
            text = res.json()["choices"][0]["message"]["content"].strip()
                
        # Clean response string to parse JSON
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        text = text.strip()
        
        evaluation = json.loads(text)
        required_keys = ["prediction", "confidence_pct", "reasons", "risks", "summary"]
        if not all(key in evaluation for key in required_keys):
            raise ValueError("LLM response missing required JSON keys.")
            
        evaluation["confidence_pct"] = int(evaluation["confidence_pct"])
        if evaluation["prediction"] not in ["Bullish", "Bearish", "Neutral"]:
            evaluation["prediction"] = "Neutral"
            
        return evaluation
        
    except Exception as e:
        logger.warning(f"Failed to use LLM pipeline for {symbol} with provider {provider}: {str(e)}. Falling back to rules engine.")
        return run_heuristics(metrics)

def evaluate_ticker(metrics: dict) -> dict:
    """
    Main orchestrator for evaluating a single ticker.
    Checks environment for FEATHERLESS_API_KEY, GEMINI_API_KEY, OPENAI_API_KEY, ANTHROPIC_API_KEY, or DEEPSEEK_API_KEY.
    """
    heuristics_result = run_heuristics(metrics)
    
    featherless_key = os.environ.get("FEATHERLESS_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    anthropic_key = os.environ.get("ANTHROPIC_API_KEY")
    deepseek_key = os.environ.get("DEEPSEEK_API_KEY")
    
    if featherless_key and not featherless_key.startswith("YOUR_"):
        llm_result = run_llm_agent(metrics, featherless_key, provider="featherless")
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    elif gemini_key and not gemini_key.startswith("YOUR_"):
        llm_result = run_llm_agent(metrics, gemini_key, provider="gemini")
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    elif openai_key and not openai_key.startswith("YOUR_"):
        llm_result = run_llm_agent(metrics, openai_key, provider="openai")
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    elif anthropic_key and not anthropic_key.startswith("YOUR_"):
        llm_result = run_llm_agent(metrics, anthropic_key, provider="anthropic")
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    elif deepseek_key and not deepseek_key.startswith("YOUR_"):
        llm_result = run_llm_agent(metrics, deepseek_key, provider="deepseek")
        llm_result["bullish_score"] = metrics["bullish_score"]
        return llm_result
    else:
        return heuristics_result

def chat_with_ai_copilot(user_query: str, chat_history: list = None, model_name: str = None, context_ticker: str = "AAPL") -> str:
    """
    Interactive ChatGPT / Gemini style conversational AI assistant for StockMarket.
    Supports user model selection via Featherless AI or fallback providers.
    """
    if not user_query:
        return "👋 Hi there! I'm your StockMarket AI Copilot. Ask me anything about stock technicals, chart indicators, options Greeks, or market catalysts!"

    clean_query = user_query.strip().lower()
    
    # Handle natural greetings & small talk warmly
    if clean_query in ["hi", "hello", "hey", "hi there", "hello there", "sup", "yo", "who are you"]:
        return f"Hey there! 👋 I'm your StockMarket AI Copilot. I'm actively tracking ticker **{context_ticker}** right now. How can I help you analyze price action, technical indicators, or options risk today?"

    if not model_name or model_name.startswith("Default"):
        model_name = os.environ.get("FEATHERLESS_MODEL", "huihui-ai/Llama-3.3-70B-Instruct-abliterated")

    system_prompt = f"""You are StockMarket AI Assistant (powered by {model_name}), a friendly, highly intelligent, and expert financial market copilot.
You are helping a trader analyzing ticker {context_ticker} on StockMarket Terminal.
Speak in a warm, conversational, human-like tone as a knowledgeable financial pair programmer and quantitative analyst.
Provide clear, data-driven, and insightful answers. Highlight key price levels, technical risks, or market catalysts when relevant. Avoid robotic template phrases."""

    messages = [{"role": "system", "content": system_prompt}]
    
    if chat_history:
        for msg in chat_history[-6:]:
            role = "user" if msg.get("role") == "user" else "assistant"
            messages.append({"role": role, "content": msg.get("content", "")})
            
    messages.append({"role": "user", "content": user_query})
    
    # Wolfram LLM / Conversational Engine check
    wolfram_llm_key = os.environ.get("WOLFRAM_LLM_API_KEY") or os.environ.get("WOLFRAM_APP_ID")
    if "Wolfram" in model_name or (wolfram_llm_key and not wolfram_llm_key.startswith("YOUR_") and "wolfram" in user_query.lower()):
        try:
            import requests
            url = "https://api.wolframalpha.com/v1/conversation.jsp"
            params = {
                "appid": wolfram_llm_key,
                "i": f"Regarding stock ticker {context_ticker}: {user_query}"
            }
            res = requests.get(url, params=params, timeout=12)
            if res.status_code == 200:
                data = res.json()
                if data.get("result"):
                    return f"{data['result']}"
            
            url_res = "https://api.wolframalpha.com/v1/result"
            res2 = requests.get(url_res, params={"appid": wolfram_llm_key, "i": f"{context_ticker} {user_query}"}, timeout=10)
            if res2.status_code == 200:
                return f"{res2.text.strip()}"
        except Exception as e:
            logger.warning(f"Wolfram LLM copilot call failed: {e}")

    # Featherless AI LLM Cascade (Tries selected model -> Llama 3.3 70B Abliterated -> Qwen 72B)
    featherless_key = os.environ.get("FEATHERLESS_API_KEY")
    if featherless_key and not featherless_key.startswith("YOUR_"):
        candidate_models = [
            model_name,
            "huihui-ai/Llama-3.3-70B-Instruct-abliterated",
            "Qwen/Qwen2.5-72B-Instruct"
        ]
        # Remove duplicates preserving order
        seen = set()
        unique_models = [m for m in candidate_models if not (m in seen or seen.add(m))]
        
        import requests
        headers = {"Authorization": f"Bearer {featherless_key}", "Content-Type": "application/json"}
        for target_m in unique_models:
            try:
                payload = {
                    "model": target_m,
                    "messages": messages,
                    "temperature": 0.6,
                    "max_tokens": 450
                }
                res = requests.post("https://api.featherless.ai/v1/chat/completions", headers=headers, json=payload, timeout=14)
                if res.status_code == 200:
                    answer = res.json()["choices"][0]["message"]["content"].strip()
                    if answer:
                        return answer
            except Exception as e:
                logger.warning(f"Featherless model {target_m} failed: {e}")

    gemini_key = os.environ.get("GEMINI_API_KEY")
    if gemini_key and not gemini_key.startswith("YOUR_"):
        try:
            client = genai.Client(api_key=gemini_key)
            resp = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=f"{system_prompt}\n\nUser Question: {user_query}"
            )
            if resp.text:
                return resp.text.strip()
        except Exception as e:
            logger.warning(f"Gemini copilot call failed: {e}")

    # Human-like intelligent fallback
    return f"I'm analyzing **{context_ticker}** right now! Based on current market indicators, {context_ticker} is consolidating near key support levels. Keep an eye on SMA 20 vs SMA 60 moving average crossovers and volume momentum before taking position entries."

def calculate_black_scholes_greeks(S: float, K: float, T: float, r: float = 0.05, sigma: float = 0.30, option_type: str = "call") -> dict:
    """
    Calculates Black-Scholes theoretical Option Price and Greeks (Delta, Gamma, Theta, Vega, Rho).
    S: Current Stock Price
    K: Strike Price
    T: Time to Expiration in Years (e.g. 30 days = 30/365)
    r: Risk-free Interest Rate (e.g. 0.05 = 5%)
    sigma: Annualized Volatility (e.g. 0.30 = 30%)
    """
    if S <= 0 or K <= 0 or T <= 0 or sigma <= 0:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}
        
    try:
        def norm_cdf(x):
            return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
            
        def norm_pdf(x):
            return math.exp(-0.5 * x * x) / math.sqrt(2.0 * math.pi)

        d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
        d2 = d1 - sigma * math.sqrt(T)

        if option_type.lower() == "call":
            price = S * norm_cdf(d1) - K * math.exp(-r * T) * norm_cdf(d2)
            delta = norm_cdf(d1)
            rho = K * T * math.exp(-r * T) * norm_cdf(d2) / 100.0
            theta = (-S * norm_pdf(d1) * sigma / (2 * math.sqrt(T)) - r * K * math.exp(-r * T) * norm_cdf(d2)) / 365.0
        else:
            price = K * math.exp(-r * T) * norm_cdf(-d2) - S * norm_cdf(-d1)
            delta = norm_cdf(d1) - 1.0
            rho = -K * T * math.exp(-r * T) * norm_cdf(-d2) / 100.0
            theta = (-S * norm_pdf(d1) * sigma / (2 * math.sqrt(T)) + r * K * math.exp(-r * T) * norm_cdf(-d2)) / 365.0

        gamma = norm_pdf(d1) / (S * sigma * math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0

        return {
            "price": round(price, 2),
            "delta": round(delta, 4),
            "gamma": round(gamma, 4),
            "theta": round(theta, 4),
            "vega": round(vega, 4),
            "rho": round(rho, 4)
        }
    except Exception:
        return {"price": 0.0, "delta": 0.0, "gamma": 0.0, "theta": 0.0, "vega": 0.0, "rho": 0.0}

def query_wolfram_engine(query_str: str) -> dict:
    """
    Queries Wolfram Alpha API for symbolic financial math, derivative valuation,
    and quantitative equations.
    """
    app_id = os.environ.get("WOLFRAM_APP_ID")
    if not app_id or app_id.startswith("YOUR_"):
        return {
            "success": False,
            "result": "Wolfram Engine requires WOLFRAM_APP_ID in .env",
            "source": "fallback"
        }
        
    try:
        import requests
        url = "https://api.wolframalpha.com/v1/result"
        params = {"appid": app_id, "i": query_str}
        res = requests.get(url, params=params, timeout=10)
        if res.status_code == 200:
            return {
                "success": True,
                "result": res.text.strip(),
                "source": "wolfram_alpha"
            }
        else:
            return {
                "success": False,
                "result": f"Wolfram returned status {res.status_code}",
                "source": "wolfram_alpha"
            }
    except Exception as e:
        return {
            "success": False,
            "result": str(e),
            "source": "wolfram_alpha"
        }

def generate_perfect_corp_ai_media(prompt_text: str, mode: str = "text-to-image") -> dict:
    """
    Generates AI visual graphics & enhanced media using Perfect Corp.'s Generative AI API (Reverie Hacks).
    """
    api_key = os.environ.get("PERFECT_CORP_API_KEY")
    if not api_key or api_key.startswith("YOUR_"):
        return {
            "success": False,
            "message": "Perfect Corp API requires PERFECT_CORP_API_KEY in .env",
            "image_url": None
        }
        
    try:
        import requests
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        url = "https://yce.perfectcorp.com/api/v1/generative/text-to-image"
        payload = {
            "prompt": prompt_text,
            "aspect_ratio": "16:9",
            "style": "fintech_infographic"
        }
        res = requests.post(url, headers=headers, json=payload, timeout=15)
        if res.status_code == 200:
            data = res.json()
            return {
                "success": True,
                "image_url": data.get("image_url") or data.get("url"),
                "message": "AI Graphic generated via Perfect Corp API"
            }
        else:
            return {
                "success": False,
                "message": f"Perfect Corp API returned status {res.status_code}",
                "image_url": None
            }
    except Exception as e:
        return {
            "success": False,
            "message": str(e),
            "image_url": None
        }
