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

    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=12)
        if resp.status_code == 200:
            data = resp.json()
            return {
                "success": True,
                "response": data.get("result") or data.get("output") or data.get("data"),
                "raw": data
            }
        else:
            return {
                "success": False,
                "error": f"Momen API HTTP {resp.status_code}: {resp.text}",
                "response": None
            }
    except Exception as e:
        return {
            "success": False,
            "error": f"Momen request failed: {str(e)}",
            "response": None
        }
