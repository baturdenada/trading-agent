"""
AUTO-UPDATER - Runs continuously on VPS
Automatically syncs files from HTTP server and restarts agents
Requires: HTTP server running on port 8888
"""

import os
import time
import subprocess
import psutil
import hashlib
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

class AutoUpdater:
    def __init__(self):
        self.project_dir = Path("C:/Users/Administrator/Desktop/DS trading agent")
        self.local_hashes = {}

        # Agents to manage
        self.agents = {
            "intelligence_hub.py": "required",
            "ultimate_trader.py": "required",
            "strategy_agent.py": "forbidden",
            "news_agent.py": "forbidden",
            "teacher_agent.py": "forbidden",
            "orchestrator_agent.py": "forbidden"
        }

    def get_file_hash(self, filepath):
        """Get hash of file for change detection"""
        try:
            if not filepath.exists():
                return None
            with open(filepath, 'rb') as f:
                return hashlib.md5(f.read()).hexdigest()
        except:
            return None

    def check_updates(self):
        """Check if any agent files have changed"""
        changes = {}
        for agent_name in self.agents:
            filepath = self.project_dir / agent_name
            current_hash = self.get_file_hash(filepath)

            if agent_name not in self.local_hashes:
                self.local_hashes[agent_name] = current_hash
            elif self.local_hashes[agent_name] != current_hash:
                changes[agent_name] = "updated"
                self.local_hashes[agent_name] = current_hash
                logger.info(f"Detected update: {agent_name}")

        return changes

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
                psutil.Process(pid).kill()
                logger.info(f"Killed {script_name} (PID: {pid})")
                time.sleep(2)
                return True
            except Exception as e:
                logger.error(f"Failed to kill {script_name}: {e}")
        return False

    def start_agent(self, script_name):
        """Start an agent"""
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

    def apply_updates(self, changes):
        """Apply detected updates by restarting affected agents"""
        # Kill forbidden agents (they should never run)
        for agent_name, agent_type in self.agents.items():
            if agent_type == "forbidden":
                if self.find_process(agent_name):
                    logger.warning(f"Killing forbidden agent: {agent_name}")
                    self.kill_process(agent_name)

        # Restart required agents that were updated
        for agent_name in changes:
            if self.agents.get(agent_name) == "required":
                logger.info(f"Restarting updated agent: {agent_name}")
                self.kill_process(agent_name)
                time.sleep(1)
                self.start_agent(agent_name)

    def ensure_required_running(self):
        """Ensure all required agents are running"""
        for agent_name, agent_type in self.agents.items():
            if agent_type == "required":
                if not self.find_process(agent_name):
                    logger.warning(f"Required agent {agent_name} is not running! Starting...")
                    self.start_agent(agent_name)
                else:
                    logger.debug(f"✅ {agent_name} running")

    def ensure_webhook_uploader_running(self):
        """Ensure webhook uploader is always running for monitoring"""
        if not self.find_process("agent_webhook_uploader.py"):
            logger.warning("Webhook uploader not running! Starting...")
            self.start_agent("agent_webhook_uploader.py")
        else:
            logger.debug("✅ agent_webhook_uploader.py running")

    def run(self):
        """Main auto-updater loop"""
        logger.info("=" * 80)
        logger.info("AUTO-UPDATER STARTED")
        logger.info("=" * 80)
        logger.info("Role: Automatically sync files and manage agents")
        logger.info("Monitoring: intelligence_hub, ultimate_trader, agent_webhook_uploader")
        logger.info("")

        while True:
            try:
                # Check for file updates
                changes = self.check_updates()
                if changes:
                    logger.info(f"Applying {len(changes)} updates...")
                    self.apply_updates(changes)

                # Ensure required agents are running
                self.ensure_required_running()

                # Ensure webhook uploader is running (critical for monitoring)
                self.ensure_webhook_uploader_running()

                # Kill any forbidden agents that started
                for agent_name, agent_type in self.agents.items():
                    if agent_type == "forbidden":
                        if self.find_process(agent_name):
                            logger.warning(f"Killing forbidden agent: {agent_name}")
                            self.kill_process(agent_name)

                # Check every 30 seconds
                time.sleep(30)

            except Exception as e:
                logger.error(f"Auto-updater error: {e}")
                time.sleep(30)

if __name__ == "__main__":
    updater = AutoUpdater()
    updater.run()
