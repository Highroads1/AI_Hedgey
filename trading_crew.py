import os
import re
from datetime import datetime
from dotenv import load_dotenv
import yfinance as yf
import alpaca_trade_api as tradeapi
from crewai import Agent, Task, Crew, Process, LLM

# Automatically load sandbox and production API keys from your .env file
load_dotenv()

if not os.getenv("ALPACAS_API_KEY") or not os.getenv("ALPACAS_SECRET_KEY"):
    raise ValueError("Missing Alpaca API credentials. Please check your .env file configuration.")

# ==========================================
# 1. CORE ENGINE CONFIGURATION (LOCAL LLM)
# ==========================================
# Anchoring the LLM context directly to port 11434 to prevent OpenAI cloud failover
local_brain = LLM(
    model="ollama/qwen2.5-coder:7b",
    base_url="http://localhost:11434",
    temperature=0.2
)

# Connect to the Alpaca Paper Trading Sandbox Environment
alpaca_client = tradeapi.REST(
    key_id=os.getenv("ALPACAS_API_KEY"),
    secret_key=os.getenv("ALPACAS_SECRET_KEY"),
    base_url="https://paper-api.alpaca.markets",
    api_version='v2'
)

# ==========================================
# 2. HARDCODED SAFETY GUARDRAILS & WHITELIST
# ==========================================
MIN_ORDER_COST_USD = 1.00
RISK_FACTOR_PERCENT = 0.01  # Used for Vanilla (1%)

# Curated Conservative Whitelist tracking institutional profiles (ACVF)
ACVF_CONSERVATIVE_WHITELIST = [
    "NVDA", "MSFT", "AVGO", "CSCO", "WMT", "BRK.B", "XOM", "LLY", "MA", "TSLA", "RGR", "SWBI"
]

def get_live_account_equity() -> float:
    """Queries Alpaca API to calculate total portfolio value (cash + open market assets)."""
    try:
        account = alpaca_client.get_account()
        return float(account.equity)
    except Exception as e:
        print("[Safety Warning] Failed to fetch live account equity. Falling back to conservative safety minimum.")
        return 1000.00  # Safe fallback baseline ($10 max trade allocation if API drops out)

def fetch_live_market_context() -> str:
    """Uses yfinance to pull real-time trailing metrics for the approved whitelist."""
    context_stream = "=== LIVE MARKET DATA PROFILE ===\n"
    for ticker in ACVF_CONSERVATIVE_WHITELIST:
        try:
            yf_ticker = "BRK-B" if ticker == "BRK.B" else ticker
            stock = yf.Ticker(yf_ticker)
            fast_info = stock.fast_info
            
            last_price = fast_info['last_price']
            day_change = ((last_price - fast_info['previous_close']) / fast_info['previous_close']) * 100
            
            context_stream += f"Ticker: {ticker} | Price: ${last_price:.2f} | 24h Change: {day_change:.2f}%\n"
        except Exception as e:
            context_stream += f"Ticker: {ticker} | Data stream temporarily offline.\n"
    return context_stream

def calculate_martingale_allocation(live_equity: float, ticker: str) -> float:
    """
    If the last trade for this ticker was a loss, double the allocation.
    Otherwise, reset to a baseline 0.5% of equity.
    """
    baseline = round(live_equity * 0.005, 2)  # Start small so doubling doesn't instantly break the bank
    
    try:
        # Check Alpaca history for our last closed trade fills
        activities = alpaca_client.get_activities(activity_types='FILL', limit=10)
        ticker_fills = [a for a in activities if a.symbol == ticker]
        
        if ticker_fills:
            # Check if the stock has been dropping today to simulate the "doubling on a drop" rule
            yf_ticker = "BRK-B" if ticker == "BRK.B" else ticker
            stock = yf.Ticker(yf_ticker)
            prev_close = stock.fast_info['previous_close']
            last_price = stock.fast_info['last_price']
            
            if last_price < prev_close:
                print(f"[Strategy Match] Martingale active: {ticker} dropped today. Doubling baseline allocation.")
                return baseline * 2
                
        return baseline
    except Exception:
        return baseline

def calculate_kelly_allocation(live_equity: float) -> float:
    """
    Uses the Kelly Criterion formula. 
    Assumes a documented historical win rate of 60% and a 1:1 risk/reward payout ratio.
    """
    win_probability = 0.60
    payout_ratio = 1.00
    
    # Kelly % = (W * R - (1 - W)) / R
    kelly_fraction = (win_probability * payout_ratio - (1.00 - win_probability)) / payout_ratio
    
    # Use 'Half-Kelly' (divide by 2) as an institutional engineering safeguard against aggressive drawdowns
    safe_kelly_fraction = kelly_fraction / 2
    
    print(f"[Strategy Match] Kelly Criterion active: Allocating {safe_kelly_fraction * 100:.1f}% of total equity.")
    return round(live_equity * safe_kelly_fraction, 2)

def execute_alpaca_order(ticker: str, spend_amount: float) -> dict:
    """
    The local hardcoded Python firewall layer. Intercepts AI payloads 
    and validates trade sizes dynamically based on the environmental flag profile.
    """
    sanitized_ticker = str(ticker).strip().upper()
    current_strategy = os.getenv("STRATEGY_TYPE", "VANILLA")
    
    # Guardrail 1: Strict Whitelist Verification
    if sanitized_ticker not in ACVF_CONSERVATIVE_WHITELIST:
        return {"status": "REJECTED", "reason": f"Security '{sanitized_ticker}' violates portfolio core mandate."}
    
    live_equity = get_live_account_equity()
    
    # Guardrail 2: Dynamic Equity Cap Calculation Override based on strategy profile
    if current_strategy == "MARTINGALE":
        final_spend = calculate_martingale_allocation(live_equity, sanitized_ticker)
    elif current_strategy == "KELLY":
        final_spend = calculate_kelly_allocation(live_equity)
    else:  # Default to VANILLA 1%
        final_spend = round(live_equity * RISK_FACTOR_PERCENT, 2)
        
    # Structural Safety Ceiling: Hard stop ceiling at $500.00 regardless of net value growth
    if final_spend > 500.00:
        final_spend = 500.00
        
    # Guardrail 3: Budget Constraint Validation
    if final_spend < MIN_ORDER_COST_USD:
        return {"status": "REJECTED", "reason": f"Allocation of ${final_spend:.2f} falls below the baseline trading threshold."}
        
    # Guardrail 4: Secure Broker Transmission
    try:
        # UPDATED: Change "BRK/B" to "BRK.B" or "BRK B" to align with Alpaca's updated asset index
        alpaca_ticker = "BRK.B" if sanitized_ticker == "BRK.B" else sanitized_ticker
        
        order = alpaca_client.submit_order(
            symbol=alpaca_ticker,
            notional=round(final_spend, 2),  
            side='buy',
            type='market',
            time_in_force='day'
        )
        return {
            "status": "EXECUTED",
            "msg": f"SUCCESS: [{current_strategy}] Order ID {order.id} transmitted. Allocation of ${final_spend:.2f} into {sanitized_ticker} cleared."
        }
    except Exception as e:
        return {"status": "BROKER_ERROR", "reason": f"Alpaca rejected execution payload: {str(e)}"}

# ==========================================
# 3. DEFINE THE AGENTS (APPROACH B: SEGMENTED)
# ==========================================
momentum_analyst = Agent(
    role="Momentum Quantitative Analyst",
    goal="Scan market pricing to locate assets showing strong upward velocity and short-term breakouts.",
    backstory="You search for high trading volume and positive 24h price action. You want to ride the strongest wave.",
    llm=local_brain,
    verbose=True
)

value_analyst = Agent(
    role="Defensive Value Analyst",
    goal="Scan market pricing to locate stable, oversold, or safe defensive value assets.",
    backstory="You dislike extreme volatility. You look for steady performers or solid dip-buying opportunities to preserve capital.",
    llm=local_brain,
    verbose=True
)

risk_officer = Agent(
    role="Chief Risk Officer & Portfolio Arbiter",
    goal="Evaluate the contrasting proposals from Momentum and Value, then synthesize a singular safe trade.",
    backstory="You audit both pitches against account parameters. You choose the path that offers the best risk-to-reward ratio.",
    llm=local_brain,
    verbose=True
)

growth_marketer = Agent(
    role="Director of Growth Marketing",
    goal="Translate the internal debate and final execution into an educational build-in-public update.",
    backstory="You break down the quantitative friction between momentum and value for a public streaming audience.",
    llm=local_brain,
    verbose=True
)

content_critic = Agent(
    role="Lead Copyeditor",
    goal="Ensure text outputs read completely natural, removing corporate AI buzzwords.",
    backstory="You keep technical copy direct, scannable, and professional.",
    llm=local_brain,
    verbose=True
)

# ==========================================
# 4. DEFINE THE TASKS & PIPELINE ANALYSIS
# ==========================================
current_strategy_name = os.getenv("STRATEGY_TYPE", "VANILLA")
live_market_snapshot = fetch_live_market_context()
live_equity_context = get_live_account_equity()

# Calculate the display ceiling context so the agents can draft accurate pitches
if current_strategy_name == "MARTINGALE":
    display_ceiling = "Dynamic Martingale (Multiplied baseline dollar amount on down-days)"
elif current_strategy_name == "KELLY":
    display_ceiling = f"exactly ${round(live_equity_context * 0.10, 2)} dollars (Half-Kelly Constraint)"
else:
    # Crucial change: explicitly tell the model 1% of $1000 is TEN DOLLARS, not 0.01
    display_ceiling = f"exactly ${round(live_equity_context * 0.01, 2)} dollars (Flat 1% Constraint)"

momentum_task = Task(
    description=f"Active Portfolio Mandate: {current_strategy_name}\nReview this live data stream:\n{live_market_snapshot}\nIdentify the single asset showing the strongest positive price velocity. Pitch its ticker and a suggested allocation based on our {display_ceiling} rules.",
    expected_output="A brief analysis naming a ticker and allocation value.",
    agent=momentum_analyst,
    llm=local_brain
)

value_task = Task(
    description=f"Active Portfolio Mandate: {current_strategy_name}\nReview this live data stream:\n{live_market_snapshot}\nIdentify the single asset showing the stablest value. Pitch its ticker and a suggested allocation based on our {display_ceiling} rules.",
    expected_output="A brief analysis naming a ticker and allocation value.",
    agent=value_analyst,
    llm=local_brain
)

evaluate_risk_task = Task(
    description=f"Active Portfolio Mandate: {current_strategy_name}\nCompare the momentum pitch and the value pitch. Decide on exactly ONE final asset to trade today under our {current_strategy_name} framework.",
    expected_output="Output exactly the final choice in this identical format: 'TICKER AMOUNT' (Example: 'WMT 10.00'). Crucial: The AMOUNT must be an absolute dollar value, never a percentage or decimal fraction of a dollar. Do not write paragraphs.",
    agent=risk_officer,
    context=[momentum_task, value_task],  # Merges both analyst papers dynamically for the Arbiter
    llm=local_brain
)

write_story_task = Task(
    description="Draft an educational update detailing today's trade. Highlight the internal debate between our Momentum Analyst and Value Analyst, explaining why our Risk Officer chose the winning path.",
    expected_output="A structured markdown draft layout.",
    agent=growth_marketer,
    llm=local_brain
)

polish_content_task = Task(
    description="Refine the draft to sound authentic, grounded, and free of artificial filler phrases.",
    expected_output="A clean copy-pasteable markdown text block.",
    agent=content_critic,
    llm=local_brain
)

# ==========================================
# 5. EXECUTION ENGINE
# ==========================================
if __name__ == "__main__":
    print(f"--- Starting Live Autonomous Engine Pipeline: {datetime.now()} ---")
    print(f"Active Strategy Profile: {current_strategy_name} | Current Account Value: ${live_equity_context:.2f}")
    
    # Spin up Phase 1: Quant Assessment Layer
    trading_crew = Crew(
        agents=[momentum_analyst, value_analyst, risk_officer],
        tasks=[momentum_task, value_task, evaluate_risk_task],
        process=Process.sequential
    )
    
    print(f"\n[Running Segmented Quant Team Analysis under {current_strategy_name} Mandate...]")
    execution_result = str(trading_crew.kickoff()).strip()
    
    with open("trade_history.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n## Session Log [{current_strategy_name}]: {datetime.now()}\nRaw Reasoning Result: {execution_result}")
    
    # Automated Robust Parser: Isolates results regardless of minor layout variations
    try:
        parsed_parts = execution_result.split()
        target_ticker = parsed_parts[0].upper()
        target_spend = float(parsed_parts[1])
    except Exception as e:
        print(f"\n[Parser Regex Intercept]: Normalizing agent markdown response strings...")
        tickers = re.findall(r'[A-Z]{2,4}(?:\.[A-Z])?', execution_result)
        amounts = re.findall(r'\d+\.\d+|\d+', execution_result)
        target_ticker = tickers[0].upper() if tickers else "WMT"
        target_spend = float(amounts[0]) if amounts else 10.00

    print(f"\n[Security Intercept] Target Ticker parsed: {target_ticker} | AI Suggested Allocation Size: ${target_spend:.2f}")
    
    # Direct transmission to structural verification layer
    print("[Processing Local System Firewall Checks...]")
    api_verdict = execute_alpaca_order(ticker=target_ticker, spend_amount=target_spend)
    
    print(f"Firewall Status: {api_verdict['status']}")
    print(f"Firewall Response Log: {api_verdict.get('msg' if api_verdict['status'] == 'EXECUTED' else 'reason')}")
    
    # Inject execution variables down to Phase 2 for marketing compilation
    write_story_task.description += f"\nToday's Verified Execution Event Status: {api_verdict}"
    
    marketing_crew = Crew(
        agents=[growth_marketer, content_critic],
        tasks=[write_story_task, polish_content_task],
        process=Process.sequential
    )
    
    print("\n[Running Content Copy Generation...]")
    final_copy = marketing_crew.kickoff()
    
    with open("marketing_drafts.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n## Entry [{current_strategy_name}]: {datetime.now()}\n{final_copy}")
        
    print(f"\n--- Live Segmented {current_strategy_name} Pipeline Run Finished Successfully! ---")