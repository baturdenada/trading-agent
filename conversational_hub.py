"""
CONVERSATIONAL HUB - GPT-powered natural language understanding
Replaces rigid keyword matching with true AI conversation
Routes all inputs through GPT for intelligent decision-making
"""

import logging
import json
import os
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
from config import Config
from api_helper import send_telegram_reliable, call_deepseek_reliable

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class ConversationalHub:
    def __init__(self):
        Config.validate_credentials()
        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self.conversation_history = []

        # Natural language to symbol mapping
        self.symbol_aliases = {
            'gold': 'XAUUSD.s',
            'silver': 'XAGUSD.s',
            'euro': 'EURUSD.s',
            'eur': 'EURUSD.s',
            'dollar franc': 'USDCHF.s',
            'franc': 'USDCHF.s',
            'chf': 'USDCHF.s',
            'usdchf': 'USDCHF.s',
            'dollar yen': 'USDJPY.s',
            'yen': 'USDJPY.s',
            'jpy': 'USDJPY.s',
            'usdjpy': 'USDJPY.s',
            'dollar cad': 'USDCAD.s',
            'canadian': 'USDCAD.s',
            'cad': 'USDCAD.s',
            'usdcad': 'USDCAD.s',
            'pound': 'GBPUSD.s',
            'gbpusd': 'GBPUSD.s',
            'gbp': 'GBPUSD.s',
        }
        logger.info("Conversational Hub initialized")

    def send(self, msg):
        """Send message via Telegram"""
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)

    def parse_symbol_from_text(self, text):
        """Convert natural language like 'dollar franc' to 'USDCHF.s'"""
        text_lower = text.lower()

        # Check aliases
        for alias, symbol in self.symbol_aliases.items():
            if alias in text_lower:
                return symbol

        # Check direct symbol names (EURUSD, XAUUSD, etc)
        for word in text_lower.split():
            if word.upper() in ['EURUSD', 'XAUUSD', 'XAGUSD', 'USDCHF', 'USDJPY', 'USDCAD', 'GBPUSD']:
                return word.upper() + '.s'

        return None

    def understand_intent(self, user_input):
        """Use GPT to understand what the user wants"""
        system_prompt = """You are an intelligent trading assistant. Analyze the user's input and determine their intent.

Respond with ONLY a JSON object (no other text):
{
    "intent": "ANALYZE|TRADE|CLOSE|STATS|RISK|CONVERSATION|UNKNOWN",
    "action": "specific action to take",
    "parameters": {
        "symbol": "symbol if mentioned (e.g., 'euro' = EURUSD, 'dollar franc' = USDCHF, 'gold' = XAUUSD)",
        "quantity": "quantity/lot if mentioned",
        "tp": "take profit if mentioned",
        "sl": "stop loss if mentioned",
        "days": "days for analysis if mentioned"
    },
    "confidence": 0-100,
    "reasoning": "why you think this is the intent"
}

CLOSE intent examples:
- "close dollar franc" → CLOSE intent with symbol=USDCHF
- "close euro" → CLOSE intent with symbol=EURUSD
- "close gold position" → CLOSE intent with symbol=XAUUSD
- "shut down the yen trade" → CLOSE intent with symbol=USDJPY

INTENT GUIDE:
- ANALYZE: User wants technical analysis (e.g., "analyze gold", "how is eurusd", "check xauusd")
- TRADE: User wants to open a trade (e.g., "buy 0.05 gold", "sell eurusd", "open position")
- BACKTEST: User wants to test a strategy (e.g., "backtest eurusd with tp 300 sl 2000")
- OPTIMIZE: User wants to find best parameters
- STATS: User wants account statistics
- RISK: User wants risk analysis
- CONVERSATION: General chat (e.g., "how are you", "what can you do", "tell me about yourself")
- UNKNOWN: Can't determine intent

Extract parameters naturally - don't be strict about format."""

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_input}
                ],
                temperature=0.3,
                max_tokens=300
            )

            content = response.choices[0].message.content.strip()

            # Extract JSON from response
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                intent_data = json.loads(json_match.group(0))
                return intent_data
        except Exception as e:
            logger.error(f"Intent understanding error: {e}")

        return {
            "intent": "UNKNOWN",
            "action": "ask for clarification",
            "confidence": 0,
            "reasoning": "Error in processing"
        }

    def handle_stats(self):
        """Get account statistics and open positions"""
        try:
            from ultimate_trader import UltimateTrader
            import MetaTrader5 as mt5

            trader = UltimateTrader()
            account = trader.mt5_manager.get_account_info()

            if not account:
                return "MT5 not connected"

            positions = mt5.positions_get()
            open_count = len(positions) if positions else 0

            msg = f"📊 ACCOUNT STATS\n"
            msg += f"Balance: ${account.balance:.2f}\n"
            msg += f"Equity: ${account.equity:.2f}\n"
            msg += f"Profit/Loss: ${account.equity - account.balance:.2f}\n"
            msg += f"Open Positions: {open_count}\n"

            if open_count > 0:
                msg += f"\n🔓 OPEN POSITIONS:\n"
                for pos in positions[:5]:  # Show first 5
                    profit = pos.profit if hasattr(pos, 'profit') else 0
                    msg += f"• {pos.symbol}: {pos.volume}L @ ${pos.price_open:.4f} ({profit:+.2f})\n"
                if open_count > 5:
                    msg += f"... and {open_count - 5} more"

            return msg
        except Exception as e:
            logger.error(f"Stats error: {e}")
            return f"Error getting stats: {str(e)[:50]}"

    def handle_conversation(self, user_input):
        """Handle general conversation"""
        system_prompt = """You are an intelligent trading AI assistant with a friendly personality.
You help traders with:
- Technical analysis and market insights
- Trading strategy development
- Risk management advice
- Market news and events
- Performing trades with proper risk management

Be conversational, knowledgeable, and helpful. If asked about trading, provide specific insights.
Keep responses concise for Telegram (max 400 chars per message)."""

        self.conversation_history.append({"role": "user", "content": user_input})

        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt}
                ] + self.conversation_history[-6:],  # Keep last 6 messages for context
                temperature=0.7,
                max_tokens=400
            )

            assistant_response = response.choices[0].message.content
            self.conversation_history.append({"role": "assistant", "content": assistant_response})

            # Keep history size manageable
            if len(self.conversation_history) > 20:
                self.conversation_history = self.conversation_history[-20:]

            return assistant_response
        except Exception as e:
            return f"Error processing request: {str(e)[:100]}"

    def handle_analysis(self, symbol, days=30):
        """Handle analysis request by calling NLP engine"""
        from nlp_engine import NLPEngine
        try:
            nlp = NLPEngine()
            params = {
                'symbols': [symbol],
                'days': days,
                'strategy': 'Technical',
                'indicator': 'RSI'
            }
            result = nlp.handle_analyze(params)
            return result
        except Exception as e:
            logger.error(f"Analysis error: {e}")
            return f"Could not analyze {symbol}: {str(e)[:100]}"

    def handle_trade(self, symbol, action, quantity, tp=None, sl=None):
        """Handle trade execution request"""
        from ultimate_trader import UltimateTrader
        try:
            trader = UltimateTrader()

            # Get current price and indicators
            indicators = trader.calculate_indicators(symbol)
            if not indicators:
                return f"Could not get market data for {symbol}"

            # Convert SL/TP to float if provided
            if sl:
                try:
                    sl = float(sl)
                except (ValueError, TypeError):
                    sl = None
            if tp:
                try:
                    tp = float(tp)
                except (ValueError, TypeError):
                    tp = None

            # Calculate SL/TP if not provided
            if not sl:
                sl = indicators['support'] - indicators['atr']
            if not tp:
                tp = indicators['resistance'] + indicators['atr']

            # Validate risk
            account = trader.mt5_manager.get_account_info()
            if not account:
                return "Account not connected"

            # Check max positions
            import MetaTrader5 as mt5
            positions = mt5.positions_get()
            open_count = len(positions) if positions else 0

            limit_exceeded, reason = trader.risk_manager.check_max_positions(open_count)
            if limit_exceeded:
                return reason

            # Validate symbol exists
            symbol_info = mt5.symbol_info(symbol)
            if symbol_info is None:
                return f"Symbol {symbol} not found on MT5. Available: XAUUSD, EURUSD, GBPUSD, etc."

            if not symbol_info.trade_mode or symbol_info.trade_mode == 'DISABLED':
                return f"Trading disabled for {symbol}"

            # Validate and adjust volume - ensure all values are float
            min_volume = float(getattr(symbol_info, 'volume_min', None) or 0.1)
            volume_step = float(getattr(symbol_info, 'volume_step', None) or 0.01)
            max_volume = float(getattr(symbol_info, 'volume_max', None) or 1000)

            # Ensure quantity is float
            quantity = float(quantity)

            # Ensure quantity meets minimum
            if quantity < min_volume:
                quantity = min_volume

            # Cap at maximum
            if quantity > max_volume:
                quantity = max_volume

            # Round to nearest step
            if volume_step > 0:
                quantity = round(quantity / volume_step) * volume_step

            logger.info(f"Volume: {quantity} (min: {min_volume}, max: {max_volume}, step: {volume_step})")

            # Place trade
            order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL

            # Use current ask/bid instead of indicator price
            if action.upper() == "BUY":
                current_price = symbol_info.ask
            else:
                current_price = symbol_info.bid

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": quantity,
                "type": order_type,
                "price": current_price,
                "sl": round(sl, 5),
                "tp": round(tp, 5),
                "deviation": 20,
                "magic": 987654,
                "comment": f"AI_{action.upper()}_{quantity}lot",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result is None:
                # Try to get last error
                last_error = mt5.last_error()
                return f"MT5 Error: {last_error} - Try a different symbol or check MT5 account"

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                msg = f"✅ TRADE OPENED\n{action.upper()} {quantity}L {symbol}\nEntry: ${current_price:.4f}\nSL: ${sl:.4f}\nTP: ${tp:.4f}"
                return msg
            else:
                return f"Trade failed ({result.retcode}): {result.comment if hasattr(result, 'comment') else 'Unknown error'}"

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return f"Trade execution error: {str(e)[:100]}"

    def handle_close_position(self, symbol_text):
        """Close an open position by natural language symbol"""
        import MetaTrader5 as mt5

        # Convert natural language to symbol
        symbol = self.parse_symbol_from_text(symbol_text)

        if not symbol:
            return f"❌ Couldn't recognize symbol from: '{symbol_text}'\n\nTry: gold, silver, euro, dollar franc, dollar yen, dollar cad"

        # Find the position
        try:
            positions = mt5.positions_get(symbol=symbol)
            if not positions:
                return f"❌ No open position for {symbol}"

            # Close the position
            position = positions[0]
            tick = mt5.symbol_info_tick(symbol)
            if not tick:
                return f"❌ Could not get price for {symbol}"

            order_type = mt5.ORDER_TYPE_SELL if position.type == 0 else mt5.ORDER_TYPE_BUY
            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": position.volume,
                "type": order_type,
                "position": position.ticket,
                "deviation": 20,
                "comment": "Closed via natural language command",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result is None:
                last_error = mt5.last_error()
                return f"❌ Order send failed for {symbol}: {last_error}"

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                return f"✅ Closed {symbol} | P&L: ${position.profit:+.2f}"
            else:
                error_msg = result.comment if hasattr(result, 'comment') else 'Unknown error'
                return f"❌ Close failed for {symbol}: {error_msg}"

        except Exception as e:
            logger.error(f"Close position exception: {e}")
            return f"❌ Error closing {symbol}: {str(e)[:100]}"

    def process_input(self, user_input):
        """Main entry point - process any user input intelligently"""
        logger.info(f"Processing: {user_input}")

        # Understand intent
        intent_data = self.understand_intent(user_input)
        intent = intent_data.get('intent', 'UNKNOWN')

        logger.info(f"Intent: {intent} (confidence: {intent_data.get('confidence')}%)")

        # Route based on intent
        if intent == "ANALYZE":
            symbol = intent_data.get('parameters', {}).get('symbol')
            if symbol:
                return self.handle_analysis(symbol)
            else:
                return "I can analyze: XAUUSD, XAGUSD, EURUSD, USDCAD, USDJPY, USDCHF, USOUSD, SP500, NAS100. Which would you like?"

        elif intent == "TRADE":
            params = intent_data.get('parameters', {})
            symbol = params.get('symbol')
            quantity = params.get('quantity', 0.1)
            tp = params.get('tp')
            sl = params.get('sl')

            # Infer action from wording
            action = "BUY" if "buy" in user_input.lower() else "SELL" if "sell" in user_input.lower() else "BUY"

            if symbol:
                return self.handle_trade(symbol, action, quantity, tp=tp, sl=sl)
            else:
                return "What symbol do you want to trade? (XAUUSD, EURUSD, etc.)"

        elif intent == "CLOSE":
            symbol_text = intent_data.get('parameters', {}).get('symbol', user_input)
            return self.handle_close_position(symbol_text)

        elif intent == "STATS":
            return self.handle_stats()

        elif intent == "RISK":
            return self.handle_stats()  # Similar to stats for now

        elif intent == "CONVERSATION":
            return self.handle_conversation(user_input)

        else:
            # Default: try conversation
            return self.handle_conversation(user_input)

if __name__ == "__main__":
    hub = ConversationalHub()

    # Test inputs
    test_inputs = [
        "Analyze gold",
        "How are you?",
        "Buy 0.5 eurusd",
        "What's the current situation in XAUUSD",
        "Show me risk analysis"
    ]

    for test_input in test_inputs:
        print(f"\nUser: {test_input}")
        response = hub.process_input(test_input)
        print(f"Bot: {response}")
