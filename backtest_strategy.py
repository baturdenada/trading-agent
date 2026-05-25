"""
Strategy Backtester - Previous Day High/Low Breakout
Run: python backtest_strategy.py XAUUSD.s 30
"""

import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
import json
import sys
from datetime import datetime, timedelta

load_dotenv()

def get_candles(symbol, days=30):
    """Fetch historical candles"""
    mt5.initialize(
        path=os.getenv("MT5_PATH"),
        login=int(os.getenv("MT5_LOGIN", 0)),
        password=os.getenv("MT5_PASSWORD"),
        server=os.getenv("MT5_SERVER")
    )
    
    rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days + 5)
    mt5.shutdown()
    
    if rates is None:
        return None
    
    data = []
    for rate in rates[:days]:
        data.append({
            'date': datetime.fromtimestamp(rate[0]).strftime('%Y-%m-%d'),
            'high': rate[2],
            'low': rate[3],
            'close': rate[4]
        })
    return data

def backtest_strategy(data, tp, sl):
    """Run backtest for specific TP/SL"""
    wins = 0
    losses = 0
    total_profit = 0
    
    for i in range(1, len(data)):
        prev_high = data[i-1]['high']
        prev_low = data[i-1]['low']
        today_high = data[i]['high']
        today_low = data[i]['low']
        today_open = data[i]['close']
        
        # Long breakout
        if today_high > prev_high:
            entry = max(today_open, prev_high)
            target = entry + tp
            stop = entry - sl
            
            if today_high >= target:
                wins += 1
                total_profit += tp
            elif today_low <= stop:
                losses += 1
                total_profit -= sl
        
        # Short breakout
        if today_low < prev_low:
            entry = min(today_open, prev_low)
            target = entry - tp
            stop = entry + sl
            
            if today_low <= target:
                wins += 1
                total_profit += tp
            elif today_high >= stop:
                losses += 1
                total_profit -= sl
    
    total_trades = wins + losses
    return {
        'tp': tp,
        'sl': sl,
        'wins': wins,
        'losses': losses,
        'total_trades': total_trades,
        'win_rate': round(wins / total_trades * 100, 1) if total_trades > 0 else 0,
        'net_profit': round(total_profit, 0)
    }

def optimize_parameters(symbol, days=30):
    """Find optimal TP/SL combinations"""
    print(f"📊 Fetching {days} days of {symbol}...")
    data = get_candles(symbol, days)
    
    if not data:
        print("❌ Failed to fetch data")
        return None
    
    print(f"✅ Loaded {len(data)} days")
    print("🔄 Running backtest for all TP/SL combinations...")
    
    tp_values = [100, 200, 300, 400, 500, 600, 800, 1000]
    sl_values = [1000, 1500, 2000, 2500, 3000, 3500, 4000, 5000, 6000]
    
    results = []
    
    for tp in tp_values:
        for sl in sl_values:
            result = backtest_strategy(data, tp, sl)
            if result['total_trades'] > 0:
                results.append(result)
                print(f"  TP:{tp} SL:{sl} -> WR:{result['win_rate']}% Profit:${result['net_profit']}")
    
    # Find best by net profit
    best = max(results, key=lambda x: x['net_profit'])
    
    # Save results
    output = {
        'symbol': symbol,
        'days': days,
        'best': best,
        'all_results': results
    }
    
    with open('C:\\trading-memory\\backtest_results.json', 'w') as f:
        json.dump(output, f, indent=2)
    
    return best

if __name__ == "__main__":
    symbol = sys.argv[1] if len(sys.argv) > 1 else "XAUUSD.s"
    days = int(sys.argv[2]) if len(sys.argv) > 2 else 30
    
    print(f"\n🎯 OPTIMIZING STRATEGY FOR {symbol}\n{'='*50}")
    best = optimize_parameters(symbol, days)
    
    if best:
        print(f"\n{'='*50}")
        print(f"🏆 BEST RESULT:")
        print(f"   Take Profit: {best['tp']} points")
        print(f"   Stop Loss: {best['sl']} points")
        print(f"   Win Rate: {best['win_rate']}%")
        print(f"   Net Profit: ${best['net_profit']}")
        print(f"   Trades: {best['total_trades']} ({best['wins']}W / {best['losses']}L)")
        print(f"{'='*50}")
        
        # Create Obsidian note
        note_path = f"C:\\trading-memory\\obsidian-vault\\Strategy Analysis - {symbol.replace('.s', '')}.md"
        with open(note_path, 'w') as f:
            f.write(f"""# Strategy Analysis: {symbol}

**Date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}
**Period:** Last {days} days

## Optimal Parameters
- **Take Profit:** {best['tp']} points
- **Stop Loss:** {best['sl']} points
- **Win Rate:** {best['win_rate']}%
- **Net Profit:** ${best['net_profit']}
- **Trades:** {best['total_trades']} ({best['wins']} wins / {best['losses']} losses)

## Recommendation
Based on the analysis, the optimal TP/SL combination is **{best['tp']} / {best['sl']}** 
with a win rate of **{best['win_rate']}%** and net profit of **${best['net_profit']}** over {days} days.

---
*Analysis generated by Strategy Backtester*
""")
        print(f"\n💾 Results saved to Obsidian: {note_path}")