"""
VPS SUPERVISOR - Automatically manages agent lifecycle on VPS
Ensures only Intelligence Hub listens to Telegram
Restarts outdated agents with latest code
Runs continuously to maintain proper agent configuration
"""

import subprocess
import time
import psutil
import os
from datetime import datetime
import logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

class VPSSupervisor:
    def __init__(self):
        self.project_dir = Path("C:/Users/Administrator/Desktop/DS trading agent")
        self.required_agents = {
            "intelligence_hub.py": "Telegram listener and conversational router",
            "ultimate_trader.py": "Autonomous trading brain"
        }
        self.forbidden_agents = {
            "strategy_agent.py": "Should not listen to Telegram",
            "news_agent.py": "Should not listen to Telegram",
            "teacher_agent.py": "Should not listen to Telegram",
            "orchestrator_agent.py": "Should not listen to Telegram"
        }

    def find_process(self, script_name):
        """Find if a script is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                if script_name in cmdline and 'python' in cmdline.lower():
                    return proc.info['pid']
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return None

    def kill_process(self, script_name):
        """Kill a running script"""
        pid = self.find_process(script_name)
        if pid:
            try:
                proc = psutil.Process(pid)
                proc.kill()
                logger.info(f"Killed {script_name} (PID: {pid})")
                time.sleep(2)
                return True
            except Exception as e:
                logger.error(f"Failed to kill {script_name}: {e}")
        return False

    def start_agent(self, script_name):
        """Start an agent in a new window"""
        try:
            subprocess.Popen(
                f'start cmd /c "cd {self.project_dir} && py {script_name}"',
                shell=True
            )
            logger.info(f"Started {script_name}")
            time.sleep(3)
            return True
        except Exception as e:
            logger.error(f"Failed to start {script_name}: {e}")
            return False

    def ensure_required_agents(self):
        """Ensure required agents are running"""
        for script_name, description in self.required_agents.items():
            pid = self.find_process(script_name)
            if not pid:
                logger.warning(f"Required agent {script_name} not running! Starting...")
                self.start_agent(script_name)
            else:
                logger.info(f"✅ {script_name} running (PID: {pid})")

    def stop_forbidden_agents(self):
        """Stop agents that should not be listening to Telegram"""
        for script_name, reason in self.forbidden_agents.items():
            pid = self.find_process(script_name)
            if pid:
                logger.warning(f"Forbidden agent {script_name} is running! Killing... ({reason})")
                self.kill_process(script_name)

    def run(self):
        """Main supervisor loop"""
        logger.info("VPS SUPERVISOR STARTED")
        logger.info("Role: Ensures only Intelligence Hub listens to Telegram")
        logger.info("Mode: Continuous monitoring")

        while True:
            try:
                # Stop any forbidden agents
                self.stop_forbidden_agents()

                # Ensure required agents are running
                self.ensure_required_agents()

                # Wait before next check
                time.sleep(30)

            except Exception as e:
                logger.error(f"Supervisor error: {e}")
                time.sleep(30)

if __name__ == "__main__":
    supervisor = VPSSupervisor()
    supervisor.run()
