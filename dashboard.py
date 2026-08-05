import os
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from rich.style import Style
from rich.box import ROUNDED
from rich.columns import Columns

console = Console()

def render_terminal_dashboard(results: list):
    """
    Renders a stunning terminal-based report dashboard using 'rich'.
    """
    if not results:
        console.print("[bold red]No stock research data available to display.[/bold red]")
        return

    # Check if we are running in Single Ticker or Watch List mode
    is_watchlist = len(results) > 1

    # Header Panel
    title = Text("\n📈 Stock Market Research & Prediction Agent", style="bold cyan")
    subtitle = Text(f"Generated at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')} | Heuristic + AI Analytics", style="italic white")
    
    header_content = Text.assemble(title, "\n", subtitle)
    console.print(Panel(header_content, border_style="cyan", box=ROUNDED, expand=False))

    # Disclaimer Warning
    disclaimer_text = Text(
        "⚠️  EDUCATIONAL USE ONLY. This tool provides research notes and is NOT financial advice.", 
        style="bold black on yellow"
    )
    console.print(Panel(disclaimer_text, border_style="yellow", box=ROUNDED, expand=False))
    console.print("")

    if is_watchlist:
        # RENDER WATCH LIST RANKING TABLE
        console.print("[bold underline cyan]Watch List Rankings (Sorted by Bullish Setup Strength):[/bold underline cyan]\n")
        
        table = Table(box=ROUNDED, border_style="dim white")
        table.add_column("Rank", justify="center", style="bold")
        table.add_column("Symbol", justify="left", style="bold cyan")
        table.add_column("Close", justify="right")
        table.add_column("Day Change", justify="right")
        table.add_column("Prediction", justify="center")
        table.add_column("Confidence", justify="right")
        table.add_column("Sentiment", justify="center")
        table.add_column("Setup Score", justify="right")
        
        for rank, res in enumerate(results, start=1):
            if not res.get("success", False):
                table.add_row(
                    str(rank), 
                    res["symbol"], 
                    "N/A", 
                    "N/A", 
                    "[bold red]FAIL[/bold red]", 
                    "N/A", 
                    "N/A", 
                    "0",
                    style="dim red"
                )
                continue
                
            pred = res.get("prediction", "Neutral")
            score = res.get("bullish_score", 50)
            conf = f"{res.get('confidence_pct', 50)}%"
            change_val = res.get("day_change_pct", 0.0)
            
            # Formatting values
            change_color = "green" if change_val > 0 else ("red" if change_val < 0 else "white")
            change_str = f"[{change_color}]+{change_val:.2f}%[/{change_color}]" if change_val > 0 else f"[{change_color}]{change_val:.2f}%[/{change_color}]"
            
            close_str = f"${res.get('last_close', 0.0):.2f}"
            
            # Predict labels
            if pred == "Bullish":
                pred_str = "[bold green]Bullish ↗[/bold green]"
                row_style = Style(bgcolor="green", dim=True) # subtle background highlight
            elif pred == "Bearish":
                pred_str = "[bold red]Bearish ↘[/bold red]"
            else:
                pred_str = "[bold yellow]Neutral ➔[/bold yellow]"
                
            sent_lbl = res.get("sentiment_label", "Neutral")
            sent_score = res.get("sentiment_score", 0.0)
            sent_color = "green" if sent_score > 0.15 else ("red" if sent_score < -0.15 else "yellow")
            sent_str = f"[{sent_color}]{sent_lbl} ({sent_score:.2f})[/{sent_color}]"
            
            table.add_row(
                str(rank),
                res["symbol"],
                close_str,
                change_str,
                pred_str,
                conf,
                sent_str,
                f"{score}/100"
            )
            
        console.print(table)
        console.print("")

    # RENDER DETAILED SECTION FOR EACH TICKER
    console.print("[bold underline cyan]Detailed Stock Breakdowns:[/bold underline cyan]\n")
    
    for res in results:
        symbol = res["symbol"]
        if not res.get("success", False):
            console.print(Panel(
                f"[bold red]Error loading data for {symbol}:[/bold red]\n{res.get('error_message', 'Unknown Error')}",
                title=f"Ticker: {symbol}",
                border_style="red"
            ))
            continue
            
        pred = res.get("prediction", "Neutral")
        conf = res.get("confidence_pct", 50)
        close = res.get("last_close", 0.0)
        change = res.get("day_change_pct", 0.0)
        
        # Color schemes based on predictions
        if pred == "Bullish":
            border_color = "green"
            pred_text = f"[bold green]BULLISH ({conf}% Confidence)[/bold green]"
        elif pred == "Bearish":
            border_color = "red"
            pred_text = f"[bold red]BEARISH ({conf}% Confidence)[/bold red]"
        else:
            border_color = "yellow"
            pred_text = f"[bold yellow]NEUTRAL ({conf}% Confidence)[/bold yellow]"
            
        change_text = f"[green]+{change:.2f}%[/green]" if change > 0 else (f"[red]{change:.2f}%[/red]" if change < 0 else "0.00%")
        
        # Technical Summary Sub-table
        tech_table = Table.grid(padding=(0, 2))
        tech_table.add_column("Metric", style="bold white")
        tech_table.add_column("Value", style="cyan")
        
        tech_table.add_row("Last Close", f"${close:.2f} ({change_text})")
        
        sma5 = res.get("sma_5")
        sma20 = res.get("sma_20")
        sma60 = res.get("sma_60")
        tech_table.add_row("5-Day SMA", f"${sma5:.2f}" if sma5 else "N/A")
        tech_table.add_row("20-Day SMA", f"${sma20:.2f}" if sma20 else "N/A")
        tech_table.add_row("60-Day SMA", f"${sma60:.2f}" if sma60 else "N/A")
        
        vol_pct = res.get("volatility_pct", 0.0)
        vol_lvl = res.get("volatility_level", "Low")
        vol_color = "red" if vol_lvl == "High" else ("yellow" if vol_lvl == "Moderate" else "green")
        tech_table.add_row("Volatility", f"[{vol_color}]{vol_pct:.1f}% ({vol_lvl})[/{vol_color}]")
        
        sent_score = res.get("sentiment_score", 0.0)
        sent_lbl = res.get("sentiment_label", "Neutral")
        sent_color = "green" if sent_lbl == "Bullish" else ("red" if sent_lbl == "Bearish" else "yellow")
        tech_table.add_row("News Sentiment", f"[{sent_color}]{sent_lbl} ({sent_score:.2f})[/{sent_color}]")

        # Detailed Body Content
        body_text = Text()
        body_text.append("📊 Technical Indicators & Volatility:\n", style="bold underline")
        
        # Add tech sub-table to console rendering directly, but for Panel text we construct strings
        sma_vs_close = []
        if sma20:
            rel = "above" if close > sma20 else "below"
            sma_vs_close.append(f"Price is {rel} its 20-day trendline (${sma20:.2f})")
        if sma60:
            rel = "above" if close > sma60 else "below"
            sma_vs_close.append(f"Price is {rel} its 60-day trendline (${sma60:.2f})")
        
        sma_status_str = " | ".join(sma_vs_close)
        
        body_text.append(f"  • {sma_status_str}\n")
        body_text.append(f"  • Daily moves exhibit a {vol_lvl.lower()} risk profile (Annualized Volatility: {vol_pct:.1f}%)\n\n")
        
        body_text.append("🤖 Agent Prediction & Reasoning:\n", style="bold underline")
        body_text.append(f"  • Directional Outlook: {pred_text}\n")
        body_text.append(f"  • Core Summary: {res.get('summary', 'No summary available.')}\n\n")
        
        body_text.append("✅ Key Bullish Catalysts / Reasons:\n", style="bold green")
        for reason in res.get("reasons", []):
            body_text.append(f"  • {reason}\n")
        body_text.append("\n")
            
        body_text.append("⚠️ Key Bearish Warnings / Risks:\n", style="bold red")
        for risk in res.get("risks", []):
            body_text.append(f"  • {risk}\n")
        body_text.append("\n")
            
        body_text.append("📰 Latest News Articles Searched:\n", style="bold underline")
        news_items = res.get("news", [])[:3]
        if news_items:
            for n in news_items:
                headline_clean = n["headline"].replace("\n", " ")
                body_text.append(f"  • {headline_clean} ([dim cyan]{n['source']}[/dim cyan])\n")
        else:
            body_text.append("  • No recent news headlines found.\n")

        # Create detailed Panel
        console.print(Panel(
            body_text,
            title=f"[bold]{symbol}[/bold] - Close: ${close:.2f}",
            border_style=border_color,
            box=ROUNDED,
            padding=(1, 2)
        ))
        console.print("")

def generate_markdown_report(results: list, filepath: str = "stock_research_report.md"):
    """
    Generates a structured, beginner-friendly Markdown report.
    """
    valid_results = [r for r in results if r.get("success", False)]
    if not valid_results:
        return
        
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    with open(filepath, "w") as f:
        # 1. Header Banner & Disclaimer
        f.write("# 📈 Stock Market Research & Prediction Report\n\n")
        f.write("> [!IMPORTANT]\n")
        f.write("> **EDUCATIONAL USE ONLY. This tool provides research notes and is NOT financial advice.**\n\n")
        
        f.write(f"*Report generated on: {now_str}*\n\n")
        
        # 2. Plain-Language Portfolio Summary
        f.write("## 📝 Plain-Language Portfolio Summary\n\n")
        
        bullish_tickers = [r["symbol"] for r in valid_results if r["prediction"] == "Bullish"]
        bearish_tickers = [r["symbol"] for r in valid_results if r["prediction"] == "Bearish"]
        neutral_tickers = [r["symbol"] for r in valid_results if r["prediction"] == "Neutral"]
        
        f.write("### Portfolio Health Overview\n")
        if len(valid_results) == 1:
            res = valid_results[0]
            f.write(f"The research agent has evaluated **{res['symbol']}**. ")
            f.write(f"The stock is presenting a **{res['prediction']}** outlook with **{res['confidence_pct']}%** prediction confidence. ")
            f.write(f"This assessment is driven by {res['sentiment_label'].lower()} news headlines and a tech layout showing price sitting above/below moving averages. ")
            f.write("Please review the detailed technical breakdown and associated risks below before making paper-trading choices.\n\n")
        else:
            f.write(f"The research agent has analyzed a watch list of **{len(valid_results)} stocks**: ")
            f.write(f"{', '.join([r['symbol'] for r in valid_results])}. ")
            f.write("Here is the overall directional breakdown of your watchlist:\n")
            if bullish_tickers:
                f.write(f"- 🟢 **Bullish Setups ({len(bullish_tickers)}):** {', '.join(bullish_tickers)}\n")
            if neutral_tickers:
                f.write(f"- 🟡 **Neutral Consolidations ({len(neutral_tickers)}):** {', '.join(neutral_tickers)}\n")
            if bearish_tickers:
                f.write(f"- 🔴 **Bearish Downward Setups ({len(bearish_tickers)}):** {', '.join(bearish_tickers)}\n")
            
            f.write("\nOverall, the market health of this portfolio is ")
            if len(bullish_tickers) > len(bearish_tickers):
                f.write("**primarily bullish**, led by strong momentum in setups like " + f"{', '.join(bullish_tickers[:2])}. ")
            elif len(bearish_tickers) > len(bullish_tickers):
                f.write("**defensive or bearish**, showing technical weakness across major tickers. Capital conservation is highlighted.")
            else:
                f.write("**neutral and range-bound**, indicating a consolidating market without clear overarching momentum.")
            f.write("\n\n")

        # 3. Watch List Rankings Table
        if len(valid_results) > 1:
            f.write("### 🏆 Watch List Setup Ranking\n\n")
            f.write("| Rank | Symbol | Last Close | Day Change | Prediction | Confidence | News Sentiment | Setup Score (0-100) |\n")
            f.write("| :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |\n")
            for idx, res in enumerate(valid_results, start=1):
                change_sign = "+" if res["day_change_pct"] > 0 else ""
                change_str = f"{change_sign}{res['day_change_pct']:.2f}%"
                
                pred_emoji = "🟢 Bullish" if res["prediction"] == "Bullish" else ("🔴 Bearish" if res["prediction"] == "Bearish" else "🟡 Neutral")
                
                f.write(f"| {idx} | **{res['symbol']}** | ${res['last_close']:.2f} | {change_str} | {pred_emoji} | {res['confidence_pct']}% | {res['sentiment_label']} ({res['sentiment_score']:.2f}) | {res['bullish_score']}/100 |\n")
            f.write("\n*Setup Score represents our algorithmic evaluation of bullish setup strength, combining price crossovers, recent changes, and news sentiment.*\n\n")

        # 4. Detail Panel for Each Stock
        f.write("## 🔍 Detailed Stock Analysis\n\n")
        
        for res in valid_results:
            symbol = res["symbol"]
            pred = res["prediction"]
            conf = res["confidence_pct"]
            close = res["last_close"]
            change_sign = "+" if res["day_change_pct"] > 0 else ""
            change_str = f"{change_sign}{res['day_change_pct']:.2f}%"
            
            f.write(f"### {symbol} - {pred} ({conf}% Confidence)\n\n")
            f.write(f"**Last Close:** ${close:.2f} ({change_str})  \n")
            
            sma5_str = f"${res['sma_5']:.2f}" if res.get('sma_5') else "N/A"
            sma20_str = f"${res['sma_20']:.2f}" if res.get('sma_20') else "N/A"
            sma60_str = f"${res['sma_60']:.2f}" if res.get('sma_60') else "N/A"
            f.write(f"**Technical Indicators:** 5-Day SMA: {sma5_str} | 20-Day SMA: {sma20_str} | 60-Day SMA: {sma60_str}  \n")
            f.write(f"**Volatility:** {res['volatility_pct']:.1f}% ({res['volatility_level']})  \n")
            f.write(f"**Sentiment Scored:** {res['sentiment_label']} (Rating: {res['sentiment_score']:.2f})  \n\n")
            
            f.write(f"**Agent Evaluation Summary:**  \n{res['summary']}\n\n")
            
            f.write("#### 🟢 Key Bullish Catalysts\n")
            for reason in res["reasons"]:
                f.write(f"- {reason}\n")
            f.write("\n")
            
            f.write("#### 🔴 Key Bearish Risks & Warnings\n")
            for risk in res["risks"]:
                f.write(f"- {risk}\n")
            f.write("\n")
            
            # News feed
            f.write("#### 📰 Recent Headlines Feed\n")
            news_items = res.get("news", [])[:5]
            if news_items:
                for n in news_items:
                    headline_clean = n["headline"].replace("\n", " ").replace("|", "-")
                    # Convert pub date to string
                    pub_date = n["time"].strftime("%b %d, %Y")
                    # Print bullet with link if url is valid
                    if n["url"]:
                        f.write(f"- **{pub_date}** - [{headline_clean}]({n['url']}) (*{n['source']}*)\n")
                    else:
                        f.write(f"- **{pub_date}** - {headline_clean} (*{n['source']}*)\n")
            else:
                f.write("- No recent news headlines found for this ticker.\n")
                
            f.write("\n---\n\n")
            
        # 5. Educational Explanations Section
        f.write("## 📚 Beginner-Friendly Educational Glossary\n\n")
        f.write("To help you build your trading knowledge, here are simple definitions for the technical parameters used in this report:\n\n")
        
        f.write("### 1. Simple Moving Average (SMA)\n")
        f.write("An **SMA** calculates the average price of a stock over a specific number of trading days. It smoothens daily fluctuations to reveal the overall trend direction:\n")
        f.write("- **5-Day SMA:** Reflects ultra-short term momentum. Crossovers here show quick sentiment pivots.\n")
        f.write("- **20-Day SMA:** Represents the standard short-term trend. Crossovers above or below the 20-day average are major trigger signals for swing traders.\n")
        f.write("- **60-Day SMA:** Tracks the medium-to-long term support. A stock trading above its 60-day SMA is in a healthy structural uptrend.\n")
        f.write("- **Golden Cross Crossover:** When a short-term average (e.g. 5-day or 20-day) crosses *above* a long-term average, it indicates strong buyers entering and a bullish trend starting.\n\n")
        
        f.write("### 2. Volatility (Annualized)\n")
        f.write("**Volatility** calculates how wildly a stock's price swings up and down. We annualize it based on standard daily variations over the last 20 trading days:\n")
        f.write("- **Low Volatility (<15%):** Predictable, steady price curves (common in stable blue-chips or ETFs like SPY).\n")
        f.write("- **Moderate Volatility (15% - 30%):** Standard fluctuations, healthy swing trading territory.\n")
        f.write("- **High Volatility (>30%):** Big, less predictable price moves (typical in high-growth tech, biotech, or meme stocks). *Higher volatility equals bigger risks but potentially higher rewards.*\n\n")
        
        f.write("### 3. News Sentiment Rating\n")
        f.write("We scan the recent financial headlines for keywords to judge market psychology. Scores range from **-1.00 (strongly negative)** to **+1.00 (strongly positive)**:\n")
        f.write("- **Positive headlines** (e.g., 'upgrade', 'beat earnings', 'revenue surge') signal that buyers feel positive about the stock.\n")
        f.write("- **Negative headlines** (e.g., 'downgrade', 'lawsuit', 'slump') signal fear or heavy sellers.\n\n")
        
        f.write("### 4. Setup Score (0-100)\n")
        f.write("A quantitative score calculated by our engine to measure bullish conviction. A score above 60 represents a bullish setup, below 40 a bearish setup, and between 40-60 a neutral, range-bound consolidation.\n")
        
    console.print(f"[bold green]✓ Markdown report successfully saved to: {filepath}[/bold green]\n")
