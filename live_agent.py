"""
Multi-Symbol Trading Agent - 24/7 Trading on AWS
Trades: XAUUSD, XAGUSD, EURUSD, USDCAD, USDJPY, USDCHF, USOUSD, SP500, NAS100
Features: Smart entry timing (limit/stop orders), GMT timezone, Weekend planning
"""

import logging
import time
import re
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta, timezone
import json
from openai import OpenAI

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class MultiSymbolAgent:
    def __init__(self):
        # API
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        
        # MT5
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "")
        self.path = os.getenv("MT5_PATH", "")
        
        # All symbols with .s suffix
        self.symbols = [
            {"name": "XAUUSD.s", "type": "gold", "base_risk": 0.02, "pip_value": 0.01, "volatility": 1.5},
            {"name": "XAGUSD.s", "type": "silver", "base_risk": 0.02, "pip_value": 0.01, "volatility": 2.0},
            {"name": "EURUSD.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.5},
            {"name": "USDCAD.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.4},
            {"name": "USDJPY.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.01, "volatility": 0.3},
            {"name": "USDCHF.s", "type": "forex", "base_risk": 0.01, "pip_value": 0.0001, "volatility": 0.35},
            {"name": "USOUSD.s", "type": "oil", "base_risk": 0.02, "pip_value": 0.01, "volatility": 2.5},
            {"name": "SP500.s", "type": "index", "base_risk": 0.015, "pip_value": 0.1, "volatility": 1.0},
            {"name": "NAS100.s", "type": "index", "base_risk": 0.015, "pip_value": 0.1, "volatility": 1.2}
        ]
        
        # Telegram
        self.telegram_token = "8950742927:AAGhHdDZic9CsQCjL7m4zhxLPEY1Q3KcK5E"
        self.telegram_chat_id = "832734789"
        self.last_update_id = 0
        
        # State
        self.active_positions = {}
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.weekly_plan = {}
        self.current_day = None
        self.pending_orders = []
        self.daily_reset()
        
        # Connect MT5
        self.connect_mt5()
        
        # Check if market is open
        self.is_market_open = self.check_market_status()
        
        logger.info("Multi-Symbol Trading Agent initialized")
        
        if not self.is_market_open:
            self.send_weekend_message()
        else:
            self.send("MULTI-SYMBOL AGENT READY\nSmart Entry Trading\n9 symbols | 24/7\nCommands: status, plan, analyze, positions, help")
    
    def check_market_status(self):
        """Check if forex market is open using GMT timezone"""
        now_gmt = datetime.now(timezone.utc)
        weekday = now_gmt.weekday()
        hour = now_gmt.hour
        
        if weekday == 5:
            return False
        elif weekday == 6:
            if hour >= 22:
                return True
            return False
        elif weekday == 4:
            if hour >= 22:
                return False
            return True
        else:
            return True
    
    def daily_reset(self):
        """Reset daily counters based on GMT date"""
        now_gmt = datetime.now(timezone.utc)
        today = now_gmt.strftime('%Y-%m-%d')
        
        if self.current_day == today:
            return
        
        self.current_day = today
        self.daily_pnl = 0
        self.consecutive_losses = 0
        logger.info(f"Daily reset at GMT {now_gmt.strftime('%Y-%m-%d %H:%M:%S')}")
    
    def send_weekend_message(self):
        """Send weekend analysis and trading plan"""
        now_gmt = datetime.now(timezone.utc)
        now_local = datetime.now()
        
        self.generate_weekly_plan()
        
        message = "🏁 MARKET CLOSED (Weekend)\n"
        message += f"🕐 GMT: {now_gmt.strftime('%Y-%m-%d %H:%M:%S')}\n"
        message += f"🕐 Local: {now_local.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        message += "📊 WEEKLY PLAN READY\n"
        message += "Send 'plan' to view\n\n"
        message += f"Market reopens Sunday 22:00 GMT\n"
        message += f"(Your local: Sunday 01:00 AM GMT+3)"
        
        self.send(message)
    
    def generate_weekly_plan(self):
        """Generate trading plan for the upcoming week"""
        self.weekly_plan = {}
        
        for symbol_info in self.symbols:
            symbol = symbol_info['name']
            
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, 5)
            if rates is None or len(rates) < 5:
                continue
            
            closes = [float(r[4]) for r in rates]
            highs = [float(r[2]) for r in rates]
            lows = [float(r[3]) for r in rates]
            
            current_price = closes[-1]
            weekly_change = ((closes[-1] - closes[0]) / closes[0] * 100) if closes[0] != 0 else 0
            weekly_high = max(highs)
            weekly_low = min(lows)
            
            rsi = self.calculate_rsi(closes, period=14)
            resistance = weekly_high
            support = weekly_low
            
            if weekly_change > 0.5:
                trend = "BULLISH"
                plan = f"Buy on pullback to ${support + (weekly_high - weekly_low)*0.3:.2f}"
                confidence = 70
            elif weekly_change < -0.5:
                trend = "BEARISH"
                plan = f"Sell on rally to ${resistance - (weekly_high - weekly_low)*0.3:.2f}"
                confidence = 70
            else:
                trend = "SIDEWAYS"
                plan = f"Wait for breakout above ${resistance:.2f} or below ${support:.2f}"
                confidence = 50
            
            self.weekly_plan[symbol] = {
                'trend': trend,
                'key_level': f"R: {resistance:.2f} | S: {support:.2f}",
                'plan': plan,
                'confidence': confidence,
                'weekly_change': weekly_change,
                'rsi': round(rsi, 1)
            }
            
            time.sleep(0.3)
    
    def connect_mt5(self):
        """Connect to MT5"""
        if not mt5.initialize(path=self.path, login=self.login, password=self.password, server=self.server):
            logger.error(f"MT5 connection failed: {mt5.last_error()}")
            return False
        
        for s in self.symbols:
            mt5.symbol_select(s['name'], True)
        
        logger.info(f"MT5 connected - Account: {mt5.account_info().login}")
        return True
    
    def send(self, msg):
        """Send Telegram message"""
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(url, json={"chat_id": self.telegram_chat_id, "text": msg}, timeout=10)
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    def calculate_lot_size(self, symbol_info, confidence, account_balance):
        """Intelligent lot size calculation"""
        base_risk = symbol_info['base_risk']
        confidence_multiplier = 0.5 + (confidence / 100)
        loss_penalty = max(0.3, 1.0 - (self.consecutive_losses * 0.15))
        risk_pct = min(base_risk * confidence_multiplier * loss_penalty, 0.03)
        
        account_risk = account_balance * risk_pct
        stop_distance = symbol_info['volatility']
        pip_value = symbol_info['pip_value']
        
        lot_size = account_risk / (stop_distance * pip_value * 100000)
        lot_size = round(lot_size, 2)
        
        bounds = {"gold": (0.01, 0.5), "silver": (0.01, 0.5), "forex": (0.01, 1.0), "oil": (0.01, 0.5), "index": (0.01, 0.5)}
        min_lot, max_lot = bounds.get(symbol_info['type'], (0.01, 0.5))
        lot_size = max(min_lot, min(lot_size, max_lot))
        
        return round(lot_size, 2), risk_pct
    
    def calculate_rsi(self, prices, period=14):
        """Calculate RSI"""
        if len(prices) < period + 1:
            return 50
        deltas = [prices[i] - prices[i-1] for i in range(1, len(prices))]
        gains = [d if d > 0 else 0 for d in deltas]
        losses = [-d if d < 0 else 0 for d in deltas]
        avg_gain = sum(gains[:period]) / period
        avg_loss = sum(losses[:period]) / period
        if avg_loss == 0:
            return 100
        rs = avg_gain / avg_loss
        return 100 - (100 / (1 + rs))
    
    def get_signal_for_symbol(self, symbol_info):
        """Get trading signal with entry conditions"""
        symbol = symbol_info['name']
        
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, 100)
        if rates is None or len(rates) < 50:
            return None
        
        closes = [float(r[4]) for r in rates]
        highs = [float(r[2]) for r in rates]
        lows = [float(r[3]) for r in rates]
        current_price = closes[-1]
        
        # Calculate key levels
        resistance = max(highs[-20:])
        support = min(lows[-20:])
        pivot = (resistance + support) / 2
        
        rsi = self.calculate_rsi(closes)
        ema20 = sum(closes[-20:]) / 20 if len(closes) >= 20 else current_price
        ema50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else current_price
        momentum = ((closes[-1] - closes[-5]) / closes[-5] * 100) if len(closes) >= 5 else 0
        
        dist_to_resistance = ((resistance - current_price) / current_price) * 100
        dist_to_support = ((current_price - support) / current_price) * 100
        
        positions = mt5.positions_get(symbol=symbol)
        has_position = len(positions) > 0 if positions else False
        
        prompt = f"""Symbol: {symbol}
Current Price: {current_price:.4f}
RSI: {rsi:.1f}
EMA20: {ema20:.4f}
EMA50: {ema50:.4f}
Momentum: {momentum:+.2f}%

Key Levels:
Resistance: {resistance:.4f}
Support: {support:.4f}
Pivot: {pivot:.4f}
Dist to Resistance: {dist_to_resistance:.2f}%
Dist to Support: {dist_to_support:.2f}%

Has open position: {has_position}

Output JSON with entry strategy:
{{
    "action": "BUY/SELL/HOLD",
    "confidence": 0-100,
    "entry_type": "MARKET/LIMIT/STOP",
    "entry_price": 0,
    "stop_loss": 0,
    "take_profit": 0,
    "reasoning": "entry strategy explanation"
}}

Entry Strategy Rules:
- If near support and RSI < 40: LIMIT BUY at support
- If near resistance and RSI > 60: LIMIT SELL at resistance
- If strong breakout: STOP order
- Otherwise HOLD or MARKET only if confidence > 75"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
                max_tokens=300
            )
            
            content = response.choices[0].message.content.strip()
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                content = json_match.group(0)
            
            result = json.loads(content)
            
            result.setdefault('action', 'HOLD')
            result.setdefault('confidence', 0)
            result.setdefault('entry_type', 'MARKET')
            result.setdefault('entry_price', current_price)
            result.setdefault('stop_loss', 0)
            result.setdefault('take_profit', 0)
            result.setdefault('reasoning', 'Analysis')
            
            if result['action'] not in ['BUY', 'SELL', 'HOLD']:
                result['action'] = 'HOLD'
            result['confidence'] = max(0, min(100, result['confidence']))
            
            return result
        except Exception as e:
            logger.error(f"Signal error for {symbol}: {e}")
            return {'action': 'HOLD', 'confidence': 0, 'entry_type': 'MARKET', 'reasoning': str(e)}
    
    def place_limit_order(self, symbol_info, signal, price, sl, tp, lot):
        """Place a limit order (wait for price to reach entry)"""
        symbol = symbol_info['name']
        
        order_type = mt5.ORDER_TYPE_BUY_LIMIT if signal['action'] == 'BUY' else mt5.ORDER_TYPE_SELL_LIMIT
        
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 987654,
            "comment": f"AI_LIMIT_{signal['action']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.send(f"📌 LIMIT {signal['action']} {lot} {symbol}\nEntry: ${price:.3f}\nSL: ${sl:.3f} | TP: ${tp:.3f}\n{signal['reasoning'][:80]}")
            return True
        else:
            error = result.comment if result is not None else 'Order send failed'
            logger.error(f"Limit order failed: {error}")
            return False
    
    def place_stop_order(self, symbol_info, signal, price, sl, tp, lot):
        """Place a stop order (trigger on breakout)"""
        symbol = symbol_info['name']
        
        order_type = mt5.ORDER_TYPE_BUY_STOP if signal['action'] == 'BUY' else mt5.ORDER_TYPE_SELL_STOP
        
        request = {
            "action": mt5.TRADE_ACTION_PENDING,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 987654,
            "comment": f"AI_STOP_{signal['action']}",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.send(f"📊 STOP {signal['action']} {lot} {symbol}\nTrigger: ${price:.3f}\nSL: ${sl:.3f} | TP: ${tp:.3f}\n{signal['reasoning'][:80]}")
            return True
        else:
            error = result.comment if result is not None else 'Order send failed'
            logger.error(f"Stop order failed: {error}")
            return False
    
    def place_market_order(self, symbol_info, signal, price, sl, tp, lot):
        """Execute immediate market order"""
        symbol = symbol_info['name']
        
        order_type = mt5.ORDER_TYPE_BUY if signal['action'] == 'BUY' else mt5.ORDER_TYPE_SELL
        
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": sl,
            "tp": tp,
            "deviation": 20,
            "magic": 987654,
            "comment": f"AI_MARKET_{signal['action']}",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
        
        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            self.send(f"⚡ MARKET {signal['action']} {lot} {symbol}\nPrice: ${price:.3f}\nSL: ${sl:.3f} | TP: ${tp:.3f}\n{signal['reasoning'][:80]}")
            return True
        else:
            error = result.comment if result is not None else 'Order send failed'
            logger.error(f"Market order failed: {error}")
            return False
    
    def execute_trade(self, symbol_info, signal):
        """Execute trade based on entry type"""
        if not self.is_market_open:
            self.send(f"⚠️ Market closed. {symbol_info['name']} signal queued.")
            return False
        
        account = mt5.account_info()
        if not account:
            return False
        
        lot, risk_pct = self.calculate_lot_size(symbol_info, signal['confidence'], account.balance)
        symbol = symbol_info['name']
        tick = mt5.symbol_info_tick(symbol)
        
        if not tick:
            return False
        
        # Use signal's prices or calculate defaults
        entry_price = signal.get('entry_price', 0)
        sl_price = signal.get('stop_loss', 0)
        tp_price = signal.get('take_profit', 0)
        
        # Calculate defaults if not provided
        if sl_price == 0:
            sl_distance = symbol_info['volatility'] * 30
            if signal['action'] == 'BUY':
                sl_price = entry_price - (sl_distance * symbol_info['pip_value'])
            else:
                sl_price = entry_price + (sl_distance * symbol_info['pip_value'])
        
        if tp_price == 0:
            tp_distance = symbol_info['volatility'] * 60
            if signal['action'] == 'BUY':
                tp_price = entry_price + (tp_distance * symbol_info['pip_value'])
            else:
                tp_price = entry_price - (tp_distance * symbol_info['pip_value'])
        
        entry_type = signal.get('entry_type', 'MARKET')
        
        if entry_type == 'LIMIT':
            return self.place_limit_order(symbol_info, signal, entry_price, sl_price, tp_price, lot)
        elif entry_type == 'STOP':
            return self.place_stop_order(symbol_info, signal, entry_price, sl_price, tp_price, lot)
        else:
            return self.place_market_order(symbol_info, signal, tick.ask if signal['action'] == 'BUY' else tick.bid, sl_price, tp_price, lot)
    
    def get_updates(self):
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/getUpdates"
            params = {"offset": self.last_update_id + 1, "timeout": 3}
            response = requests.get(url, params=params, timeout=10)
            data = response.json()
            if data.get("ok") and data.get("result"):
                for update in data["result"]:
                    self.last_update_id = update["update_id"]
                    if "message" in update and "text" in update["message"]:
                        msg = update["message"]["text"]
                        self.process_command(msg)
            return True
        except:
            return True
    
    def process_command(self, msg):
        msg_lower = msg.lower()
        
        if msg_lower == "status":
            self.cmd_status()
        elif msg_lower == "positions":
            self.cmd_positions()
        elif msg_lower in ["analyze", "signal"]:
            self.cmd_signal()
        elif msg_lower == "plan":
            self.cmd_plan()
        elif msg_lower == "help":
            self.cmd_help()
        else:
            self.send(f"Commands: status, positions, analyze, plan, help")
    
    def cmd_status(self):
        account = mt5.account_info()
        if not account:
            self.send("MT5 not connected")
            return
        
        now_gmt = datetime.now(timezone.utc)
        now_local = datetime.now()
        
        market_status = "OPEN" if self.is_market_open else "CLOSED"
        total_pnl = 0
        total_positions = 0
        for s in self.symbols:
            positions = mt5.positions_get(symbol=s['name'])
            if positions:
                total_positions += len(positions)
                total_pnl += sum(p.profit for p in positions)
        
        self.send(f"📊 STATUS\n"
                  f"🕐 GMT: {now_gmt.strftime('%H:%M:%S')} | Local: {now_local.strftime('%H:%M:%S')}\n"
                  f"Market: {market_status}\n"
                  f"Balance: ${account.balance:.2f}\n"
                  f"Equity: ${account.equity:.2f}\n"
                  f"Positions: {total_positions}\n"
                  f"PnL: ${total_pnl:+.2f}")
    
    def cmd_positions(self):
        found = False
        for s in self.symbols:
            positions = mt5.positions_get(symbol=s['name'])
            if positions:
                found = True
                for p in positions:
                    self.send(f"{s['name']}: {'BUY' if p.type==0 else 'SELL'} {p.volume} | PnL: ${p.profit:+.2f}")
        
        if not found:
            self.send("No open positions")
    
    def cmd_signal(self):
        if not self.is_market_open:
            self.send("📊 Market closed. Send 'plan' for weekly analysis.")
            return
        
        self.send("🤖 Analyzing all symbols...")
        for s in self.symbols:
            signal = self.get_signal_for_symbol(s)
            if signal and signal.get('action') != 'HOLD':
                self.send(f"{s['name']}: {signal['action']} ({signal['entry_type']}) | {signal['confidence']}%\n{signal['reasoning'][:80]}")
            time.sleep(2)
        self.send("Analysis complete")
    
    def cmd_plan(self):
        if not self.weekly_plan:
            self.send("Generating plan...")
            self.generate_weekly_plan()
        
        message = "📊 WEEKLY TRADING PLAN\n━━━━━━━━━━━━━━━━\n\n"
        
        for symbol, plan in list(self.weekly_plan.items())[:4]:
            message += f"📈 {symbol}\n"
            message += f"   Trend: {plan.get('trend', 'N/A')}\n"
            message += f"   Plan: {plan.get('plan', 'N/A')}\n"
            message += f"   Confidence: {plan.get('confidence', 0)}%\n\n"
        
        message += f"Market reopens Sunday 22:00 GMT"
        self.send(message)
    
    def cmd_help(self):
        help_text = """MULTI-SYMBOL AGENT - Smart Entry Trading

SYMBOLS: XAUUSD, XAGUSD, EURUSD, USDCAD, USDJPY, USDCHF, USOUSD, SP500, NAS100

COMMANDS:
status - Balance, PnL, market status
positions - Open trades
analyze - Trading signals
plan - Weekly trading plan
help - This menu

ENTRY TYPES:
• MARKET - Execute immediately
• LIMIT - Wait for pullback to level
• STOP - Trigger on breakout

Market hours: Sunday 22:00 GMT to Friday 22:00 GMT"""
        self.send(help_text)
    
    def scan_and_trade(self):
        """Main trading loop - only when market is open"""
        if not self.is_market_open:
            return
        
        account = mt5.account_info()
        if not account:
            return
        
        self.daily_reset()
        
        for symbol_info in self.symbols:
            # Check existing positions and pending orders
            positions = mt5.positions_get(symbol=symbol_info['name'])
            orders = mt5.orders_get(symbol=symbol_info['name'])
            
            if positions or orders:
                continue
            
            signal = self.get_signal_for_symbol(symbol_info)
            
            if signal and signal.get('action') != 'HOLD' and signal.get('confidence', 0) > 65:
                self.execute_trade(symbol_info, signal)
                time.sleep(5)
    
    def run(self):
        """Main loop"""
        self.send("MULTI-SYMBOL AGENT ONLINE\nSmart Entry Trading\nCommands: status, plan, analyze, help")
        logger.info("Multi-symbol agent running on AWS")
        
        try:
            while True:
                self.is_market_open = self.check_market_status()
                self.daily_reset()
                
                if not self.is_market_open and not self.weekly_plan:
                    self.generate_weekly_plan()
                    self.send_weekend_message()
                
                self.get_updates()
                self.scan_and_trade()
                time.sleep(60)
        except KeyboardInterrupt:
            self.send("Agent stopped")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    agent = MultiSymbolAgent()
    agent.run()