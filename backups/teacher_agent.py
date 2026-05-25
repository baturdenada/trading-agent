"""
Teacher Agent - Learns from past trades, improves strategies, stores memory
Runs alongside main trading agent
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

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class TeacherAgent:
    def __init__(self):
        self.client = OpenAI(api_key=os.getenv("DEEPSEEK_API_KEY"), base_url="https://api.deepseek.com")
        
        # MT5
        self.login = int(os.getenv("MT5_LOGIN", 0))
        self.password = os.getenv("MT5_PASSWORD", "")
        self.server = os.getenv("MT5_SERVER", "")
        self.path = os.getenv("MT5_PATH", "")
        
        # Telegram
        self.telegram_token = "8950742927:AAGhHdDZic9CsQCjL7m4zhxLPEY1Q3KcK5E"
        self.telegram_chat_id = "832734789"
        self.last_update_id = 0
        
        # Memory storage
        self.memory_path = "C:\\Users\\Administrator\\Desktop\\DS trading agent\\memory"
        os.makedirs(self.memory_path, exist_ok=True)
        
        # Learning data
        self.trade_history = []
        self.lessons_learned = []
        self.strategy_insights = []
        
        self.load_memory()
        
        logger.info("Teacher Agent initialized")
        self.send("🧠 TEACHER AGENT ONLINE\nI learn from every trade and improve strategies.\nCommands: learn, insights, improve, memory")
    
    def send(self, msg):
        try:
            url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
            requests.post(url, json={"chat_id": self.telegram_chat_id, "text": msg}, timeout=10)
        except Exception as e:
            logger.error(f"Send error: {e}")
    
    def load_memory(self):
        """Load all past trades and lessons"""
        try:
            # Load trade history
            trade_file = os.path.join(self.memory_path, "trade_history.json")
            if os.path.exists(trade_file):
                with open(trade_file, 'r') as f:
                    self.trade_history = json.load(f)
            
            # Load lessons
            lessons_file = os.path.join(self.memory_path, "lessons.json")
            if os.path.exists(lessons_file):
                with open(lessons_file, 'r') as f:
                    self.lessons_learned = json.load(f)
            
            logger.info(f"Loaded {len(self.trade_history)} trades, {len(self.lessons_learned)} lessons")
        except Exception as e:
            logger.error(f"Memory load error: {e}")
    
    def save_memory(self):
        """Save all data to memory"""
        try:
            trade_file = os.path.join(self.memory_path, "trade_history.json")
            with open(trade_file, 'w') as f:
                json.dump(self.trade_history[-500:], f, indent=2)
            
            lessons_file = os.path.join(self.memory_path, "lessons.json")
            with open(lessons_file, 'w') as f:
                json.dump(self.lessons_learned[-100:], f, indent=2)
            
            logger.info("Memory saved")
        except Exception as e:
            logger.error(f"Save error: {e}")
    
    def fetch_recent_trades(self):
        """Get all trades from MT5 history"""
        from_date = int((datetime.now() - timedelta(days=7)).timestamp())
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
                    
                    # Check if already stored
                    if not any(t.get('ticket') == deal.ticket for t in self.trade_history):
                        new_trades.append(trade)
        
        if new_trades:
            self.trade_history.extend(new_trades)
            self.save_memory()
            logger.info(f"Added {len(new_trades)} new trades")
        
        return new_trades
    
    def analyze_performance(self):
        """Analyze trade performance for patterns"""
        if not self.trade_history:
            return "Not enough trades yet"
        
        wins = [t for t in self.trade_history if t['is_win']]
        losses = [t for t in self.trade_history if not t['is_win']]
        
        win_rate = len(wins) / len(self.trade_history) * 100 if self.trade_history else 0
        avg_win = sum(w['profit'] for w in wins) / len(wins) if wins else 0
        avg_loss = sum(l['profit'] for l in losses) / len(losses) if losses else 0
        
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
        
        # Analyze by hour
        hour_stats = {}
        for t in self.trade_history:
            try:
                hour = datetime.fromisoformat(t['time']).hour
                if hour not in hour_stats:
                    hour_stats[hour] = {'wins': 0, 'losses': 0}
                if t['is_win']:
                    hour_stats[hour]['wins'] += 1
                else:
                    hour_stats[hour]['losses'] += 1
            except:
                pass
        
        best_hour = None
        best_hour_wr = 0
        for hour, stats in hour_stats.items():
            total = stats['wins'] + stats['losses']
            if total >= 2:
                wr = stats['wins'] / total * 100
                if wr > best_hour_wr:
                    best_hour_wr = wr
                    best_hour = hour
        
        analysis = {
            'total_trades': len(self.trade_history),
            'wins': len(wins),
            'losses': len(losses),
            'win_rate': round(win_rate, 1),
            'avg_win': round(avg_win, 2),
            'avg_loss': round(avg_loss, 2),
            'profit_factor': round(abs(sum(w['profit'] for w in wins) / sum(l['profit'] for l in losses)), 2) if losses else 999,
            'best_symbol': best_symbol,
            'best_symbol_win_rate': round(best_win_rate, 1) if best_symbol else 0,
            'best_hour': best_hour,
            'best_hour_win_rate': round(best_hour_wr, 1) if best_hour else 0
        }
        
        return analysis
    
    def generate_insights(self):
        """Generate trading insights using AI"""
        analysis = self.analyze_performance()
        
        prompt = f"""Based on this trading performance data:

Total Trades: {analysis['total_trades']}
Win Rate: {analysis['win_rate']}%
Average Win: ${analysis['avg_win']}
Average Loss: ${analysis['avg_loss']}
Profit Factor: {analysis['profit_factor']}
Best Symbol: {analysis['best_symbol']} ({analysis['best_symbol_win_rate']}% win rate)
Best Hour: {analysis['best_hour']}:00 ({analysis['best_hour_win_rate']}% win rate)

Provide 3 actionable insights to improve trading:
1. What is working well?
2. What needs improvement?
3. Specific recommendation for next week

Keep each insight under 100 characters."""
        
        try:
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5,
                max_tokens=300
            )
            
            insights = response.choices[0].message.content
            return insights
        except Exception as e:
            logger.error(f"Insight error: {e}")
            return "Unable to generate insights"
    
    def learn_from_trades(self):
        """Main learning loop - analyzes trades and generates lessons"""
        new_trades = self.fetch_recent_trades()
        
        if new_trades:
            analysis = self.analyze_performance()
            insights = self.generate_insights()
            
            lesson = {
                'timestamp': datetime.now().isoformat(),
                'new_trades': len(new_trades),
                'total_trades': analysis['total_trades'],
                'win_rate': analysis['win_rate'],
                'insights': insights
            }
            
            self.lessons_learned.append(lesson)
            self.save_memory()
            
            # Send important insights to Telegram
            if analysis['win_rate'] < 40 and analysis['total_trades'] > 10:
                self.send(f"⚠️ Learning Alert: Win rate dropped to {analysis['win_rate']}%\nConsider reducing position sizes.")
            elif analysis['win_rate'] > 60 and analysis['total_trades'] > 10:
                self.send(f"✅ Learning Alert: Win rate improved to {analysis['win_rate']}%\nStrategy is working!")
            
            logger.info(f"Learned from {len(new_trades)} new trades")
    
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
        
        if msg_lower == "learn":
            self.cmd_learn()
        elif msg_lower == "insights":
            self.cmd_insights()
        elif msg_lower == "improve":
            self.cmd_improve()
        elif msg_lower == "memory":
            self.cmd_memory()
        elif msg_lower == "help":
            self.cmd_help()
        else:
            self.send(f"Teacher commands: learn, insights, improve, memory, help")
    
    def cmd_learn(self):
        """Force learning from all trades"""
        self.send("📚 Analyzing trade history...")
        self.fetch_recent_trades()
        analysis = self.analyze_performance()
        
        message = f"📊 LEARNING SUMMARY\n"
        message += f"Total Trades: {analysis['total_trades']}\n"
        message += f"Win Rate: {analysis['win_rate']}%\n"
        message += f"Avg Win: +${analysis['avg_win']} | Avg Loss: -${analysis['avg_loss']}\n"
        message += f"Profit Factor: {analysis['profit_factor']}\n"
        
        if analysis['best_symbol']:
            message += f"\n🏆 Best Symbol: {analysis['best_symbol']} ({analysis['best_symbol_win_rate']}% win rate)"
        if analysis['best_hour']:
            message += f"\n⏰ Best Hour: {analysis['best_hour']}:00 ({analysis['best_hour_win_rate']}% win rate)"
        
        self.send(message)
    
    def cmd_insights(self):
        """Get AI-generated insights"""
        self.send("🧠 Generating insights...")
        insights = self.generate_insights()
        self.send(f"📈 INSIGHTS:\n{insights}")
    
    def cmd_improve(self):
        """Get improvement suggestions"""
        analysis = self.analyze_performance()
        
        suggestions = []
        if analysis['profit_factor'] < 1:
            suggestions.append("❌ Profit factor below 1 - reduce position sizes")
        if analysis['win_rate'] < 45:
            suggestions.append("⚠️ Win rate below 45% - review entry criteria")
        if analysis['best_symbol']:
            suggestions.append(f"✅ Focus more on {analysis['best_symbol']} - your best performer")
        if analysis['best_hour']:
            suggestions.append(f"⏰ Trade more during {analysis['best_hour']}:00 - highest win rate")
        
        if suggestions:
            self.send("💡 IMPROVEMENT SUGGESTIONS:\n" + "\n".join(suggestions))
        else:
            self.send("✅ Performance looks good! Continue current strategy.")
    
    def cmd_memory(self):
        """Show memory stats"""
        self.send(f"🧠 MEMORY STATUS\n"
                  f"Trades stored: {len(self.trade_history)}\n"
                  f"Lessons learned: {len(self.lessons_learned)}\n"
                  f"Memory path: {self.memory_path}")
    
    def cmd_help(self):
        help_text = """🧠 TEACHER AGENT COMMANDS

learn - Analyze all trades
insights - AI-generated trading insights
improve - Get improvement suggestions
memory - Show memory status
help - This menu

The teacher agent:
- Learns from every trade
- Identifies winning patterns
- Suggests improvements
- Stores all learnings"""
        self.send(help_text)
    
    def run(self):
        """Main loop"""
        if not mt5.initialize(path=self.path, login=self.login, password=self.password, server=self.server):
            self.send("MT5 connection failed")
            return
        
        self.send("🧠 TEACHER AGENT ONLINE\nI learn from every trade and improve strategies.\nCommands: learn, insights, improve, memory")
        logger.info("Teacher agent running")
        
        try:
            while True:
                self.get_updates()
                self.learn_from_trades()  # Learn every cycle
                time.sleep(3600)  # Learn every hour
        except KeyboardInterrupt:
            self.send("Teacher agent stopped")
            self.save_memory()
        finally:
            mt5.shutdown()

if __name__ == "__main__":
    agent = TeacherAgent()
    agent.run()