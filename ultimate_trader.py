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
from trade_state_machine import TradeStateMachine, TradeState
from consensus_engine import ConsensusEngine, AgentOpinion
from multi_timeframe_analyzer import MultiTimeframeAnalyzer
from strategy_plugin import StrategyPluginManager, SignalOutput
from ml_feedback import get_analyzer, TradeOutcome
from economic_calendar import get_calendar

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

        # Initialize state machine & consensus engine for professional trade execution
        self.state_machine = TradeStateMachine(
            min_confirmation_candles=1,  # 1 candle minimum
            max_confirmation_candles=3   # 3 candle maximum
        )
        self.consensus_engine = ConsensusEngine(required_agreement=0.66)  # 2/3 agreement required
        self.mtf_analyzer = MultiTimeframeAnalyzer()  # Multi-timeframe confirmation across H1/M30/M15
        self.strategy_manager = StrategyPluginManager()  # Modular strategy system
        self.ml_analyzer = get_analyzer()  # ML feedback loop for learning from outcomes
        self.economic_calendar = get_calendar()  # Economic calendar for news avoidance

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

        logger.info("ULTIMATE TRADER INITIALIZED - Ready for trading operations")
    
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
    
    def calculate_lot_size(self, symbol_info, confidence, account_balance, atr, risk_reward_ratio=None):
        """Calculate lot size with dynamic adjustment based on R:R ratio"""
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

            # DYNAMIC POSITION SIZING: Adjust based on risk/reward ratio
            if risk_reward_ratio and risk_reward_ratio > 2.0:
                lot_size *= 1.2  # 20% bigger for excellent risk/reward (1:2 or better)
            elif risk_reward_ratio and risk_reward_ratio < 1.0:
                lot_size *= 0.6  # 40% smaller for poor risk/reward (<1:1)

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

            # Apply R:R adjustment
            if risk_reward_ratio and risk_reward_ratio > 2.0:
                lot_size *= 1.2
            elif risk_reward_ratio and risk_reward_ratio < 1.0:
                lot_size *= 0.6

            lot_size = max(0.01, min(lot_size, 0.5))
            return round(lot_size, 2), risk_pct

    def collect_consensus_opinions(self, symbol_info, indicators, ai_decision, regime_info, all_positions):
        """
        Collect opinions from multiple systems for consensus voting

        Returns: List of AgentOpinion objects
        """
        opinions = []

        # 1. NLP/AI Engine opinion
        ai_action = ai_decision.get('action', 'SKIP')
        ai_confidence = ai_decision.get('confidence', 50)
        opinions.append(AgentOpinion(
            agent_name='nlp_engine',
            action=ai_action,
            confidence=ai_confidence,
            reasoning=ai_decision.get('reasoning', 'AI analysis')[:60],
            signal_strength='STRONG' if ai_confidence > 70 else 'WEAK'
        ))

        # 2. Regime Detector opinion
        regime = regime_info.get('regime', 'UNKNOWN')
        regime_opinion_action = 'SKIP'
        regime_confidence = regime_info.get('confidence', 50)

        if regime == 'STRONG_TREND':
            regime_opinion_action = ai_action  # Follow AI signal in strong trends
            regime_confidence = min(regime_confidence + 10, 100)
        elif regime == 'VOLATILE':
            regime_opinion_action = 'SKIP'  # Skip in volatile markets
            regime_confidence = 100
        elif regime == 'RANGING':
            regime_opinion_action = ai_action if ai_confidence > 60 else 'SKIP'

        opinions.append(AgentOpinion(
            agent_name='regime_detector',
            action=regime_opinion_action,
            confidence=regime_confidence,
            reasoning=f'{regime} market (confidence: {regime_info.get("confidence", 50)}%)',
            signal_strength='STRONG',
            regime=regime
        ))

        # 3. Position Optimizer opinion (look at existing position quality)
        pos_optimizer_action = 'SKIP'
        pos_optimizer_confidence = 50

        if all_positions:
            avg_quality = sum(p['score'].get('total', 50) if isinstance(p.get('score'), dict)
                            else p.get('score', 50) for p in all_positions) / len(all_positions)
            if avg_quality < 40:  # Existing positions weak
                pos_optimizer_action = ai_action  # Open new positions
                pos_optimizer_confidence = 70
            elif avg_quality > 75:  # Existing positions excellent
                pos_optimizer_action = 'SKIP'  # Don't add new positions
                pos_optimizer_confidence = 80
        else:
            pos_optimizer_action = ai_action
            pos_optimizer_confidence = 65

        opinions.append(AgentOpinion(
            agent_name='position_optimizer',
            action=pos_optimizer_action,
            confidence=pos_optimizer_confidence,
            reasoning=f'Current portfolio quality: {avg_quality:.0f}' if all_positions else 'No existing positions',
            signal_strength='STRONG' if pos_optimizer_confidence > 70 else 'WEAK'
        ))

        return opinions

    def get_hybrid_decision(self, symbol_info, indicators, account, has_position):
        """
        Hybrid decision: Combine AI analysis with plugin strategies
        Returns best signal from plugins, validated by AI
        """
        # Get all plugin signals
        plugin_signals = self.strategy_manager.analyze_with_all(
            symbol_info['name'],
            indicators,
            {'balance': account.balance, 'equity': account.equity}
        )

        # Filter for trading signals (not HOLD)
        trading_signals = {
            name: signal for name, signal in plugin_signals.items()
            if signal.action in ['BUY', 'SELL']
        }

        # If plugins suggest trading, use their signal
        if trading_signals:
            # Get highest confidence signal
            best_signal = max(trading_signals.values(), key=lambda s: s.confidence)
            logger.info(f"Plugin signal for {symbol_info['name']}: {best_signal.setup_type} - {best_signal.action} ({best_signal.confidence:.0f}%)")

            return {
                'action': best_signal.action,
                'confidence': best_signal.confidence,
                'entry_price': best_signal.entry_price,
                'stop_loss': best_signal.stop_loss,
                'take_profit': best_signal.take_profit,
                'reasoning': best_signal.reasoning,
                'source': 'PLUGIN'
            }

        # No plugin signals, fall back to AI decision
        logger.debug(f"No plugin signals for {symbol_info['name']}, using AI")
        ai_decision = self.get_ai_decision(symbol_info, indicators, account, has_position)
        ai_decision['source'] = 'AI'
        return ai_decision

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
        pnl_pct = (pnl / (position.volume * entry * 100)) * 100 if entry > 0 else 0
        pnl_pips = (current_price - entry) / symbol_info['pip_value'] if position.type == 0 else (entry - current_price) / symbol_info['pip_value']
        atr = self.calculate_atr(symbol_info['name'])
        risk_in_pips = abs(entry - position.sl) / symbol_info['pip_value'] if position.sl else 50

        # AUTO-CLOSE LOSING TRADES BASED ON SETUP QUALITY DEGRADATION
        if pnl < 0:
            indicators = self.calculate_indicators(symbol_info['name'])
            if indicators:
                # If trend has completely reversed from entry, consider it a bad setup
                entry_bias = "BUY" if position.type == 0 else "SELL"
                current_trend = indicators['trend']

                # Reverse direction indicators mean setup is degraded
                if (entry_bias == "BUY" and current_trend in ["STRONG_DOWN", "WEAK_DOWN"]) or \
                   (entry_bias == "SELL" and current_trend in ["STRONG_UP", "WEAK_UP"]):
                    # Check if loss is small enough to exit - don't wait for SL
                    if pnl_pct > -1.5:  # Exit losing trades with <1.5% loss if setup degraded
                        self.close_position(position.ticket, "Setup degradation - trend reversed")
                        logger.info(f"Closed losing position {symbol_info['name']} due to setup degradation")
                        return

        # 1. PROFIT-TAKING ALERTS - Notify user of opportunities
        if position.tp:
            distance_to_tp = abs(position.tp - current_price)
            pct_to_tp = (distance_to_tp / abs(position.tp - entry)) * 100 if position.tp != entry else 0

            if pnl > 0:
                # WINNING POSITION - Alert at milestones
                if pnl > position.volume * entry * 0.01 and pnl_pct > 0.5:  # 0.5%+ profit
                    self.send(f"💰 PROFIT ALERT {position.symbol}: +${pnl:.2f} ({pnl_pct:.2f}%) | {pct_to_tp:.0f}% away from TP\nType CLOSE {position.ticket} to exit with profit")
                elif pnl > position.volume * entry * 0.02 and pnl_pct > 1.0:  # 1.0%+ profit
                    self.send(f"🎯 STRONG PROFIT {position.symbol}: +${pnl:.2f} ({pnl_pct:.2f}%) | {pct_to_tp:.0f}% from TP\nSuggest: CLOSE for guaranteed profit or hold for TP")

        # 2. TRAILING STOP - Lock in profits above 1.5x risk
        if pnl_pips > risk_in_pips * self.trailing_activation and pnl > 0:
            new_sl = current_price - (self.trailing_distance * risk_in_pips * symbol_info['pip_value']) if position.type == 0 else current_price + (self.trailing_distance * risk_in_pips * symbol_info['pip_value'])
            if (position.type == 0 and new_sl > position.sl) or (position.type == 1 and new_sl < position.sl):
                self.modify_sl(position.ticket, new_sl)
                logger.info(f"Trailing stop updated for {symbol_info['name']} to ${new_sl:.3f}")
                self.send(f"🛡️ TRAILING STOP activated {position.symbol} | New SL: ${new_sl:.4f}")

        # 3. BREAK-EVEN STOP - Move SL to entry when at 0.5x risk profit
        if pnl > 0 and pnl_pips > (risk_in_pips * 0.5):
            breakeven_sl = entry if position.type == 0 else entry
            if (position.type == 0 and breakeven_sl > position.sl) or (position.type == 1 and breakeven_sl < position.sl):
                self.modify_sl(position.ticket, breakeven_sl)
                logger.info(f"Break-even stop set for {symbol_info['name']}")
                self.send(f"✅ BREAK-EVEN STOP {position.symbol} | SL moved to entry")

        # 4. LOSS MANAGEMENT - Alert on losses approaching SL
        if pnl < 0:
            loss_pct = abs(pnl_pct)
            if loss_pct > 0.5 and loss_pct < 1.5:
                self.send(f"⚠️ LOSS ALERT {position.symbol}: -${abs(pnl):.2f} ({loss_pct:.2f}%)\nConsider cutting loss or wait for reversal")
            elif loss_pct > 1.5:
                self.send(f"🔴 SIGNIFICANT LOSS {position.symbol}: -${abs(pnl):.2f} ({loss_pct:.2f}%)\nRecommend: Review position or close")

        # 5. RSI-BASED EXIT - Close overbought/oversold
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
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
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

    def should_defer_trade(self, confidence, symbol, existing_positions):
        """Intelligent hold logic - defer trade if better to wait"""
        if len(existing_positions) < 3:
            return False  # Open capacity, don't defer

        # If new signal is low-moderate confidence but we have high-quality positions, defer
        if confidence < 70:
            # Check quality of existing positions (extract 'total' score from dict)
            existing_scores = [p.get('score', {}).get('total', 50) if isinstance(p.get('score'), dict) else p.get('score', 50) for p in existing_positions]
            avg_position_quality = sum(existing_scores) / len(existing_scores) if existing_scores else 50

            if avg_position_quality > 65:
                logger.info(f"Deferring {symbol} trade (confidence {confidence}) - existing positions are higher quality")
                return True

        return False

    def attempt_grid_trade(self, position, symbol_info, confidence):
        """Grid trade on losers - average down if setup is still valid"""
        if position.profit > -0.5:  # Only grid if loss > 0.5%
            return False

        indicators = self.calculate_indicators(symbol_info['name'])
        if not indicators:
            return False

        # Check if original setup is still valid (haven't completely reversed)
        entry_bias = "BUY" if position.type == 0 else "SELL"
        current_rsi = indicators['rsi']

        # Grid if RSI hasn't completely reversed AND confidence is high
        is_oversold = current_rsi < 30
        is_overbought = current_rsi > 70

        if (entry_bias == "BUY" and is_oversold and confidence > 75) or \
           (entry_bias == "SELL" and is_overbought and confidence > 75):
            # Calculate grid lot - smaller than original
            tick = mt5.symbol_info_tick(symbol_info['name'])
            if not tick:
                return False

            grid_lot = position.volume * 0.5  # Grid is 50% of original position
            grid_price = tick.ask if entry_bias == "BUY" else tick.bid

            order_type = mt5.ORDER_TYPE_BUY if entry_bias == "BUY" else mt5.ORDER_TYPE_SELL
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol_info['name'],
                "volume": grid_lot,
                "type": order_type,
                "price": grid_price,
                "deviation": 20,
                "comment": "GRID_TRADE",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)
            if result and result.retcode == mt5.TRADE_RETCODE_DONE:
                self.send(f"📊 GRID TRADE OPENED: Averaging down on {symbol_info['name']} | Grid: {grid_lot}L @ ${grid_price:.4f}")
                logger.info(f"Grid trade executed for {symbol_info['name']}: {grid_lot}L")
                return True

        return False

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
        """
        Professional trade execution with:
        - State machine (confirmation phases)
        - Multi-agent consensus voting
        - Smart risk management
        """
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

            # PHASE 1: Manage existing positions
            if positions:
                for pos in positions:
                    self.manage_position(pos, symbol_info)
                    # Try grid trading if position is losing and setup is still valid
                    indicators = self.calculate_indicators(symbol_info['name'])
                    if indicators and pos.profit < 0:
                        decision = self.get_ai_decision(symbol_info, indicators, account, True)
                        self.attempt_grid_trade(pos, symbol_info, decision.get('confidence', 0))
                continue

            # Check economic calendar (Phase 1.5: Avoid news trades)
            self.economic_calendar.maybe_refresh()
            if self.economic_calendar.should_skip_trade(symbol_info['name']):
                logger.info(f"Skipping {symbol_info['name']} due to economic event")
                continue

            # PHASE 2: Detect new signals
            indicators = self.calculate_indicators(symbol_info['name'])
            if not indicators:
                continue

            # Get market regime
            rates = mt5.copy_rates_from_pos(symbol_info['name'], mt5.TIMEFRAME_H1, 0, 100)
            regime_info = self.regime_detector.detect_regime(symbol_info['name'], rates, indicators) if rates is not None else {}

            # Get hybrid decision (plugins first, fallback to AI)
            decision = self.get_hybrid_decision(symbol_info, indicators, account, False)

            # Adjust confidence based on learned patterns
            adjusted_confidence = decision.get('confidence', 50)
            setup_type = self._extract_setup_type(decision.get('reasoning', ''))

            # ML feedback: Apply confidence adjustment based on historical performance
            if self.ml_analyzer:
                ml_adjustment = self.ml_analyzer.get_confidence_adjustment(
                    setup_type, symbol_info['name'], regime_info.get('regime', 'UNKNOWN')
                )
                adjusted_confidence = adjusted_confidence * ml_adjustment
                logger.info(f"ML adjustment for {symbol_info['name']}: {adjusted_confidence:.0f}% (multiplier: {ml_adjustment:.2f}x)")

                # Skip if poor historical performance
                if self.ml_analyzer.should_skip_setup(setup_type):
                    logger.info(f"Skipping {setup_type} for {symbol_info['name']} - poor historical win rate")
                    continue

            # PHASE 2.5: Multi-Timeframe Confirmation
            mtf_decision = None
            if decision and decision.get('action') in ['BUY', 'SELL']:
                mtf_decision = self.mtf_analyzer.analyze_signal(
                    symbol_info['name'],
                    decision.get('action'),
                    rates,  # H1 rates from earlier
                    indicators
                )
                self.mtf_analyzer.log_analysis(mtf_decision)

                # Apply multi-timeframe confidence adjustment
                adjusted_confidence = adjusted_confidence * mtf_decision.confidence_adjustment
                logger.info(f"MTF adjustment for {symbol_info['name']}: {adjusted_confidence:.0f}% (multiplier: {mtf_decision.confidence_adjustment:.2f}x)")

                # Skip if multi-timeframe analysis suggests not to proceed
                if not mtf_decision.should_proceed:
                    logger.info(f"Skipping {symbol_info['name']}: Multi-timeframe conflict detected")
                    continue

            # PHASE 3: Consensus voting on new signals
            if decision and decision.get('action') in ['BUY', 'SELL'] and adjusted_confidence >= 50:
                # Collect opinions from multiple systems
                opinions = self.collect_consensus_opinions(
                    symbol_info, indicators, decision, regime_info, all_positions
                )

                # Reach consensus
                consensus = self.consensus_engine.collect_opinions(symbol_info['name'], opinions)
                self.consensus_engine.log_consensus(consensus)

                # Skip if no consensus
                if not consensus.should_execute:
                    if consensus.verdict.value == "DISAGREEMENT":
                        logger.warning(f"⚠️ Agent disagreement on {symbol_info['name']} - skipping")
                    continue

                # Check if we should defer this trade
                if self.should_defer_trade(adjusted_confidence, symbol_info['name'], all_positions):
                    logger.info(f"Trade deferred for {symbol_info['name']} - waiting for better setup")
                    continue

                # Check correlation risk
                # all_positions already contains dicts from position_optimizer, not MT5 objects
                corr_exceeded, corr_reason = self.risk_manager.check_correlation_risk(
                    all_positions, self.max_correlated
                )
                if corr_exceeded:
                    logger.warning(f"Skipping {symbol_info['name']}: {corr_reason}")
                    continue

                # PHASE 4: Arm setup in state machine (wait for confirmation)
                self.state_machine.detect_signal(symbol_info['name'], {
                    'action': decision['action'],
                    'entry_price': decision.get('entry_price', 0),
                    'stop_loss': decision.get('stop_loss', 0),
                    'take_profit': decision.get('take_profit', 0),
                    'confidence': consensus.consensus_confidence,
                    'reasoning': consensus.reasoning,
                    'regime': regime_info.get('regime', 'UNKNOWN')
                })

            # PHASE 5: Monitor pending setups (confirmation → entry window → execution)
            if symbol_info['name'] in self.state_machine.pending_setups:
                setup = self.state_machine.pending_setups[symbol_info['name']]
                tick = mt5.symbol_info_tick(symbol_info['name'])
                if not tick:
                    continue

                current_price = tick.ask if setup.action == 'BUY' else tick.bid

                # Check for pullback/confirmation
                confirm_result = self.state_machine.process_confirmation(
                    symbol_info['name'], current_price, "UP"  # Would get from candle analysis
                )

                if confirm_result['ready_to_enter']:
                    setup = confirm_result['setup']
                    # Now check for breakout entry
                    entry_result = self.state_machine.check_entry_window(symbol_info['name'], current_price)

                    if entry_result['should_enter']:
                        setup = entry_result['setup']
                        # Execute the trade
                        self._execute_confirmed_trade(setup, symbol_info, indicators, regime_info, account, all_positions)
                        self.state_machine.close_setup(symbol_info['name'])

                time.sleep(1)

    def _execute_confirmed_trade(self, setup, symbol_info, indicators, regime_info, account, all_positions):
        """Execute a trade that passed all confirmation phases"""
        # Calculate risk/reward ratio
        risk_reward_ratio = None
        if setup.stop_loss and setup.take_profit:
            try:
                risk = abs(setup.entry_price - setup.stop_loss)
                reward = abs(setup.take_profit - setup.entry_price)
                risk_reward_ratio = reward / risk if risk > 0 else 1.0
            except:
                risk_reward_ratio = None

        lot, risk_pct = self.calculate_lot_size(
            symbol_info, setup.confidence, account.balance,
            indicators['atr'], risk_reward_ratio=risk_reward_ratio
        )

        # Apply regime adjustment
        if setup.regime == 'VOLATILE':
            lot *= 0.7
            logger.info(f"Reducing lot size by 30% due to volatile regime")

        tick = mt5.symbol_info_tick(symbol_info['name'])
        if not tick:
            return

        # Swap if needed
        if len(all_positions) >= 5:
            should_swap, ticket_to_close = self.position_optimizer.should_swap_for_new_trade(
                all_positions, setup.confidence
            )
            if should_swap and ticket_to_close:
                logger.info(f"Swapping position {ticket_to_close} for {setup.action} signal")
                self.close_position(ticket_to_close, "Position swap for better opportunity")
                time.sleep(1)

        # Set order parameters
        if setup.action == 'BUY':
            price = tick.ask
            order_type = mt5.ORDER_TYPE_BUY
        else:
            price = tick.bid
            order_type = mt5.ORDER_TYPE_SELL

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol_info['name'],
            "volume": lot,
            "type": order_type,
            "price": price,
            "sl": round(setup.stop_loss, 5),
            "tp": round(setup.take_profit, 5),
            "deviation": 20,
            "magic": 987654,
            "comment": f"Ultimate_{setup.action}_Confirmed",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }

        result = mt5.order_send(request)
        if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
            regime_note = f" [{setup.regime}]"
            self.send(
                f"✅ CONFIRMED ENTRY: {setup.action} {lot} {symbol_info['name']} @ {price:.3f}{regime_note}\n"
                f"Risk: {risk_pct:.1f}% | SL: {setup.stop_loss:.3f} | TP: {setup.take_profit:.3f}\n"
                f"Consensus: {setup.confidence:.0f}%\n{setup.reasoning[:80]}"
            )
            logger.info(f"🎯 Trade executed after confirmation phase: {symbol_info['name']} {setup.action}")
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