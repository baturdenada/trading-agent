"""
INTELLIGENCE HUB - Central integration of NLP, Workflows, and Self-Modification
Orchestrates all three systems into one unified interface
"""

import logging
import time
import json
import requests
from datetime import datetime
from dotenv import load_dotenv
import os
from nlp_engine import NLPEngine
from workflow_engine import WorkflowEngine
from self_modifier import SelfModifier
from conversational_hub import ConversationalHub
from api_helper import send_telegram_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)
load_dotenv()

class IntelligenceHub:
    def __init__(self):
        # Load configuration
        Config.validate_credentials()

        # Initialize conversational hub (main AI processor)
        self.conversational = ConversationalHub()

        # Initialize sub-systems for fallback
        self.nlp = NLPEngine()
        self.workflows = WorkflowEngine()
        self.modifier = SelfModifier()

        # Telegram
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID
        self.last_update_id = 0

        # State
        self.pending_approvals = {}
        self.memory_path = Config.TRADING_MEMORY_PATH

        logger.info("Intelligence Hub initialized with Conversational AI")
        self.send("🧠 INTELLIGENCE HUB ONLINE\nConversational AI Enabled\nYou can now chat naturally about trading, analysis, or place orders.\nJust type anything!")

    def send(self, msg):
        """Send Telegram message"""
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)

    def route_command(self, text):
        """Route command through conversational AI"""
        logger.info(f"Processing: {text}")

        # Use conversational hub for intelligent routing
        try:
            result = self.conversational.process_input(text)
            return result
        except Exception as e:
            logger.error(f"Conversational processing error: {e}")
            # Fallback to basic help
            return f"Error processing input. Available: analyze [symbol], buy/sell [symbol] [quantity], stats, risk, help"

    def handle_nlp_command(self, text):
        """Process command through NLP engine"""
        logger.info(f"NLP processing: {text}")
        self.send("🧠 Processing your command...")

        try:
            result = self.nlp.process_command(text)
            return result
        except Exception as e:
            return f"❌ NLP error: {str(e)}"

    def handle_workflow_command(self, text):
        """Process command through Workflow engine"""
        logger.info(f"Workflow processing: {text}")
        self.send("🔄 Executing workflow...")

        # Extract workflow name
        workflow_name = None
        workflows = ['daily-report', 'analyze-strategy', 'compare-symbols']

        for wf in workflows:
            if wf in text.lower():
                workflow_name = wf
                break

        if not workflow_name:
            return "❌ Unknown workflow. Available: daily-report, analyze-strategy, compare-symbols"

        # Load and execute
        workflow_file = f"C:\\Users\\user\\Desktop\\DS trading agent\\workflows\\{workflow_name}.md"

        try:
            result = self.workflows.execute_workflow(workflow_file)
            self.workflows.save_execution_log()
            return result
        except Exception as e:
            return f"❌ Workflow error: {str(e)}"

    def handle_self_modify_command(self, text):
        """Process command through Self-Modification system"""
        logger.info(f"Self-modify processing: {text}")
        self.send("🤖 Starting self-analysis...")

        try:
            result = self.modifier.analyze_and_suggest('ultimate_trader.py')

            if isinstance(result, dict) and result.get('status') == 'awaiting_approval':
                # Store for later approval
                session_id = datetime.now().strftime('%Y%m%d_%H%M%S')
                self.pending_approvals[session_id] = result
                return f"✅ Analysis complete. Awaiting your approval.\n\nReply with suggestion IDs (e.g., '1,3,5') to approve, or 'cancel' to skip."

            return result

        except Exception as e:
            return f"❌ Self-modification error: {str(e)}"

    def cmd_status(self):
        """System status"""
        status = """🧠 INTELLIGENCE HUB STATUS

✅ NLP Engine: Active
✅ Workflow Engine: Active
✅ Self-Modification: Active

CAPABILITIES:
• Natural language understanding
• Workflow automation
• Self-improvement suggestions
• Integration with Ultimate Trader

Try:
• 'analyze XAUUSD for 30 days'
• 'run daily-report workflow'
• 'self-analyze'"""
        return status

    def cmd_help(self):
        """Help menu"""
        help_text = """🧠 INTELLIGENCE HUB

NATURAL LANGUAGE (NLP):
• 'Analyze XAUUSD for 30 days'
• 'Backtest EURUSD with TP 300 SL 2000'
• 'Optimize XAGUSD parameters'
• 'Show stats', 'Risk analysis'

WORKFLOWS:
• 'Run daily-report workflow'
• 'Run analyze-strategy workflow'
• 'Run compare-symbols workflow'

SELF-IMPROVEMENT:
• 'Self-analyze' - Get improvement suggestions
• 'Self-improve' - Review optimization options

BUILT-IN:
• 'status' - System status
• 'help' - This menu"""
        return help_text

    def get_updates(self):
        """Get Telegram updates"""
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
                        logger.info(f"Received: {msg}")
                        result = self.route_command(msg)
                        self.send(result)
            return True
        except Exception as e:
            logger.error(f"Update error: {e}")
            return True

    def run(self):
        """Main loop"""
        self.send("🧠 INTELLIGENCE HUB STARTED\n\nI can help you with:\n• Natural language trading commands\n• Workflow automation\n• Self-improvement analysis\n\nType 'help' for commands")
        logger.info("Intelligence Hub running")

        try:
            while True:
                self.get_updates()
                time.sleep(2)
        except KeyboardInterrupt:
            self.send("Intelligence Hub stopped")
        finally:
            pass

if __name__ == "__main__":
    hub = IntelligenceHub()
    hub.run()
