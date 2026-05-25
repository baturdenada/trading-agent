# 🧠 Intelligence Hub - Complete Trading Automation System

## Overview

The Intelligence Hub is a three-part intelligent trading system that adds **natural language processing**, **workflow automation**, and **self-improvement capabilities** to your existing trading ecosystem.

```
Your Commands
     ↓
Intelligence Hub
     ├→ NLP Engine (natural language understanding)
     ├→ Workflow Engine (n8n-style automation)
     ├→ Self-Modification (code optimization)
     ↓
Ultimate Trader & Agents
     ↓
Real Trading Results
```

---

## ⚡ Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
# (Already installed: MetaTrader5, requests, openai, numpy, pandas, flask, psutil, feedparser, jinja2)
pip install jinja2  # Add if not installed
```

### 2. Run the Intelligence Hub

```bash
cd "C:\Users\user\Desktop\DS trading agent"
python intelligence_hub.py
```

You should see:
```
🧠 INTELLIGENCE HUB ONLINE
NLP + Workflows + Self-Modification
```

### 3. Start Sending Commands via Telegram

```
Text: "Analyze XAUUSD for 30 days"
Response: Detailed analysis with trend, levels, and strategy recommendation
```

---

## 📖 System Components

### Part 1: NLP Engine (`nlp_engine.py`)

**What it does:** Understands ANY trading-related command in natural language

**Supported Commands:**
- `"Analyze XAUUSD for the last 30 days"` → Symbol analysis with trend detection
- `"Backtest EURUSD with TP 300 and SL 2000"` → Full backtest with results
- `"Optimize XAGUSD parameters"` → Find best TP/SL combination
- `"Show me trading stats"` → Account statistics
- `"What's my risk level?"` → Risk analysis

**How it works:**
1. Extracts parameters from text (symbols, days, TP, SL, indicators)
2. Classifies intent (ANALYZE, BACKTEST, OPTIMIZE, STATS, RISK, COMPARE, REPORT)
3. Routes to appropriate handler
4. Returns formatted Telegram response

**Example Flow:**
```
Input: "Analyze XAUUSD for 30 days"
     ↓
Extract: symbol=XAUUSD, days=30
     ↓
Intent: ANALYZE
     ↓
Action: Get candles → Calculate metrics → Format result
     ↓
Output: 📈 XAUUSD ANALYSIS (30 days) ... Trend: UPTREND ...
```

---

### Part 2: Workflow Engine (`workflow_engine.py`)

**What it does:** Execute complex trading workflows defined in markdown

**Key Features:**
- Define workflows as markdown files
- Support for multiple step types (API calls, Python scripts, AI summaries, file writes, Telegram sends)
- Variable substitution with Jinja2 templating
- Error handling (continue on error, skip steps)
- Execution logging to Obsidian vault

**Workflow File Format:**

```markdown
---
name: workflow-name
trigger: manual
inputs:
  - symbol: XAUUSD.s
  - days: 30
---

# Workflow Title

## Step 1: Description
- action: get_candles
- symbol: {{symbol}}
- days: {{days}}
- output: candle_data

## Step 2: Description
- action: ai_summary
- input: {{candle_data}}
- prompt: "Analyze this data and..."
- output: analysis
```

**Available Step Actions:**

| Action | Purpose | Inputs |
|--------|---------|--------|
| `get_candles` | Fetch OHLC data | symbol, days |
| `get_account` | Get account info | none |
| `python_script` | Run Python script | script, params |
| `ai_summary` | AI analysis | input, prompt |
| `write_file` | Save to file | path, content |
| `telegram_send` | Send Telegram message | message |
| `api_call` | HTTP API call | url, method, body |

**Example Workflows Included:**

1. **analyze-strategy.md** - Analyze a trading strategy with backtest
2. **daily-report.md** - Generate daily performance report  
3. **compare-symbols.md** - Compare multiple symbols

**Run a Workflow:**
```
Text: "run analyze-strategy workflow"
System: Loads → Executes 5 steps → Saves report to Obsidian → Sends Telegram
```

---

### Part 3: Self-Modification System (`self_modifier.py`)

**What it does:** Analyze system performance and suggest code improvements

**How it works:**

1. **Analyze Performance**
   - Read trade history from memory
   - Calculate metrics (win rate, profit, avg win/loss)
   
2. **Read Code**
   - Load current system code
   - Understand trading parameters
   
3. **Generate Suggestions**
   - Use Claude/DeepSeek to suggest improvements
   - For each suggestion: parameter name, current value, proposed value, impact
   
4. **User Approval**
   - Send suggestions to Telegram
   - Wait for user to approve specific ones
   
5. **Apply Changes**
   - Backup original code
   - Apply approved suggestions
   - Notify user to restart agent

**Example Suggestions:**

```
#1 Increase Position Size
   Parameter: base_risk
   Current: 0.02
   Proposed: 0.03
   Impact: Scale up profitable trading by 50%
   Difficulty: Easy

#2 Tighter Stop Loss
   Parameter: risk_in_pips
   Current: 50
   Proposed: 35
   Impact: Reduce average loss by 30%
   Difficulty: Easy
```

**Commands:**

```
Text: "self-analyze"
Response: Performance analysis + suggested improvements

Text: "1,3,5"  (after suggestions)
Response: Changes applied, restart agent to activate
```

---

## 🚀 Example Usage Scenarios

### Scenario 1: Quick Market Analysis

**User:** "Analyze XAUUSD for the last 30 days using breakout strategy"

**System:**
1. NLP extracts: symbol=XAUUSD, days=30, strategy=breakout
2. Fetches 30 days of candle data
3. Calculates trend, support/resistance, volatility
4. Returns formatted analysis

**Response:**
```
📈 XAUUSD ANALYSIS (30 days)

Price Data:
• Current: $4554.50
• 20-day High: $4650.00
• 20-day Low: $4450.00
• Range: $200.00

Trend:
• SMA20: $4520
• SMA50: $4480
• Status: UPTREND

Levels:
• Distance to High: 2.1%
• Distance to Low: 2.3%

Strategy: Breakout
Timeframe: Daily
Data: Last 30 days
```

---

### Scenario 2: Backtest & Optimize

**User:** "Backtest EURUSD with TP 300 and SL 2000 for the last 60 days"

**System:**
1. NLP extracts: symbol=EURUSD, tp=300, sl=2000, days=60
2. Fetches 60 days of data
3. Simulates high/low breakout strategy
4. Returns win rate, profit, and statistics

**Response:**
```
🎯 BACKTEST RESULTS

Symbol: EURUSD.s
Period: 60 days
Strategy: High/Low Breakout
TP: 300 points
SL: 2000 points

Results:
• Total Trades: 45
• Wins: 32 | Losses: 13
• Win Rate: 71.1%
• Net Profit: $2,850
• Profit Factor: 2.4

✅ PROFITABLE | GOOD WIN RATE
```

---

### Scenario 3: Daily Automated Report

**Setup:** Workflow scheduled daily at 22:00

**Workflow: daily-report.md**
1. Gets current account status
2. Generates AI summary
3. Creates Obsidian report
4. Sends Telegram notification

**Automatic Response:**
```
📊 DAILY REPORT - 2026-05-23

💰 Balance: $4,500
💹 Daily PnL: +$147

Account performing well. Equity is solid.
Continue current trading strategy.

📁 Full report saved to Obsidian
```

---

### Scenario 4: Self-Improvement

**User:** "Self-analyze"

**System:**
1. Reads 2,072 trades from history
2. Analyzes performance (90.2% win rate, $4,388 profit)
3. Reads `ultimate_trader.py` code
4. Uses Claude to suggest 3-5 improvements

**Response:**
```
🧠 SELF-IMPROVEMENT SUGGESTIONS

#1 Increase Position Size
   Current: base_risk = 0.02
   Proposed: base_risk = 0.03
   Impact: Scale profitable trading by 50%
   Difficulty: Easy

#2 Dynamic Trailing Stop
   Current: trailing_distance = 0.5
   Proposed: trailing_distance = 0.3 (dynamic based on volatility)
   Impact: Capture more profits in trending markets
   Difficulty: Medium

#3 Time-Based Risk Reduction
   Current: Same risk all day
   Proposed: Reduce risk 30% at market close
   Impact: Reduce overnight gap risk by 40%
   Difficulty: Easy

Reply with numbers to approve: "1,2,3"
```

**User:** "1,3"

**System:**
1. Backs up original code
2. Applies suggestions #1 and #3
3. Saves changes
4. Asks to restart agent

---

## 📊 Integration with Existing System

The Intelligence Hub **does NOT replace** your existing agents. Instead, it **enhances** them:

```
Your Existing System:
├─ Ultimate Trader (trades 24/7) ← UNCHANGED
├─ Teacher Agent (analyzes trades) ← UNCHANGED  
├─ Strategy Agent (creates strategies) ← UNCHANGED
├─ News Agent (monitors news) ← UNCHANGED
└─ Orchestrator (monitors all) ← UNCHANGED

Intelligence Hub (NEW):
├─ NLP Engine (understands commands)
├─ Workflow Engine (automates complex tasks)
├─ Self-Modifier (suggests improvements)
└─ Integration Hub (ties everything together)

Both systems work together via:
- Shared memory files (JSON in C:\trading-memory\)
- Shared Obsidian vault
- Telegram bot coordination
- MT5 API access
```

---

## 🛠️ Deployment Steps

### Step 1: Copy Files to Your System

```bash
# All files are already created in:
# C:\Users\user\Desktop\DS trading agent\

nlp_engine.py
workflow_engine.py
self_modifier.py
intelligence_hub.py

# Plus workflows in:
# C:\Users\user\Desktop\DS trading agent\workflows\

analyze-strategy.md
daily-report.md
compare-symbols.md
```

### Step 2: Start Intelligence Hub

```bash
cd "C:\Users\user\Desktop\DS trading agent"
python intelligence_hub.py

# Output should show:
# 🧠 INTELLIGENCE HUB ONLINE
# 2026-05-23 10:30:45 | Intelligence Hub initialized
# 2026-05-23 10:30:46 | Intelligence Hub running
```

### Step 3: Test via Telegram

Send a message to your bot:
```
Text: "Analyze XAUUSD for 30 days"
Expected: Full analysis with trend, levels, and recommendations
```

### Step 4: Create Custom Workflows (Optional)

Copy an existing workflow and modify:

```bash
cp workflows\analyze-strategy.md workflows\custom-workflow.md
# Edit custom-workflow.md with your own steps
# Run: "execute custom-workflow"
```

---

## 📝 Custom Workflow Template

Create new workflows by copying this template:

```markdown
---
name: my-workflow
description: Description of what this does
trigger: manual
inputs:
  - symbol: XAUUSD.s
  - days: 30
---

# My Custom Workflow

## Step 1: Get Data
- action: get_candles
- symbol: {{symbol}}
- days: {{days}}
- output: data

## Step 2: Analyze
- action: ai_summary
- input: {{data}}
- prompt: "Analyze this price data and..."
- output: analysis

## Step 3: Report
- action: write_file
- path: C:\trading-memory\obsidian-vault\Report_{{date}}.md
- content: |
  # Analysis Report
  {{analysis}}

## Step 4: Notify
- action: telegram_send
- message: "Analysis complete: {{analysis}}"
```

Save to: `workflows\my-workflow.md`

Then use: `"run my-workflow workflow"`

---

## 🔧 Customization Guide

### Modify NLP Intent Classification

Edit `nlp_engine.py`, line ~140:

```python
def classify_intent(self, text):
    prompt = f"""Classify into ONE category:
ANALYZE - analyze a symbol
BACKTEST - test a strategy
YOUR_NEW_INTENT - your custom intent
...
"""
```

### Add New Workflow Step Type

Edit `workflow_engine.py`, add to `execute_step()`:

```python
elif action == 'your_action':
    return self.step_your_action(step, context)

def step_your_action(self, step, context):
    # Your implementation here
    return {'success': True, 'output': result}
```

### Modify Self-Improvement Suggestions

Edit `self_modifier.py`, line ~100:

```python
prompt = f"""...
For each suggestion:
- YOUR_CUSTOM_FIELD
- YOUR_CUSTOM_PARAMETER
...
"""
```

---

## 🐛 Troubleshooting

### Issue: "MT5 connection failed"

**Solution:** Check `.env` file has correct credentials:
```
MT5_LOGIN=9770723
MT5_PASSWORD=Batden01*
MT5_SERVER=Bybit-Demo
MT5_PATH=C:\Program Files\MetaTrader 5\terminal64.exe
```

### Issue: "Workflow not found"

**Solution:** Workflow files must be in `workflows/` folder with `.md` extension

### Issue: "No trades found for analysis"

**Solution:** Need at least 10 trades before self-analysis. System will self-improve over time.

### Issue: "Telegram message not sent"

**Solution:** Check Telegram token and chat ID in `.env` and code

---

## 📊 Performance Monitoring

The system automatically saves:
- Execution logs → `C:\trading-memory\obsidian-vault\Workflow-Logs\`
- Analysis reports → `C:\trading-memory\obsidian-vault\Analysis_*`
- Trade backups → `C:\Users\user\Desktop\DS trading agent\backups\`

Monitor these files to track system health.

---

## 🎯 Next Steps

1. **Run Intelligence Hub** - `python intelligence_hub.py`
2. **Test a command** - "Analyze XAUUSD for 30 days"
3. **Run a workflow** - "run daily-report workflow"
4. **Self-improve** - "self-analyze" then approve suggestions
5. **Create custom workflows** - Build your own automated sequences

---

## 📚 API Reference

### NLP Engine Methods

```python
nlp = NLPEngine()
nlp.process_command("Analyze XAUUSD for 30 days")
nlp.classify_intent(text)
nlp.extract_parameters(text)
```

### Workflow Engine Methods

```python
engine = WorkflowEngine()
engine.execute_workflow("workflows/analyze-strategy.md", inputs={...})
engine.execute_step(step, context)
engine.save_execution_log()
```

### Self-Modifier Methods

```python
modifier = SelfModifier()
modifier.analyze_and_suggest('ultimate_trader.py')
modifier.apply_approved_changes([1, 3, 5], 'ultimate_trader.py')
modifier.get_optimization_report()
```

---

## 🔐 Security Notes

- All credentials stored in `.env` (not in code)
- API keys never logged or transmitted
- Backup files created before any modifications
- User approval required for code changes
- All logs saved locally

---

## 📞 Support

For issues or questions:
1. Check logs in `C:\trading-memory\obsidian-vault\`
2. Review this README
3. Check `.env` configuration
4. Verify all dependencies installed: `pip install -r requirements.txt`

---

**Ready to transform your trading with AI-powered intelligence?** 🚀

Start with: `python intelligence_hub.py`
