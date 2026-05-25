"""
Memory Helper - Shared module for all agents to read/write to Obsidian vault
"""

import os
import json
from datetime import datetime
from pathlib import Path

class MemoryHelper:
    def __init__(self):
        self.vault_path = Path("C:\\trading-memory\\obsidian-vault")
        self.vault_path.mkdir(exist_ok=True)
        
        # Create subfolders if they don't exist
        for folder in ["Trades", "Insights", "Strategies", "News", "Daily-Logs"]:
            (self.vault_path / folder).mkdir(exist_ok=True)
    
    def save_trade(self, trade_data):
        """Save a trade to Obsidian vault"""
        filename = self.vault_path / "Trades" / f"trade_{trade_data.get('ticket', datetime.now().timestamp())}.md"
        content = f"""---
type: trade
ticket: {trade_data.get('ticket', 'N/A')}
symbol: {trade_data.get('symbol', 'N/A')}
action: {trade_data.get('action', 'N/A')}
volume: {trade_data.get('volume', 0)}
price: {trade_data.get('price', 0)}
profit: {trade_data.get('profit', 0)}
is_win: {trade_data.get('is_win', False)}
timestamp: {datetime.now().isoformat()}
---

## Trade Details

- **Symbol:** {trade_data.get('symbol', 'N/A')}
- **Action:** {trade_data.get('action', 'N/A')}
- **Volume:** {trade_data.get('volume', 0)}
- **Entry Price:** {trade_data.get('price', 0)}
- **Profit/Loss:** ${trade_data.get('profit', 0):+.2f}
- **Result:** {'WIN' if trade_data.get('is_win', False) else 'LOSS'}

## Reasoning

{trade_data.get('reasoning', 'No reasoning recorded')}

## Notes

(Add notes here after trade closes)
"""
        with open(filename, 'w') as f:
            f.write(content)
        return str(filename)
    
    def save_insight(self, insight_data):
        """Save an AI-generated insight to Obsidian vault"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        filename = self.vault_path / "Insights" / f"insight_{timestamp}.md"
        content = f"""---
type: insight
source: {insight_data.get('source', 'Unknown')}
confidence: {insight_data.get('confidence', 0)}
timestamp: {datetime.now().isoformat()}
---

# {insight_data.get('title', 'Insight')}

{insight_data.get('content', '')}

## Related
- **Action:** {insight_data.get('suggested_action', 'None')}
- **Confidence:** {insight_data.get('confidence', 0)}%
"""
        with open(filename, 'w') as f:
            f.write(content)
        return str(filename)
    
    def save_strategy(self, strategy_data):
        """Save a generated strategy to Obsidian vault"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        name = strategy_data.get('name', f'strategy_{timestamp}')
        filename = self.vault_path / "Strategies" / f"{name.replace(' ', '_')}.md"
        content = f"""---
type: strategy
name: {strategy_data.get('name', 'Unknown')}
status: {strategy_data.get('status', 'pending')}
created: {datetime.now().isoformat()}
---

# {strategy_data.get('name', 'Strategy')}

## Entry Conditions
{chr(10).join(f'- {c}' for c in strategy_data.get('entry_conditions', []))}

## Exit Conditions
{chr(10).join(f'- {c}' for c in strategy_data.get('exit_conditions', []))}

## Risk Management
- **Stop Loss:** {strategy_data.get('stop_loss', 'N/A')}
- **Risk Per Trade:** {strategy_data.get('risk_per_trade', 1)}%

## Performance
- **Win Rate:** {strategy_data.get('win_rate', 'Pending')}%
- **Total Trades:** {strategy_data.get('total_trades', 0)}
- **Net Profit:** ${strategy_data.get('net_profit', 0):+.2f}
"""
        with open(filename, 'w') as f:
            f.write(content)
        return str(filename)
    
    def save_news_impact(self, news_data):
        """Save news impact analysis to Obsidian vault"""
        timestamp = datetime.now().strftime('%Y-%m-%d_%H%M%S')
        filename = self.vault_path / "News" / f"news_{timestamp}.md"
        content = f"""---
type: news
sentiment: {news_data.get('sentiment', 'NEUTRAL')}
confidence: {news_data.get('confidence', 0)}
timestamp: {datetime.now().isoformat()}
---

# {news_data.get('title', 'News Impact')}

**Summary:** {news_data.get('summary', 'N/A')}

## Affected Symbols
{chr(10).join(f'- {s}' for s in news_data.get('affected_symbols', []))}

## Trading Recommendation
{news_data.get('recommendation', 'Monitor price action')}

## Source
{news_data.get('link', 'Unknown')}
"""
        with open(filename, 'w') as f:
            f.write(content)
        return str(filename)
    
    def get_recent_insights(self, limit=10):
        """Read recent insights from Obsidian for self-reflection"""
        insights = []
        insights_dir = self.vault_path / "Insights"
        if insights_dir.exists():
            files = sorted(insights_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
            for f in files:
                with open(f, 'r') as file:
                    content = file.read()
                    insights.append(content)
        return insights
    
    def get_recent_trades(self, limit=20):
        """Read recent trades from Obsidian for self-reflection"""
        trades = []
        trades_dir = self.vault_path / "Trades"
        if trades_dir.exists():
            files = sorted(trades_dir.glob("*.md"), key=lambda x: x.stat().st_mtime, reverse=True)[:limit]
            for f in files:
                with open(f, 'r') as file:
                    content = file.read()
                    trades.append(content)
        return trades

# Global instance for all agents to use
memory = MemoryHelper()