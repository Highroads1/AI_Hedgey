import os
import sys
from datetime import datetime
from dotenv import dotenv_values
import alpaca_trade_api as tradeapi
from crewai import Agent, Task, Crew, LLM

# Initialize local brain explicitly
local_brain = LLM(
    model="ollama/qwen2.5-coder:7b",
    base_url="http://localhost:11434",
    temperature=0.1
)

def fetch_equity(env_path):
    """Pulls live equity from a target env file configuration."""
    if not os.path.exists(env_path):
        return 0.0
    config = dotenv_values(env_path)
    try:
        client = tradeapi.REST(
            key_id=config.get("ALPACAS_API_KEY"),
            secret_key=config.get("ALPACAS_SECRET_KEY"),
            base_url="https://paper-api.alpaca.markets",
            api_version='v2'
        )
        return float(client.get_account().equity)
    except Exception:
        return 0.0

if __name__ == "__main__":
    print("--- Starting Multi-Strategy Portfolio Audit ---")
    
    # 1. Gather raw data from the three sandboxes
    v_eq = fetch_equity("vanilla.env")
    m_eq = fetch_equity("martingale.env")
    k_eq = fetch_equity("kelly.env")
    
    raw_metrics = f"""
    TIMESTAMP: {datetime.now()}
    
    STRATEGY PERFORMANCE METRICS:
    1. Vanilla 1% Strategy Current Net Value: ${v_eq:.2f}
    2. Martingale Scaling Strategy Current Net Value: ${m_eq:.2f}
    3. Kelly Criterion Strategy Current Net Value: ${k_eq:.2f}
    """
    
    # 2. Deploy the Performance Auditor Agent
    auditor = Agent(
        role="Lead Portfolio Performance Auditor",
        goal="Analyze the performance values of competing trading strategies and compile an executive summary.",
        backstory="You act as a neutral data controller. You rank performance objectively and strip out complexity.",
        llm=local_brain,
        verbose=True
    )
    
    audit_task = Task(
        description=f"Review these raw net asset values:\n{raw_metrics}\nCalculate the performance rankings, declare the current leading strategy, and highlight any massive divergences or risks.",
        expected_output="A concise, scannable markdown table displaying the leaderboard followed by 2 bullet points highlighting specific performance observations.",
        agent=auditor,
        llm=local_brain
    )
    
    audit_crew = Crew(
        agents=[auditor],
        tasks=[audit_task]
    )
    
    summary_report = audit_crew.kickoff()
    
    # 3. Append the results to a centralized leaderboard file
    with open("strategy_leaderboard.md", "a", encoding="utf-8") as f:
        f.write(f"\n\n## Audit Run: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{summary_report}\n---")
        
    print("Audit Complete. strategy_leaderboard.md updated successfully.")