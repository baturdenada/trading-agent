---
name: analyze-strategy
description: Analyze a trading strategy with backtest and optimization
trigger: manual
inputs:
  - symbol: XAUUSD.s
  - days: 30
  - tp: 400
  - sl: 6000
---

# Analyze Trading Strategy

## Step 1: Fetch Historical Data
- action: get_candles
- symbol: {{symbol}}
- days: {{days}}
- output: candle_data

## Step 2: Run Backtest
- action: python_script
- script: backtest_strategy.py
- symbol: {{symbol}}
- days: {{days}}
- tp: {{tp}}
- sl: {{sl}}
- output: backtest_results

## Step 3: Generate AI Analysis
- action: ai_summary
- input: {{backtest_results}}
- prompt: "Analyze these backtest results. Is this a good strategy? Should we use it? Provide specific recommendations based on win rate and profit."
- output: ai_analysis

## Step 4: Create Report
- action: write_file
- path: C:\trading-memory\obsidian-vault\Analysis_{{date}}.md
- content: |
  # Strategy Analysis - {{symbol}}
  **Date:** {{date}} {{time}}
  **Period:** {{days}} days
  
  ## Backtest Results
  {{backtest_results}}
  
  ## AI Analysis
  {{ai_analysis}}
  
  ## Action Items
  - Review the analysis above
  - Decide if strategy should be deployed
  - If approved, run live on demo account first

## Step 5: Send Telegram Notification
- action: telegram_send
- message: |
  ✅ Analysis Complete: {{symbol}}
  
  TP: {{tp}} | SL: {{sl}}
  Period: {{days}} days
  
  📊 Results saved to Obsidian
  Check the full analysis for details
