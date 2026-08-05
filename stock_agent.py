#!/usr/bin/env python3
"""
Stock Market Research and Prediction Agent
Main orchestrator script.
"""

import os
import sys
import argparse
from rich.console import Console
from rich.prompt import Prompt, Confirm

# ==============================================================================
# OPTIONAL API CREDENTIAL CONFIGURATION
# If you prefer not to use environment variables, you can paste your keys here.
# Note: If these variables are set, they will override environment variables.
# ==============================================================================
USER_FINNHUB_API_KEY = ""  # Paste Finnhub API Key here if desired
USER_GEMINI_API_KEY = ""   # Paste Gemini API Key here if desired
# ==============================================================================

# Inject custom keys into environment if provided
if USER_FINNHUB_API_KEY.strip():
    os.environ["FINNHUB_API_KEY"] = USER_FINNHUB_API_KEY.strip()
if USER_GEMINI_API_KEY.strip():
    os.environ["GEMINI_API_KEY"] = USER_GEMINI_API_KEY.strip()

# Import project modules
from data_fetcher import get_stock_data
from analyzer import run_analysis
from agent_logic import evaluate_ticker
from dashboard import render_terminal_dashboard, generate_markdown_report

console = Console()

def parse_args():
    parser = argparse.ArgumentParser(
        description="Stock Market Research & Prediction Agent - Beginner-friendly dashboard & analytics."
    )
    parser.add_argument(
        "-t", "--tickers", 
        type=str, 
        help="Single ticker symbol or comma-separated list of symbols (e.g. AAPL,NVDA,TSLA)."
    )
    parser.add_argument(
        "-o", "--output", 
        type=str, 
        default="stock_research_report.md", 
        help="Path where the Markdown report will be saved."
    )
    return parser.parse_args()

def interactive_menu() -> str:
    """
    Guides the beginner user to choose between single ticker or watchlist research.
    """
    console.print("\n[bold cyan]Welcome to the Stock Market Research & Prediction Agent![/bold cyan]")
    console.print("[dim]This tool fetches real-time market data, news, evaluates sentiment, and runs predictive analysis.[/dim]\n")
    
    choice = Prompt.ask(
        "Choose research mode [1: Single Ticker, 2: Watch List Mode]",
        choices=["1", "2"],
        default="1"
    )
    
    if choice == "1":
        ticker = Prompt.ask("Enter a single stock symbol (e.g. AAPL, NVDA, SPY)")
        return ticker
    else:
        tickers = Prompt.ask("Enter stock symbols separated by commas (e.g. AAPL, NVDA, TSLA, MSFT, SPY)")
        return tickers

def process_tickers(tickers_str: str) -> list:
    """
    Parses tickers list, fetches data, analyzes indicators, predicts outcome and compiles results.
    """
    # Parse and sanitize symbols
    raw_symbols = tickers_str.split(",")
    symbols = [sym.strip().upper() for sym in raw_symbols if sym.strip()]
    
    if not symbols:
        console.print("[bold red]Error: No valid ticker symbols entered.[/bold red]")
        return []
        
    results = []
    
    console.print(f"\n[cyan]Starting analysis on {len(symbols)} ticker(s)...[/cyan]")
    
    for symbol in symbols:
        with console.status(f"[bold green]Analyzing {symbol}...[/bold green]") as status:
            try:
                # 1. Fetch
                data = get_stock_data(symbol)
                
                if not data["success"]:
                    console.print(f"[bold red]✗ Failed {symbol}:[/bold red] {data['error_message']}")
                    results.append({
                        "symbol": symbol,
                        "success": False,
                        "error_message": data["error_message"]
                    })
                    continue
                
                # 2. Analyze
                analysis_results = run_analysis(symbol, data)
                
                if not analysis_results["success"]:
                    console.print(f"[bold red]✗ Failed to analyze {symbol}:[/bold red] {analysis_results['error_message']}")
                    results.append({
                        "symbol": symbol,
                        "success": False,
                        "error_message": analysis_results["error_message"]
                    })
                    continue
                
                # 3. Prediction & Agent Logic
                eval_result = evaluate_ticker(analysis_results)
                
                # Merge evaluation back into analysis metrics
                analysis_results.update(eval_result)
                results.append(analysis_results)
                
                console.print(f"[bold green]✓ Completed {symbol}[/bold green]")
                
            except Exception as e:
                console.print(f"[bold red]✗ System crash on ticker {symbol}:[/bold red] {str(e)}")
                results.append({
                    "symbol": symbol,
                    "success": False,
                    "error_message": f"Unexpected pipeline failure: {str(e)}"
                })
                
    return results

def main():
    args = parse_args()
    
    # 1. Determine tickers to evaluate
    if args.tickers:
        tickers_str = args.tickers
    else:
        tickers_str = interactive_menu()
        
    # Check if user entered anything
    if not tickers_str.strip():
        console.print("[bold red]No tickers input. Exiting.[/bold red]")
        sys.exit(1)
        
    # 2. Process tickers
    results = process_tickers(tickers_str)
    
    # Filter for successful results to perform ranking and reports
    success_results = [r for r in results if r.get("success", False)]
    failed_results = [r for r in results if not r.get("success", False)]
    
    # If there are successful ones, sort them from highest bullish setup score to lowest (Ranking Algorithm)
    # The setup score ('bullish_score') ranges from 0 (very bearish) to 100 (very bullish)
    if success_results:
        success_results.sort(key=lambda x: x.get("bullish_score", 50), reverse=True)
        
    # Re-assemble sorted list with failures at the bottom
    final_results = success_results + failed_results
    
    if not final_results:
        console.print("[bold red]All tickers failed to process. Check internet connection or symbol spelling.[/bold red]")
        sys.exit(1)
        
    # 3. Render Terminal Dashboard
    render_terminal_dashboard(final_results)
    
    # 4. Save Markdown Report
    report_path = args.output
    generate_markdown_report(final_results, report_path)

if __name__ == "__main__":
    main()
