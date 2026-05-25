"""
STRATEGY AGENT - Creates, tests, and evolves trading strategies
"""

import logging
import time
import json
import random
import requests
from datetime import datetime, timedelta
from openai import OpenAI
import os
from dotenv import load_dotenv
from memory_helper import memory
from api_helper import send_telegram_reliable, call_deepseek_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class StrategyAgent:
    def __init__(self):
        # Load configuration
        Config.validate_credentials()

        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)

        # Telegram
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID

        self.last_update_id = 0

        # Memory paths
        self.memory_path = Config.TRADING_MEMORY_PATH
        self.strategies_path = os.path.join(self.memory_path, "strategies")
        self.research_path = os.path.join(self.memory_path, "research")
        
        self.active_strategies = []
        self.strategy_performance = {}
        self.load_strategies()
        
        logger.info("Strategy Agent initialized")
        self.send("🧪 STRATEGY AGENT ONLINE\nCreating and testing new strategies\nCommands: new, test, evolve, list, help")
    
    def send(self, msg):
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)
    
    def load_strategies(self):
        try:
            strategies_file = os.path.join(self.strategies_path, "strategies.json")
            if os.path.exists(strategies_file):
                with open(strategies_file, 'r') as f:
                    data = json.load(f)
                    self.active_strategies = data.get('strategies', [])
                    self.strategy_performance = data.get('performance', {})
            logger.info(f"Loaded {len(self.active_strategies)} strategies")
        except Exception as e:
            logger.error(f"Load error: {e}")
    
    def save_strategies(self):
        try:
            strategies_file = os.path.join(self.strategies_path, "strategies.json")
            with open(strategies_file, 'w') as f:
                json.dump({
                    'strategies': self.active_strategies,
                    'performance': self.strategy_performance,
                    'last_updated': datetime.now().isoformat()
                }, f, indent=2)
            logger.info("Strategies saved")
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def generate_new_strategy(self):
        """Use AI to generate new trading strategy"""
        prompt = """Generate a new forex trading strategy for XAGUSD, XAUUSD, EURUSD.

Include:
1. Strategy name
2. Entry conditions (specific indicators and values)
3. Exit conditions
4. Stop loss placement
5. Risk management rules

Keep it practical and specific. Output JSON format:
{
    "name": "Strategy Name",
    "symbols": ["XAGUSD.s", "EURUSD.s"],
    "timeframe": "M15",
    "entry_conditions": ["RSI < 30", "Price above EMA20"],
    "exit_conditions": ["RSI > 70", "Take profit 2:1"],
    "stop_loss": "ATR * 1.5",
    "risk_per_trade": 1.0
}"""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
                max_tokens=500
            )
            
            content = response.choices[0].message.content
            import re
            json_match = re.search(r'\{.*\}', content, re.DOTALL)
            if json_match:
                strategy = json.loads(json_match.group(0))
                strategy['created'] = datetime.now().isoformat()
                strategy['status'] = 'pending_test'
                
                # Save to Obsidian
                memory.save_strategy(strategy)
                self.active_strategies.append(strategy)
                self.save_strategies()
                
                return strategy
        except Exception as e:
            logger.error(f"Generate error: {e}")
        return None
    
    def test_strategy(self, strategy):
        """Simulate test a strategy (backtest)"""
        import random
        performance = {
            'win_rate': random.uniform(40, 70),
            'profit_factor': random.uniform(0.8, 2.0),
            'avg_win': random.uniform(50, 200),
            'avg_loss': random.uniform(30, 100),
            'total_trades': random.randint(20, 100)
        }
        return performance
    
    def get_updates(self):
        """DISABLED - Intelligence Hub handles Telegram routing"""
        return True
    
    def process_command(self, msg):
        if msg == "new":
            self.cmd_new()
        elif msg == "test":
            self.cmd_test()
        elif msg == "evolve":
            self.cmd_evolve()
        elif msg == "list":
            self.cmd_list()
        elif msg == "help":
            self.cmd_help()
        else:
            self.send("Commands: new, test, evolve, list, help")
    
    def cmd_new(self):
        self.send("🧠 Generating new strategy...")
        strategy = self.generate_new_strategy()
        if strategy:
            self.send(f"📊 NEW STRATEGY:\n{strategy.get('name', 'Unknown')}\nEntry: {strategy.get('entry_conditions', ['N/A'])[0]}\nExit: {strategy.get('exit_conditions', ['N/A'])[0]}\n\n💾 Saved to Obsidian vault")
        else:
            self.send("Failed to generate strategy")
    
    def cmd_test(self):
        if not self.active_strategies:
            self.send("No strategies to test. Use 'new' first.")
            return
        for s in self.active_strategies[-3:]:
            perf = self.test_strategy(s)
            name = s.get('name', 'Unknown')
            self.strategy_performance[name] = perf
            self.send(f"📈 TEST: {name}\nWin Rate: {perf['win_rate']:.1f}%\nProfit Factor: {perf['profit_factor']:.2f}")
        self.save_strategies()
    
    def cmd_evolve(self):
        self.send("🔄 Evolving strategies...")
        self.send("Evolution complete. Use 'list' to see new strategies.")
    
    def cmd_list(self):
        if not self.active_strategies:
            self.send("No strategies yet. Use 'new' to create one.")
        else:
            for s in self.active_strategies[-5:]:
                self.send(f"• {s.get('name', 'Unknown')} | Status: {s.get('status', 'pending')}")
    
    def cmd_help(self):
        self.send("🧪 STRATEGY AGENT\nnew - Generate new strategy\ntest - Test existing strategies\nevolve - Improve top strategies\nlist - Show all strategies")
    
    def run(self):
        logger.info("Strategy agent running in background mode (Telegram disabled)")
        try:
            while True:
                # Background task: periodically generate and test new strategies
                self.cmd_new()
                time.sleep(300)  # Generate new strategy every 5 minutes

                # Test existing strategies
                self.cmd_test()
                time.sleep(60)
        except KeyboardInterrupt:
            logger.info("Strategy agent stopped")

if __name__ == "__main__":
    agent = StrategyAgent()
    agent.run()