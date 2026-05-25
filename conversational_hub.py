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
        logger.info("Conversational Hub initialized")

    def send(self, msg):
        """Send message via Telegram"""
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)

    def understand_intent(self, user_input):
        """Use GPT to understand what the user wants"""
        system_prompt = """You are an intelligent trading assistant. Analyze the user's input and determine their intent.

Respond with ONLY a JSON object (no other text):
{
    "intent": "ANALYZE|TRADE|BACKTEST|OPTIMIZE|STATS|RISK|CONVERSATION|UNKNOWN",
    "action": "specific action to take",
    "parameters": {
        "symbol": "symbol if mentioned",
        "quantity": "quantity/lot if mentioned",
        "tp": "take profit if mentioned",
        "sl": "stop loss if mentioned",
        "days": "days for analysis if mentioned"
    },
    "confidence": 0-100,
    "reasoning": "why you think this is the intent"
}

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

            # Calculate SL/TP if not provided
            if not sl:
                sl = indicators['support'] - indicators['atr']
            if not tp:
                tp = indicators['resistance'] + indicators['atr']

            # Validate risk
            account = trader.mt5_manager.get_account_info()
            if not account:
                return "Account not connected"

            if not trader.risk_manager.check_max_positions():
                return "Max concurrent positions reached"

            # Place trade
            import MetaTrader5 as mt5
            order_type = mt5.ORDER_TYPE_BUY if action.upper() == "BUY" else mt5.ORDER_TYPE_SELL

            request = {
                "action": mt5.TRADE_ACTION_DEAL,
                "symbol": symbol,
                "volume": quantity,
                "type": order_type,
                "price": indicators['price'],
                "sl": round(sl, 5),
                "tp": round(tp, 5),
                "deviation": 20,
                "magic": 987654,
                "comment": f"AI_{action.upper()}_{quantity}lot",
                "type_filling": mt5.ORDER_FILLING_IOC,
            }

            result = mt5.order_send(request)

            if result.retcode == mt5.TRADE_RETCODE_DONE:
                msg = f"TRADE OPENED\n{action.upper()} {quantity}L {symbol}\nEntry: ${indicators['price']:.4f}\nSL: ${sl:.4f}\nTP: ${tp:.4f}"
                return msg
            else:
                return f"Trade failed: {result.comment}"

        except Exception as e:
            logger.error(f"Trade execution error: {e}")
            return f"Trade execution error: {str(e)[:100]}"

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

            # Infer action from wording
            action = "BUY" if "buy" in user_input.lower() else "SELL" if "sell" in user_input.lower() else "BUY"

            if symbol:
                return self.handle_trade(symbol, action, quantity)
            else:
                return "What symbol do you want to trade? (XAUUSD, EURUSD, etc.)"

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
