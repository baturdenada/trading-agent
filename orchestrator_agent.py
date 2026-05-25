"""
ORCHESTRATOR AGENT - Monitors all agents, updates code, reports status
Central command and control for the entire trading ecosystem
"""

import logging
import time
import json
import subprocess
import psutil
import requests
from datetime import datetime
import os
from dotenv import load_dotenv
from api_helper import send_telegram_reliable
from config import Config

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s', datefmt='%H:%M:%S')
logger = logging.getLogger(__name__)
load_dotenv()

class OrchestratorAgent:
    def __init__(self):
        # Load configuration
        Config.validate_credentials()

        # Telegram (main bot - @BatsDeepSeekTraderBot)
        self.telegram_token = Config.TELEGRAM_TOKEN
        self.telegram_chat_id = Config.TELEGRAM_CHAT_ID

        self.last_update_id = 0

        # Memory
        self.memory_path = Config.TRADING_MEMORY_PATH
        
        # Agent status tracking
        self.agents = {
            'main_trading': {'script': 'ultimate_trader.py', 'status': 'unknown', 'pid': None},
            'teacher': {'script': 'teacher_agent.py', 'status': 'unknown', 'pid': None},
            'strategy': {'script': 'strategy_agent.py', 'status': 'unknown', 'pid': None},
            'news': {'script': 'news_agent.py', 'status': 'unknown', 'pid': None}
        }
        
        self.alert_cooldown = {}
        
        logger.info("Orchestrator Agent initialized")
        self.send("🎛️ ORCHESTRATOR ONLINE\nMonitoring all agents\nCommands: status, restart, update, report, help")
    
    def send(self, msg):
        send_telegram_reliable(self.telegram_token, self.telegram_chat_id, msg, max_retries=2)
    
    def check_agent_status(self):
        """Check if each agent is running"""
        for name, info in self.agents.items():
            script = info['script']
            # Find process running the script
            found = False
            for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
                try:
                    cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                    if script in cmdline and 'python' in cmdline.lower():
                        found = True
                        info['status'] = 'running'
                        info['pid'] = proc.info['pid']
                        break
                except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess) as e:
                    logger.debug(f"Process query error for {script}: {e}")
                except Exception as e:
                    logger.error(f"Unexpected error checking process {script}: {e}")
            if not found:
                info['status'] = 'stopped'
                info['pid'] = None

        return self.agents
    
    def restart_agent(self, agent_name):
        """Restart a specific agent"""
        if agent_name not in self.agents:
            return f"Unknown agent: {agent_name}"

        script = self.agents[agent_name]['script']
        script_path = str(Config.PROJECT_ROOT / script)

        # Kill existing process
        for proc in psutil.process_iter(['pid', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                if script in cmdline:
                    proc.kill()
            except:
                pass

        # Start new process in new window
        project_root = str(Config.PROJECT_ROOT)
        subprocess.Popen(f'start cmd /c "cd {project_root} && py {script}"', shell=True)

        return f"Restarting {agent_name}..."
    
    def get_system_status(self):
        """Get overall system status"""
        self.check_agent_status()
        
        status = "🎛️ SYSTEM STATUS\n\n"
        for name, info in self.agents.items():
            emoji = "✅" if info['status'] == 'running' else "❌"
            status += f"{emoji} {name.upper()}: {info['status']}\n"
        
        # Memory usage
        memory = psutil.virtual_memory()
        status += f"\n💾 RAM: {memory.percent}% used"
        
        # Uptime
        boot_time = datetime.fromtimestamp(psutil.boot_time())
        uptime = datetime.now() - boot_time
        status += f"\n⏰ Uptime: {str(uptime).split('.')[0]}"
        
        return status
    
    def generate_daily_report(self):
        """Generate daily report of all agents"""
        self.check_agent_status()
        
        report = "📊 DAILY TRADING REPORT\n"
        report += f"Date: {datetime.now().strftime('%Y-%m-%d')}\n\n"
        
        for name, info in self.agents.items():
            report += f"• {name}: {info['status']}\n"
        
        # Read trade stats from memory
        trade_file = os.path.join(self.memory_path, "trade_history.json")
        if os.path.exists(trade_file):
            with open(trade_file, 'r') as f:
                trades = json.load(f)
            wins = len([t for t in trades if t.get('is_win', False)])
            report += f"\n📈 Today's Trades: {len(trades)}\nWin Rate: {wins/len(trades)*100:.1f}%" if trades else "\nNo trades today"
        
        return report
    
    def get_updates(self):
        """DISABLED - Intelligence Hub handles Telegram routing"""
        return True
    
    def process_command(self, msg):
        if msg == "status":
            self.send(self.get_system_status())
        elif msg == "report":
            self.send(self.generate_daily_report())
        elif msg.startswith("restart"):
            parts = msg.split()
            if len(parts) > 1:
                self.send(self.restart_agent(parts[1]))
            else:
                self.send("Usage: restart [agent_name]\nAgents: main_trading, teacher, strategy, news")
        elif msg == "help":
            self.cmd_help()
        else:
            self.send("Commands: status, report, restart [agent], help")
    
    def cmd_help(self):
        help_text = """🎛️ ORCHESTRATOR COMMANDS

status - All agent statuses
report - Daily performance report
restart [agent] - Restart specific agent
help - This menu

AGENTS:
• main_trading - Live trading
• teacher - Learning/analysis
• strategy - New strategies
• news - Market news

The orchestrator monitors all agents 24/7."""
        self.send(help_text)
    
    def run(self):
        logger.info("Orchestrator running in background mode (Telegram disabled)")

        # Send daily report at 00:00 GMT
        last_report_date = None

        try:
            while True:
                # Daily report at midnight
                today = datetime.now().strftime('%Y-%m-%d')
                if last_report_date != today:
                    report = self.generate_daily_report()
                    logger.info(f"Daily report:\n{report}")
                    last_report_date = today

                # Check if any agent died and alert if needed
                self.check_agent_status()
                for name, info in self.agents.items():
                    if info['status'] == 'stopped':
                        cooldown_key = f"{name}_alert"
                        if cooldown_key not in self.alert_cooldown or \
                           (datetime.now() - self.alert_cooldown[cooldown_key]).seconds > 3600:
                            logger.warning(f"⚠️ ALERT: {name} agent is stopped!")
                            self.alert_cooldown[cooldown_key] = datetime.now()

                time.sleep(30)  # Check every 30 seconds
        except KeyboardInterrupt:
            logger.info("Orchestrator stopped")

if __name__ == "__main__":
    agent = OrchestratorAgent()
    agent.run()