"""
ULTIMATE TRADING AGENT - Professional Grade
Dynamic management, adaptive strategies, self-learning
Telegram bot with natural language forwarding to Claude
"""

import logging
import time
import json
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta, timezone
from openai import OpenAI
import numpy as np
from mt5_manager import get_mt5_manager
from api_helper import send_telegram_reliable, call_deepseek_reliable
from risk_manager import RiskManager
from config import Config
from state_manager import StateManager
from trade_historian import TradeHistorian
from regime_detector import RegimeDetector
from position_optimizer import PositionOptimizer

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class UltimateTrader:
    def __init__(self):
        # Load configuration
        self.config = Config

        # API
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)

        # MT5 Manager (singleton with resilience)
        self.mt5_manager = get_mt5_manager(
            path=Config.MT5_PATH,
            login=Config.MT5_LOGIN,
            password=Config.MT5_PASSWORD,
            server=Config.MT5_SERVER
        )

        # MT5 (for backwards compatibility)
        self.login = Config.MT5_LOGIN
        self.password = Config.MT5_PASSWORD
        self.server = Config.MT5_SERVER
        self.path = Config.MT5_PATH

        # Symbols from config
        self.symbols = Config.TRADING_SYMBOLS

        # Telegram
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID

        # Validate credentials
        try:
            Config.validate_credentials()
        except ValueError as e:
            logger.error(f"Credential validation failed: {e}")
            raise
        self.last_update_id = 0
        
        # State
        self.positions = {}
        self.daily_pnl = 0
        self.consecutive_losses = 0
        self.market_regime = "UNKNOWN"
        self.learning_memory = self.load_learning_memory()
        
        # Risk limits (legacy - now handled by RiskManager)
        self.max_positions = 5
        self.max_correlated = 2
        self.trailing_activation = 1.5
        self.trailing_distance = 0.5

        # Claude webhook (your local PC)
        self.claude_webhook = "http://YOUR_LOCAL_PC_IP:5002/webhook"  # Replace with your IP or ngrok URL

        # Initialize learning & adaptation systems
        self.historian = TradeHistorian()
        self.regime_detector = RegimeDetector()
        self.position_optimizer = PositionOptimizer(
            historian=self.historian,
            regime_detector=self.regime_detector
        )

        # Connect
        self.connect_mt5()
        self.is_market_open = self.check_market_status()

        # Initialize Risk Manager with professional limits
        try:
            account = mt5.account_info()
            if account:
                self.risk_manager = RiskManager(
                    initial_balance=account.balance,
                    daily_loss_limit_pct=0.05,      # 5% daily loss limit
                    weekly_loss_limit_pct=0.10,     # 10% weekly loss limit
                    max_position_size_pct=0.10,     # 10% max position
                    max_risk_per_trade_pct=0.02,    # 2% max risk per trade
                    max_concurrent_positions=5
                )
                logger.info(f"Risk Manager initialized with balance: {account.balance:.2f}")
            else:
                logger.error("Could not get account info for Risk Manager")
                self.risk_manager = None
        except Exception as e:
            logger.error(f"Risk Manager initialization failed: {e}")
            self.risk_manager = None

        logger.info("ULTIMATE TRADER INITIALIZED")
        self.send("🔥 ULTIMATE TRADER ONLINE\nProfessional trading brain active\nDynamic management | Trailing stops | Self-learning | Risk Management\nCommands: status, positions, risk, help")
    
    def send(self, msg):
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)
    
    def forward_to_claude(self, user_message):
        """Forward unknown commands to Claude Code on local PC"""
        try:
            response = requests.post(self.claude_webhook, json={
                'message': user_message,
                'chat_id': self.telegram_chat_id
            }, timeout=30)
            result = response.json()
            return result.get('response', 'Processing complete.')
        except requests.exceptions.ConnectionError:
            return "Claude Code not reachable. Make sure claude_webhook.py is running on your local PC.\n\nAvailable commands: status, positions, risk, help"
        except Exception as e:
            return f"Error: {e}\n\nAvailable commands: status, positions, risk, help"
    
    def connect_mt5(self):
        # Use resilient MT5 manager with exponential backoff
        if not self.mt5_manager.connect():
            logger.error("MT5 connection failed after retries")
            return False

        # Select all symbols
        try:
            for s in self.symbols:
                mt5.symbol_select(s['name'], True)
            logger.info("MT5 symbols selected")
        except Exception as e:
            logger.error(f"Error selecting MT5 symbols: {e}")
            return False

        logger.info("MT5 connected and ready")
        return True
    
    def check_market_status(self):
        now_gmt = datetime.now(timezone.utc)
        weekday = now_gmt.weekday()
        hour = now_gmt.hour
        if weekday == 5 or weekday == 6:
            return False
        if weekday == 4 and hour >= 22:
            return False
        if weekday == 6 and hour < 22:
            return False
        return True
    
    def load_learning_memory(self):
        try:
            learnings_path = Config.FILE_PATHS["learnings"]
            with open(learnings_path, "r") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.info("Learning memory file not found, creating new")
            return {"winning_patterns": [], "losing_patterns": [], "adjustments": []}
        except json.JSONDecodeError as e:
            logger.error(f"Corrupted learning memory: {e}, resetting")
            return {"winning_patterns": [], "losing_patterns": [], "adjustments": []}
        except Exception as e:
            logger.error(f"Error loading learning memory: {e}")
            return {"winning_patterns": [], "losing_patterns": [], "adjustments": []}

    def save_learning_memory(self):
        try:
            learnings_path = Config.FILE_PATHS["learnings"]
            learnings_path.parent.mkdir(parents=True, exist_ok=True)
            with open(learnings_path, "w") as f:
                json.dump(self.learning_memory, f, indent=2)
        except IOError as e:
            logger.error(f"Failed to save learning memory: {e}")
        except Exception as e:
            logger.error(f"Unexpected error saving learning memory: {e}")
    
    def calculate_indicators(self, symbol, timeframe=mt5.TIMEFRAME_M15):
        rates = mt5.copy_rates_from_pos(symbol, timeframe, 0, 100)
        if rates is None or len(rates) < 50:
            return None
        
        closes = [float(r[4]) for r in rates]
        highs = [float(r[2]) for r in rates]
        lows = [float(r[3]) for r in rates]
        current = closes[-1]
        
        rsi = self.calculate_rsi(closes)
        ema9 = sum(closes[-9:]) / 9
        ema20 = sum(closes[-20:]) / 20
        ema50 = sum(closes[-50:]) / 50
        ema200 = sum(closes[-200:]) / 200 if len(closes) >= 200 else ema50
        atr = self.calculate_atr(symbol)
        recent_high = max(highs[-20:])
        recent_low = min(lows[-20:])
        pivot = (recent_high + recent_low) / 2
        momentum_1h = ((closes[-1] - closes[-12]) / closes[-12] * 100) if len(closes) >= 12 else 0
        momentum_4h = ((closes[-1] - closes[-48]) / closes[-48] * 100) if len(closes) >= 48 else 0
        
        if ema9 > ema20 > ema50 and closes[-1] > ema9:
            trend = "STRONG_UP"
        elif ema9 < ema20 < ema50 and closes[-1] < ema9:
            trend = "STRONG_DOWN"
        elif ema9 > ema20:
            trend = "WEAK_UP"
        elif ema9 < ema20:
            trend = "WEAK_DOWN"
        else:
            trend = "SIDEWAYS"
        
        if atr > 1.5 * self.calculate_atr(symbol, 50):
            volatility = "HIGH"
        elif atr < 0.5 * self.calculate_atr(symbol, 50):
            volatility = "LOW"
        else:
            volatility = "NORMAL"
        
        return {
            "price": current, "rsi": rsi, "ema9": ema9, "ema20": ema20, "ema50": ema50,
            "ema200": ema200, "atr": atr, "resistance": recent_high, "support": recent_low,
            "pivot": pivot, "trend": trend, "volatility": volatility,
            "momentum_1h": momentum_1h, "momentum_4h": momentum_4h
        }
    
    def calculate_rsi(self, prices, period=14):
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
    
    def calculate_atr(self, symbol, period=14):
        rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_M15, 0, period + 5)
        if rates is None or len(rates) < period:
            return 0.15
        true_ranges = []
        for i in range(1, min(len(rates), period + 5)):
            high = float(rates[i][2])
            low = float(rates[i][3])
            prev_close = float(rates[i-1][4])
            tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
            true_ranges.append(tr)
        if len(true_ranges) < period:
            return 0.15
        return sum(true_ranges[-period:]) / period
    
    def calculate_lot_size(self, symbol_info, confidence, account_balance, atr):
        # Use RiskManager for professional position sizing with hard caps
        if self.risk_manager:
            position_size, risk_pct = self.risk_manager.calculate_position_size(
                balance=account_balance,
                risk_percentage=symbol_info['base_risk'],
                atr=atr,
                pip_value=symbol_info['pip_value'],
                confidence=confidence
            )
            # Convert position size to lot size
            lot_size = position_size / (atr * 1.5 * symbol_info['pip_value'] * 100000)
            lot_size = max(0.01, min(lot_size, 0.5))
            return round(lot_size, 2), risk_pct
        else:
            # Fallback to legacy calculation if RiskManager unavailable
            base_risk = symbol_info['base_risk']
            confidence_multiplier = 0.5 + (confidence / 100)
            loss_penalty = max(0.3, 1.0 - (self.consecutive_losses * 0.15))
            vol_adjustment = 1.0
            if atr > 2.0:
                vol_adjustment = 0.5
            elif atr > 1.5:
                vol_adjustment = 0.7
            risk_pct = min(base_risk * confidence_multiplier * loss_penalty * vol_adjustment, 0.03)
            account_risk = account_balance * risk_pct
            lot_size = account_risk / (atr * 1.5 * symbol_info['pip_value'] * 100000)
            lot_size = max(0.01, min(lot_size, 0.5))
            return round(lot_size, 2), risk_pct
    
    def get_ai_decision(self, symbol_info, indicators, account, has_position):
        prompt = f"""Professional trading analysis for {symbol_info['name']}:

PRICE: ${indicators['price']:.4f}
TREND: {indicators['trend']}
RSI: {indicators['rsi']:.1f}
ATR: {indicators['atr']:.4f}
VOLATILITY: {indicators['volatility']}
MOMENTUM 1H: {indicators['momentum_1h']:+.2f}%
MOMENTUM 4H: {indicators['momentum_4h']:+.2f}%

KEY LEVELS:
Resistance: ${indicators['resistance']:.4f}
Support: ${indicators['support']:.4f}
Pivot: ${indicators['pivot']:.4f}

ACCOUNT: Balance ${account.balance:.0f} | Equity ${account.equity:.0f}
OPEN POSITION: {'YES' if has_position else 'NO'}

Output JSON:
{{"action":"BUY/SELL/HOLD","confidence":0-100,"entry_type":"MARKET/LIMIT","entry_price":0,"stop_loss":0,"take_profit":0,"trailing_activate":0,"reasoning":"analysis"}}

Only BUY/SELL if confidence > 60."""
        
        try:
            # Use resilient DeepSeek call with retry logic
            content = call_deepseek_reliable(
                self.client,
                prompt,
                fallback='{"action":"HOLD","confidence":0,"reasoning":"AI unavailable"}'
            )

            if content:
                import re
                json_match = re.search(r'\{.*\}', content, re.DOTALL)
                if json_match:
                    return json.loads(json_match.group(0))
        except Exception as e:
            logger.error(f"AI decision error: {e}")

        return {"action": "HOLD", "confidence": 0, "reasoning": "AI error - holding position"}
    
    def manage_position(self, position, symbol_info):
        tick = mt5.symbol_info_tick(symbol_info['name'])
        if not tick:
            return
        
        current_price = tick.ask if position.type == 0 else tick.bid
        entry = position.price_open
        pnl = position.profit
        pnl_pips = (current_price - entry) / symbol_info['pip_value'] if position.type == 0 else (entry - current_price) / symbol_info['pip_value']
        atr = self.calculate_atr(symbol_info['name'])
        risk_in_pips = abs(entry - position.sl) / symbol_info['pip_value'] if position.sl else 50
        
        if pnl_pips > risk_in_pips * self.trailing_activation:
            new_sl = current_price - (self.trailing_distance * risk_in_pips * symbol_info['pip_value']) if position.type == 0 else current_price + (self.trailing_distance * risk_in_pips * symbol_info['pip_value'])
            if (position.type == 0 and new_sl > position.sl) or (position.type == 1 and new_sl < position.sl):
                self.modify_sl(position.ticket, new_sl)
                logger.info(f"Trailing stop updated for {symbol_info['name']} to ${new_sl:.3f}")
        
        indicators = self.calculate_indicators(symbol_info['name'])
        if indicators:
            if position.type == 0 and indicators['rsi'] > 85:
                self.close_position(position.ticket, "RSI overbought - taking profit")
            elif position.type == 1 and indicators['rsi'] < 15:
                self.close_position(position.ticket, "RSI oversold - taking profit")
            if position.type == 0 and indicators['trend'] in ["STRONG_DOWN", "WEAK_DOWN"]:
                self.close_position(position.ticket, "Trend reversed - cutting loss")
            elif position.type == 1 and indicators['trend'] in ["STRONG_UP", "WEAK_UP"]:
                self.close_position(position.ticket, "Trend reversed - cutting loss")
    
    def modify_sl(self, ticket, new_sl):
        request = {"action": mt5.TRADE_ACTION_SLTP, "position": ticket, "sl": round(new_sl, 5)}
        mt5.order_send(request)
    
    def close_position(self, ticket, reason):
        pos = mt5.positions_get(ticket=ticket)
        if not pos:
            return
        pos = pos[0]

        # Get current price for exit
        tick = mt5.symbol_info_tick(pos.symbol)
        exit_price = tick.bid if pos.type == 0 else tick.ask

        order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY
        request = {
            "action": mt5.TRADE_ACTION_DEAL, "symbol": pos.symbol, "volume": pos.volume,
            "type": order_type, "position": ticket, "deviation": 20,
            "comment": f"AI_Close: {reason[:50]}", "type_filling": mt5.ORDER_FILLING_IOC,
        }
        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            # Log trade to historian for learning
            try:
                win = pos.profit > 0
                self.historian.log_trade(
                    symbol=pos.symbol,
                    entry_price=pos.price_open,
                    exit_price=exit_price,
                    entry_time=datetime.fromtimestamp(pos.time).isoformat(),
                    exit_time=datetime.now().isoformat(),
                    profit=pos.profit,
                    setup_type="MANUAL_CLOSE",  # Or extract from reason
                    rsi_value=0,  # Would need to calculate
                    trend="UNKNOWN",  # Would need indicators
                    confidence=0,
                    win=win
                )
            except Exception as e:
                logger.warning(f"Could not log trade to historian: {e}")

            self.send(f"🔒 CLOSED {pos.symbol} | Reason: {reason}")
    
    def check_portfolio_risk(self):
        """Check all risk limits and enforce them. Returns True if new trades allowed."""
        if not self.risk_manager:
            logger.warning("Risk Manager not available, skipping risk checks")
            return True

        try:
            account = mt5.account_info()
            if not account:
                logger.error("Could not get account info for risk check")
                return False

            # Get all open positions
            all_positions = []
            for s in self.symbols:
                positions = mt5.positions_get(symbol=s['name'])
                if positions:
                    all_positions.extend(positions)

            # Check daily loss limit
            daily_loss_exceeded, daily_reason = self.risk_manager.check_daily_loss_limit(
                account.balance, account.equity
            )
            if daily_loss_exceeded:
                self.send(f"🚨 DAILY LOSS LIMIT HIT: {daily_reason}")
                self.close_all_positions("Daily loss limit exceeded - emergency exit")
                self.risk_manager.suspend_trading(daily_reason)
                return False

            # Check weekly loss limit
            weekly_loss_exceeded, weekly_reason = self.risk_manager.check_weekly_loss_limit(
                account.balance
            )
            if weekly_loss_exceeded:
                self.send(f"🚨 WEEKLY LOSS LIMIT HIT: {weekly_reason}")
                self.close_all_positions("Weekly loss limit exceeded - emergency exit")
                self.risk_manager.trigger_emergency_shutdown(weekly_reason)
                return False

            # Check max concurrent positions
            max_pos_exceeded, max_pos_reason = self.risk_manager.check_max_positions(len(all_positions))
            if max_pos_exceeded:
                logger.warning(max_pos_reason)
                return False

            # Check correlation risk
            positions_dict = [{'symbol': p.symbol} for p in all_positions]
            corr_exceeded, corr_reason = self.risk_manager.check_correlation_risk(
                positions_dict, self.max_correlated
            )
            if corr_exceeded:
                logger.warning(corr_reason)
                return False

            # Check if trading is allowed
            trading_allowed, reason = self.risk_manager.is_trading_allowed()
            if not trading_allowed:
                logger.error(f"Trading not allowed: {reason}")
                return False

            return True

        except Exception as e:
            logger.error(f"Error in risk check: {e}")
            return False

    def close_all_positions(self, reason: str):
        """Emergency: Close ALL open positions"""
        logger.critical(f"CLOSING ALL POSITIONS: {reason}")
        self.send(f"🛑 EMERGENCY: Closing all positions - {reason}")

        try:
            all_positions = []
            for s in self.symbols:
                positions = mt5.positions_get(symbol=s['name'])
                if positions:
                    all_positions.extend(positions)

            closed_count = 0
            for pos in all_positions:
                try:
                    self.close_position(pos.ticket, f"EMERGENCY EXIT: {reason}")
                    closed_count += 1
                except Exception as e:
                    logger.error(f"Failed to close position {pos.ticket}: {e}")

            logger.critical(f"Closed {closed_count}/{len(all_positions)} positions")
            self.send(f"✓ Closed {closed_count} positions")

        except Exception as e:
            logger.error(f"Error closing all positions: {e}")
            self.send(f"❌ ERROR closing positions: {e}")
    
    def get_updates(self):
        """DISABLED - Intelligence Hub handles Telegram routing"""
        return True
    
    def process_command(self, msg):
        msg_lower = msg.lower().strip()
        
        # Known commands
        if msg_lower == "status":
            self.cmd_status()
        elif msg_lower == "positions":
            self.cmd_positions()
        elif msg_lower == "risk":
            self.cmd_risk()
        elif msg_lower == "help":
            self.cmd_help()
        else:
            # Forward unknown messages to Claude on local PC
            result = self.forward_to_claude(msg)
            self.send(result)
    
    def cmd_status(self):
        account = mt5.account_info()
        positions = []
        for s in self.symbols:
            pos = mt5.positions_get(symbol=s['name'])
            if pos:
                positions.extend(pos)
        total_pnl = sum(p.profit for p in positions)
        self.send(f"🔥 ULTIMATE TRADER\nMarket: {'OPEN' if self.is_market_open else 'CLOSED'}\nBalance: ${account.balance:.0f}\nPositions: {len(positions)}\nPnL: ${total_pnl:+.2f}\nRegime: {self.market_regime}")
    
    def cmd_positions(self):
        for s in self.symbols:
            pos = mt5.positions_get(symbol=s['name'])
            if pos:
                for p in pos:
                    self.send(f"{s['name']}: {'BUY' if p.type==0 else 'SELL'} {p.volume} | PnL: ${p.profit:+.2f}")
    
    def cmd_risk(self):
        positions = []
        for s in self.symbols:
            pos = mt5.positions_get(symbol=s['name'])
            if pos:
                positions.extend(pos)
        total_pnl = sum(p.profit for p in positions)
        self.send(f"📊 RISK STATUS\nMax Positions: {self.max_positions}\nCurrent: {len(positions)}\nDaily Loss Limit: ${self.daily_loss_limit}\nCurrent PnL: ${total_pnl:+.2f}\nTrailing: {self.trailing_activation}x risk")
    
    def cmd_help(self):
        self.send("🔥 ULTIMATE TRADER\n\nFEATURES:\n• Dynamic SL/TP modification\n• Trailing stop loss\n• Early exit on reversal\n• Portfolio risk management\n• Multi-timeframe analysis\n• Self-learning from trade history\n• Market regime adaptation\n• Position optimization\n\nCOMMANDS:\nstatus, positions, risk, help\n\nOr just type anything else and Claude will process it!")

    def _extract_setup_type(self, reasoning_text):
        """Extract setup type from AI reasoning for learning"""
        text = reasoning_text.lower()
        if 'rsi' in text and ('extreme' in text or 'overbought' in text or 'oversold' in text):
            return 'RSI_EXTREME'
        elif 'trend' in text and 'reversal' in text:
            return 'TREND_REVERSAL'
        elif 'momentum' in text or 'breakout' in text:
            return 'MOMENTUM_BREAKOUT'
        elif 'pivot' in text or 'support' in text or 'resistance' in text:
            return 'LEVEL_BOUNCE'
        else:
            return 'GENERAL_SIGNAL'
    
    def scan_and_trade(self):
        if not self.is_market_open:
            return
        account = mt5.account_info()
        if not account:
            return
        if not self.check_portfolio_risk():
            return

        # Get all open positions for scoring and optimization
        all_positions = self.position_optimizer.evaluate_all_positions(self.symbols, account)

        for symbol_info in self.symbols:
            positions = mt5.positions_get(symbol=symbol_info['name'])
            if positions:
                for pos in positions:
                    self.manage_position(pos, symbol_info)
                continue

            indicators = self.calculate_indicators(symbol_info['name'])
            if not indicators:
                continue

            # Detect market regime for this symbol
            rates = mt5.copy_rates_from_pos(symbol_info['name'], mt5.TIMEFRAME_H1, 0, 100)
            regime_info = self.regime_detector.detect_regime(symbol_info['name'], rates, indicators) if rates else {}

            decision = self.get_ai_decision(symbol_info, indicators, account, False)

            # Adjust confidence based on learned patterns
            if self.historian:
                setup_type = self._extract_setup_type(decision.get('reasoning', ''))
                adjusted_confidence = decision.get('confidence', 50)
                learned_threshold = self.historian.get_setup_confidence(setup_type)
                if self.historian.should_skip_setup(setup_type):
                    logger.info(f"Skipping {setup_type} for {symbol_info['name']} - poor historical win rate")
                    continue
            else:
                adjusted_confidence = decision.get('confidence', 50)

            min_confidence = 50
            if decision and decision.get('action') in ['BUY', 'SELL'] and adjusted_confidence >= min_confidence:
                lot, risk_pct = self.calculate_lot_size(symbol_info, adjusted_confidence, account.balance, indicators['atr'])

                # Apply position size adjustment based on regime
                regime_size_adjustment = regime_info.get('regime', 'UNKNOWN')
                if regime_size_adjustment == 'VOLATILE':
                    lot *= 0.7  # 30% smaller in volatile markets
                    logger.info(f"Reducing lot size by 30% due to volatile regime")

                tick = mt5.symbol_info_tick(symbol_info['name'])
                if not tick:
                    continue

                # Check if we should swap a position for this one
                if len(all_positions) >= 5:
                    should_swap, ticket_to_close = self.position_optimizer.should_swap_for_new_trade(
                        all_positions, adjusted_confidence
                    )
                    if should_swap and ticket_to_close:
                        logger.info(f"Swapping position {ticket_to_close} for new {decision['action']} signal")
                        self.close_position(ticket_to_close, "Position swap for better opportunity")
                        time.sleep(1)

                # Set SL/TP with regime adjustment
                if decision['action'] == 'BUY':
                    price = tick.ask
                    order_type = mt5.ORDER_TYPE_BUY
                    base_sl = indicators['support'] - indicators['atr']
                    base_tp = indicators['resistance'] + indicators['atr']
                else:
                    price = tick.bid
                    order_type = mt5.ORDER_TYPE_SELL
                    base_sl = indicators['resistance'] + indicators['atr']
                    base_tp = indicators['support'] - indicators['atr']

                # Apply regime adjustments to SL/TP
                if regime_info:
                    sl_multiple = regime_info.get('suggested_sl_multiple', 1.0)
                    tp_multiple = regime_info.get('suggested_tp_multiple', 1.5)
                    atr_adjusted = indicators['atr'] * (sl_multiple / tp_multiple)  # Adjust ATR scaling
                    if decision['action'] == 'BUY':
                        sl = indicators['support'] - (atr_adjusted * sl_multiple)
                        tp = indicators['resistance'] + (atr_adjusted * tp_multiple)
                    else:
                        sl = indicators['resistance'] + (atr_adjusted * sl_multiple)
                        tp = indicators['support'] - (atr_adjusted * tp_multiple)
                else:
                    sl = base_sl
                    tp = base_tp

                request = {
                    "action": mt5.TRADE_ACTION_DEAL, "symbol": symbol_info['name'], "volume": lot,
                    "type": order_type, "price": price, "sl": round(sl, 5), "tp": round(tp, 5),
                    "deviation": 20, "magic": 987654, "comment": f"Ultimate_{decision['action']}",
                    "type_filling": mt5.ORDER_FILLING_IOC,
                }
                result = mt5.order_send(request)
                if result.retcode == mt5.TRADE_RETCODE_DONE:
                    regime_note = f" [{regime_info.get('regime', 'N/A')}]" if regime_info else ""
                    self.send(f"🔥 {decision['action']} {lot} {symbol_info['name']} @ {price:.3f}{regime_note}\nRisk: {risk_pct:.1f}% | SL: {sl:.3f} | TP: {tp:.3f}\n{decision.get('reasoning', '')[:100]}")
                time.sleep(3)
    
    def run(self):
        logger.info("Ultimate trader running in background mode (Telegram disabled)")
        try:
            while True:
                self.is_market_open = self.check_market_status()
                # Core trading functionality - scan and execute trades
                self.scan_and_trade()
                time.sleep(30)
        except KeyboardInterrupt:
            logger.info("Ultimate trader stopped")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    agent = UltimateTrader()
    agent.run()