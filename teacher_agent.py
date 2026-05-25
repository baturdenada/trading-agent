"""
Teacher Agent - Learns from past trades, improves strategies, stores memory
"""

import logging
import time
import json
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os
import requests
from datetime import datetime, timedelta
from openai import OpenAI
from memory_helper import memory
from api_helper import send_telegram_reliable, call_deepseek_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class TeacherAgent:
    def __init__(self):
        # Load configuration
        Config.validate_credentials()

        self.client = OpenAI(api_key=Config.DEEPSEEK_API_KEY, base_url=Config.DEEPSEEK_API_URL)

        # MT5
        self.login = Config.MT5_LOGIN
        self.password = Config.MT5_PASSWORD
        self.server = Config.MT5_SERVER
        self.path = Config.MT5_PATH

        # Telegram
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID

        self.last_update_id = 0

        # Memory
        self.memory_path = Config.TRADING_MEMORY_PATH
        self.memory_path.mkdir(parents=True, exist_ok=True)
        
        self.trade_history = []
        self.lessons_learned = []
        self.current_stats = {}
        self.load_memory()
        
        # Connect MT5 to fetch trades
        self.connect_mt5()
        
        # Fetch trades on startup
        self.fetch_recent_trades()
        self.analyze_performance()
        
        logger.info("Teacher Agent initialized")
        self.send("🧠 TEACHER AGENT ONLINE\nI analyze trades and provide insights.\nCommands: learn, insights, improve, stats, memory, reflect, help")
    
    def send(self, msg):
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)
    
    def connect_mt5(self):
        try:
            if not mt5.initialize(path=self.path, login=self.login, password=self.password, server=self.server):
                logger.error("MT5 connection failed")
                return False
            return True
        except Exception as e:
            logger.error(f"MT5 error: {e}")
            return False
    
    def load_memory(self):
        try:
            trade_file = os.path.join(self.memory_path, "trade_history.json")
            if os.path.exists(trade_file):
                with open(trade_file, 'r') as f:
                    self.trade_history = json.load(f)
            
            lessons_file = os.path.join(self.memory_path, "lessons.json")
            if os.path.exists(lessons_file):
                with open(lessons_file, 'r') as f:
                    self.lessons_learned = json.load(f)
            
            logger.info(f"Loaded {len(self.trade_history)} trades, {len(self.lessons_learned)} lessons")
        except Exception as e:
            logger.error(f"Load error: {e}")
    
    def save_memory(self):
        try:
            trade_file = os.path.join(self.memory_path, "trade_history.json")
            with open(trade_file, 'w') as f:
                json.dump(self.trade_history[-1000:], f, indent=2)
            
            lessons_file = os.path.join(self.memory_path, "lessons.json")
            with open(lessons_file, 'w') as f:
                json.dump(self.lessons_learned[-100:], f, indent=2)
            
            logger.info("Memory saved")
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def fetch_recent_trades(self):
        """Get all trades from MT5 history"""
        from_date = int((datetime.now() - timedelta(days=30)).timestamp())
        to_date = int(time.time())
        history = mt5.history_deals_get(from_date, to_date)
        
        new_trades = []
        if history:
            for deal in history:
                if deal.profit != 0:
                    trade = {
                        'ticket': deal.ticket,
                        'symbol': deal.symbol,
                        'time': datetime.fromtimestamp(deal.time).isoformat(),
                        'action': 'BUY' if deal.type == 0 else 'SELL',
                        'volume': deal.volume,
                        'price': deal.price,
                        'profit': deal.profit,
                        'is_win': deal.profit > 0
                    }
                    
                    if not any(t.get('ticket') == deal.ticket for t in self.trade_history):
                        new_trades.append(trade)
                        # Save to Obsidian
                        memory.save_trade(trade)
        
        if new_trades:
            self.trade_history.extend(new_trades)
            self.save_memory()
            logger.info(f"Added {len(new_trades)} new trades")
        
        return new_trades
    
    def analyze_performance(self):
        """Analyze trade performance"""
        if not self.trade_history:
            self.current_stats = {'total_trades': 0, 'wins': 0, 'losses': 0, 'win_rate': 0, 'net_profit': 0}
            return self.current_stats
        
        wins = [t for t in self.trade_history if t['is_win']]
        losses = [t for t in self.trade_history if not t['is_win']]
        
        win_rate = len(wins) / len(self.trade_history) * 100 if self.trade_history else 0
        total_profit = sum(w['profit'] for w in wins)
        total_loss = sum(abs(l['profit']) for l in losses)
        
        # Analyze by symbol
        symbol_stats = {}
        for t in self.trade_history:
            sym = t['symbol']
            if sym not in symbol_stats:
                symbol_stats[sym] = {'wins': 0, 'losses': 0, 'profit': 0}
            if t['is_win']:
                symbol_stats[sym]['wins'] += 1
                symbol_stats[sym]['profit'] += t['profit']
            else:
                symbol_stats[sym]['losses'] += 1
                symbol_stats[sym]['profit'] += t['profit']
        
        best_symbol = None
        best_win_rate = 0
        for sym, stats in symbol_stats.items():
            total = stats['wins'] + stats['losses']
            if total >= 3:
                wr = stats['wins'] / total * 100
                if wr > best_win_rate:
                    best_win_rate = wr
                    best_symbol = sym
        
        self.current_stats = {
            'total_trades': len(self.trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 1),
            'net_profit': round(total_profit - total_loss, 2),
            'avg_win': round(total_profit / len(wins), 2) if wins else 0,
            'avg_loss': round(total_loss / len(losses), 2) if losses else 0,
            'best_symbol': best_symbol,
            'best_symbol_win_rate': round(best_win_rate, 1) if best_symbol else 0
        }
        
        return self.current_stats
    
    def get_updates(self):
        """DISABLED - Intelligence Hub handles Telegram routing"""
        return True
    
    def process_command(self, msg):
        msg_lower = msg.lower().strip()
        
        logger.info(f"Processing: {msg_lower}")
        
        if msg_lower == "learn":
            self.cmd_learn()
        elif msg_lower == "insights":
            self.cmd_insights()
        elif msg_lower == "improve":
            self.cmd_improve()
        elif msg_lower == "stats":
            self.cmd_stats()
        elif msg_lower == "memory":
            self.cmd_memory()
        elif msg_lower == "reflect":
            self.cmd_reflect()
        elif msg_lower == "help":
            self.cmd_help()
        else:
            self.send(f"Unknown: {msg_lower}\nTry: learn, insights, improve, stats, memory, reflect, help")
    
    def cmd_learn(self):
        self.fetch_recent_trades()
        stats = self.analyze_performance()
        
        message = f"📊 LEARNING SUMMARY\n"
        message += f"Total Trades: {stats['total_trades']}\n"
        message += f"Wins: {stats['wins']} | Losses: {stats['losses']}\n"
        message += f"Win Rate: {stats['win_rate']}%\n"
        message += f"Net Profit: ${stats['net_profit']:+.2f}\n"
        message += f"Avg Win: +${stats['avg_win']} | Avg Loss: -${stats['avg_loss']}"
        
        if stats.get('best_symbol'):
            message += f"\n\n🏆 Best Symbol: {stats['best_symbol']} ({stats['best_symbol_win_rate']}% win rate)"
        
        self.send(message)
    
    def cmd_stats(self):
        stats = self.analyze_performance()
        self.send(f"📊 TRADING STATS\nTrades: {stats['total_trades']}\nWins: {stats['wins']}\nWin Rate: {stats['win_rate']}%\nNet Profit: ${stats['net_profit']:+.2f}")
    
    def cmd_insights(self):
        stats = self.analyze_performance()
        
        prompt = f"""Based on {stats['total_trades']} trades with {stats['win_rate']}% win rate and ${stats['net_profit']:+.2f} profit:

Give 3 short, actionable trading insights. Keep each under 100 characters."""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=200
            )
            insights = response.choices[0].message.content
            
            # Save to Obsidian
            memory.save_insight({
                'source': 'Teacher Agent',
                'title': f"Performance Insights - {datetime.now().strftime('%Y-%m-%d')}",
                'content': insights,
                'confidence': stats['win_rate'],
                'suggested_action': 'Review and adjust strategy based on insights'
            })
            
            self.send(f"📈 INSIGHTS:\n{insights}\n\n💾 Saved to Obsidian vault")
        except Exception as e:
            self.send(f"📈 INSIGHTS\nWin Rate: {stats['win_rate']}%\nNet Profit: ${stats['net_profit']:+.2f}")
    
    def cmd_improve(self):
        stats = self.analyze_performance()
        
        suggestions = []
        if stats['win_rate'] < 50:
            suggestions.append("❌ Win rate below 50% - reduce position sizes")
        elif stats['win_rate'] > 70:
            suggestions.append(f"✅ Excellent win rate! Consider scaling up")
        
        if stats.get('best_symbol'):
            suggestions.append(f"🎯 Focus more on {stats['best_symbol']} - your best performer")
        
        if suggestions:
            self.send("💡 IMPROVEMENT SUGGESTIONS:\n" + "\n".join(suggestions))
        else:
            self.send("✅ Performance looks good. Continue current strategy.")
    
    def cmd_reflect(self):
        """Self-reflection - read past insights and learn"""
        self.send("🧠 Reflecting on past performance...")
        
        # Read recent insights from Obsidian
        recent_insights = memory.get_recent_insights(5)
        recent_trades = memory.get_recent_trades(10)
        
        if not recent_insights:
            self.send("No past insights found in memory. Run 'insights' first.")
            return
        
        prompt = f"""Based on these past insights and recent trades:

Insights:
{chr(10).join(recent_insights[:3])}

Recent trades summary: {len(recent_trades)} trades

What should I learn from this? Provide 2 specific improvements for my trading strategy.
Keep it short and actionable."""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=300
            )
            reflection = response.choices[0].message.content
            
            # Save reflection as insight
            memory.save_insight({
                'source': 'Self-Reflection',
                'title': f"Reflection - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
                'content': reflection,
                'confidence': 80,
                'suggested_action': 'Implement these improvements'
            })
            
            self.send(f"🧠 SELF-REFLECTION:\n{reflection}\n\n💾 Saved to memory")
        except Exception as e:
            self.send(f"Reflection error: {e}")
    
    def cmd_memory(self):
        self.send(f"🧠 MEMORY STATUS\n"
                  f"Trades stored: {len(self.trade_history)}\n"
                  f"Lessons: {len(self.lessons_learned)}\n"
                  f"Memory path: {self.memory_path}\n"
                  f"Obsidian vault: C:\\trading-memory\\obsidian-vault")
    
    def cmd_help(self):
        help_text = """🧠 TEACHER AGENT COMMANDS

learn - Analyze all trades
insights - AI trading insights (saved to Obsidian)
improve - Improvement suggestions
stats - Performance statistics
memory - Memory status
reflect - Self-reflection (reads past insights)
help - This menu

The teacher agent analyzes your trading history and provides insights.
All insights are saved to Obsidian vault for self-reflection."""
        self.send(help_text)
    
    def run(self):
        logger.info("Teacher agent running in background mode (Telegram disabled)")

        try:
            while True:
                # Background task: periodically fetch and analyze trades
                self.cmd_learn()
                time.sleep(300)  # Learn every 5 minutes

                # Periodic insights generation
                self.cmd_insights()
                time.sleep(600)  # Generate insights every 10 minutes

                # Improvement suggestions
                self.cmd_improve()
                time.sleep(900)  # Suggest improvements every 15 minutes
        except KeyboardInterrupt:
            logger.info("Teacher agent stopped")
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    agent = TeacherAgent()
    agent.run()