"""
NLP ENGINE - Natural Language Processing for Trading Commands
Processes any trading-related command and routes to appropriate action
"""

import logging
import json
import re
from datetime import datetime, timedelta
from openai import OpenAI
import os
from dotenv import load_dotenv
import MetaTrader5 as mt5
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class NLPEngine:
    def __init__(self):
        Config.validate_credentials()
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)
        self.symbols = Config.TRADING_SYMBOLS
        self.init_mt5()
        logger.info("NLP Engine initialized")

    def init_mt5(self):
        """Initialize MetaTrader5 connection"""
        try:
            mt5.initialize(
                path=Config.MT5_PATH,
                login=Config.MT5_LOGIN,
                password=Config.MT5_PASSWORD,
                server=Config.MT5_SERVER
            )
            for s in self.symbols:
                mt5.symbol_select(s, True)
            logger.info("MT5 connected")
        except Exception as e:
            logger.error(f"MT5 init error: {e}")

    def extract_parameters(self, text):
        """Extract trading parameters from natural language"""
        params = {
            'symbols': [],
            'days': 30,
            'indicator': None,
            'tp': None,
            'sl': None,
            'strategy': None,
            'action': None
        }

        # Extract symbols
        for sym in self.symbols:
            symbol_name = sym['name'] if isinstance(sym, dict) else sym
            clean_sym = symbol_name.replace('.s', '')
            if clean_sym.upper() in text.upper():
                params['symbols'].append(symbol_name)

        # Extract days
        days_match = re.search(r'(\d+)\s*(?:days?|d)\b', text, re.IGNORECASE)
        if days_match:
            params['days'] = int(days_match.group(1))

        # Extract TP/SL
        tp_match = re.search(r'tp[\s:]*(\d+)', text, re.IGNORECASE)
        if tp_match:
            params['tp'] = int(tp_match.group(1))

        sl_match = re.search(r'sl[\s:]*(\d+)', text, re.IGNORECASE)
        if sl_match:
            params['sl'] = int(sl_match.group(1))

        # Extract strategy
        strategies = ['breakout', 'rsi', 'ema', 'macd', 'bollinger', 'fibonacci', 'pivot']
        for strat in strategies:
            if strat.lower() in text.lower():
                params['strategy'] = strat
                break

        # Extract indicators
        indicators = ['rsi', 'ema', 'macd', 'atr', 'bollinger', 'stochastic', 'adx']
        for ind in indicators:
            if ind.lower() in text.lower():
                params['indicator'] = ind
                break

        return params

    def classify_intent(self, text):
        """Use AI to classify user intent"""
        prompt = f"""Classify this trading command into ONE of these categories:
ANALYZE - User wants to analyze a symbol/strategy
BACKTEST - User wants to test a strategy with parameters
OPTIMIZE - User wants to find optimal parameters
STATS - User wants performance/trading statistics
RISK - User wants risk analysis
COMPARE - User wants to compare symbols or strategies
REPORT - User wants a report generated
UNKNOWN - Doesn't fit above categories

Command: "{text}"

Respond with ONLY the category name, nothing else."""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=20
            )
            intent = response.choices[0].message.content.strip().upper()
            # Validate
            valid_intents = ['ANALYZE', 'BACKTEST', 'OPTIMIZE', 'STATS', 'RISK', 'COMPARE', 'REPORT', 'UNKNOWN']
            return intent if intent in valid_intents else 'UNKNOWN'
        except Exception as e:
            logger.error(f"Intent classification error: {e}")
            return 'UNKNOWN'

    def handle_analyze(self, params):
        """Handle ANALYZE intent"""
        if not params['symbols']:
            return "❌ Please specify a symbol (XAUUSD, EURUSD, etc.)"

        symbol = params['symbols'][0]
        days = params['days']

        # Get candles
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            if rates is None:
                return f"❌ Failed to get candles for {symbol}"

            # Calculate basic metrics
            closes = [float(r[4]) for r in rates]
            highs = [float(r[2]) for r in rates]
            lows = [float(r[3]) for r in rates]

            current = closes[-1]
            sma20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current
            sma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else current
            high_20 = max(highs[-20:])
            low_20 = min(lows[-20:])

            # Trend analysis
            if sma20 > sma50:
                trend = "UPTREND"
                emoji = "📈"
            elif sma20 < sma50:
                trend = "DOWNTREND"
                emoji = "📉"
            else:
                trend = "SIDEWAYS"
                emoji = "↔️"

            # Distance from levels
            dist_high = ((high_20 - current) / current) * 100
            dist_low = ((current - low_20) / current) * 100

            analysis = f"""{emoji} {symbol} ANALYSIS ({days} days)

📊 Price Data:
• Current: ${current:.2f}
• 20-day High: ${high_20:.2f}
• 20-day Low: ${low_20:.2f}
• Range: ${high_20 - low_20:.2f}

📈 Trend:
• SMA20: ${sma20:.2f}
• SMA50: ${sma50:.2f}
• Status: {trend}

📍 Levels:
• Distance to High: {dist_high:.2f}%
• Distance to Low: {dist_low:.2f}%

Strategy: {params['strategy'] if params['strategy'] else 'Breakout'}
Timeframe: Daily
Data: Last {days} days"""

            return analysis

        except Exception as e:
            return f"❌ Analysis error: {str(e)}"

    def handle_backtest(self, params):
        """Handle BACKTEST intent"""
        if not params['symbols']:
            return "❌ Please specify a symbol to backtest"
        if params['tp'] is None or params['sl'] is None:
            return "❌ Please specify TP (take profit) and SL (stop loss) values"

        symbol = params['symbols'][0]
        tp = params['tp']
        sl = params['sl']
        days = params['days']

        # Simulate backtest
        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            if rates is None:
                return f"❌ Failed to fetch candles"

            wins = 0
            losses = 0
            total_profit = 0

            # Simple breakout strategy backtest
            for i in range(1, len(rates)):
                prev_high = float(rates[i-1][2])
                prev_low = float(rates[i-1][3])
                today_high = float(rates[i][2])
                today_low = float(rates[i][3])

                # Long breakout
                if today_high > prev_high:
                    if today_high >= prev_high + tp:
                        wins += 1
                        total_profit += tp
                    elif today_low <= prev_high - sl:
                        losses += 1
                        total_profit -= sl

                # Short breakout
                if today_low < prev_low:
                    if today_low <= prev_low - tp:
                        wins += 1
                        total_profit += tp
                    elif today_high >= prev_low + sl:
                        losses += 1
                        total_profit -= sl

            total_trades = wins + losses
            win_rate = (wins / total_trades * 100) if total_trades > 0 else 0

            result = f"""🎯 BACKTEST RESULTS

Symbol: {symbol}
Period: {days} days
Strategy: High/Low Breakout
TP: {tp} points
SL: {sl} points

📊 Results:
• Total Trades: {total_trades}
• Wins: {wins} | Losses: {losses}
• Win Rate: {win_rate:.1f}%
• Net Profit: ${total_profit:+.0f}
• Profit Factor: {win_rate/100 * tp / ((100-win_rate)/100 * sl) if losses > 0 else 'N/A'}

{'✅ PROFITABLE' if total_profit > 0 else '❌ NOT PROFITABLE'} | {'GOOD WIN RATE' if win_rate > 55 else 'LOW WIN RATE'}"""

            return result

        except Exception as e:
            return f"❌ Backtest error: {str(e)}"

    def handle_optimize(self, params):
        """Handle OPTIMIZE intent"""
        if not params['symbols']:
            return "❌ Please specify a symbol to optimize"

        symbol = params['symbols'][0]
        days = params['days']

        try:
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            if rates is None:
                return f"❌ Failed to fetch candles"

            # Test common TP/SL combinations
            best_result = {'tp': 100, 'sl': 1000, 'profit': -999999}

            tp_values = [100, 200, 300, 400, 500]
            sl_values = [1000, 1500, 2000, 2500, 3000]

            for tp in tp_values:
                for sl in sl_values:
                    wins, losses, total_profit = 0, 0, 0

                    for i in range(1, len(rates)):
                        prev_high = float(rates[i-1][2])
                        if float(rates[i][2]) > prev_high + tp:
                            wins += 1
                            total_profit += tp
                        elif float(rates[i][3]) < prev_high - sl:
                            losses += 1
                            total_profit -= sl

                    if total_profit > best_result['profit']:
                        best_result = {'tp': tp, 'sl': sl, 'profit': total_profit,
                                     'wins': wins, 'losses': losses}

            result = f"""🔬 OPTIMIZATION RESULTS

Symbol: {symbol}
Period: {days} days
Strategy: High/Low Breakout

🏆 OPTIMAL PARAMETERS:
• Take Profit: {best_result['tp']} points
• Stop Loss: {best_result['sl']} points
• Win Rate: {best_result['wins']/(best_result['wins']+best_result['losses'])*100:.1f}%
• Net Profit: ${best_result['profit']:+.0f}
• Trades: {best_result['wins'] + best_result['losses']} ({best_result['wins']}W/{best_result['losses']}L)

Recommendation: Use TP {best_result['tp']} / SL {best_result['sl']}"""

            return result

        except Exception as e:
            return f"❌ Optimization error: {str(e)}"

    def handle_stats(self, params):
        """Handle STATS intent"""
        try:
            account = mt5.account_info()
            if not account:
                return "❌ Failed to get account info"

            # Get positions
            all_positions = []
            for sym in self.symbols:
                pos = mt5.positions_get(symbol=sym)
                if pos:
                    all_positions.extend(pos)

            total_pnl = sum(p.profit for p in all_positions)

            stats = f"""📊 ACCOUNT STATISTICS

💰 Balance: ${account.balance:.0f}
📈 Equity: ${account.equity:.0f}
💹 PnL: ${total_pnl:+.2f}
📍 Margin: ${account.margin:.0f}
📌 Positions: {len(all_positions)}

Status: {'🟢 Healthy' if account.equity > account.balance * 0.8 else '🔴 At Risk'}"""

            return stats

        except Exception as e:
            return f"❌ Stats error: {str(e)}"

    def handle_risk(self, params):
        """Handle RISK intent"""
        try:
            all_positions = []
            for sym in self.symbols:
                pos = mt5.positions_get(symbol=sym)
                if pos:
                    all_positions.extend(pos)

            account = mt5.account_info()
            if not account:
                return "❌ Failed to get account info"

            total_pnl = sum(p.profit for p in all_positions)
            total_volume = sum(p.volume for p in all_positions)
            risk_pct = (abs(total_pnl) / account.balance * 100) if account.balance > 0 else 0

            risk_level = "🟢 LOW" if risk_pct < 2 else "🟡 MEDIUM" if risk_pct < 5 else "🔴 HIGH"

            risk = f"""⚠️ RISK ANALYSIS

{risk_level} RISK

Current PnL: ${total_pnl:+.2f}
Risk %: {risk_pct:.2f}% of balance
Total Volume: {total_volume:.2f}
Positions: {len(all_positions)}

Max Daily Loss: $100
Current Daily Loss: ${total_pnl:+.2f}

Recommendation: {'Continue trading' if risk_pct < 2 else 'Reduce position size' if risk_pct < 5 else 'Close positions immediately'}"""

            return risk

        except Exception as e:
            return f"❌ Risk error: {str(e)}"

    def process_command(self, text):
        """Main entry point - process any natural language command"""
        logger.info(f"Processing: {text}")

        # Extract parameters
        params = self.extract_parameters(text)

        # Classify intent
        intent = self.classify_intent(text)
        logger.info(f"Intent: {intent}, Params: {params}")

        # Route to handler
        if intent == 'ANALYZE':
            return self.handle_analyze(params)
        elif intent == 'BACKTEST':
            return self.handle_backtest(params)
        elif intent == 'OPTIMIZE':
            return self.handle_optimize(params)
        elif intent == 'STATS':
            return self.handle_stats(params)
        elif intent == 'RISK':
            return self.handle_risk(params)
        else:
            return f"❓ I understood your request as: {intent}\nTry: 'Analyze XAUUSD', 'Backtest EURUSD TP 300 SL 2000', 'Optimize USDJPY', 'Show stats', 'Risk analysis'"

if __name__ == "__main__":
    nlp = NLPEngine()

    # Test commands
    test_commands = [
        "Analyze XAUUSD for the last 30 days",
        "Backtest EURUSD with TP 300 and SL 2000",
        "Optimize XAGUSD parameters",
        "Show me trading stats",
        "What's my risk level?"
    ]

    for cmd in test_commands:
        print(f"\n📝 Command: {cmd}")
        print(f"📤 Response:\n{nlp.process_command(cmd)}")
        print("─" * 60)
