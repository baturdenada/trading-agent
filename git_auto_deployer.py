"""
GIT AUTO DEPLOYER - Runs on VPS
Continuously pulls latest code from GitHub and restarts agents
Ensures VPS always has latest trading agent code
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

class GitAutoDeployer:
    def __init__(self):
        self.project_dir = Path("C:/Users/Administrator/Desktop/DS trading agent")
        self.repo_url = "https://github.com/baturdenada/trading-agent.git"
        self.local_commit_hash = None

        # Agents to manage
        self.agents = {
            "intelligence_hub.py": "required",
            "ultimate_trader.py": "required",
            "strategy_agent.py": "forbidden",
            "news_agent.py": "forbidden",
            "teacher_agent.py": "forbidden",
            "orchestrator_agent.py": "forbidden"
        }

    def get_current_commit(self):
        """Get current git commit hash"""
        try:
            result = subprocess.run(
                "git rev-parse HEAD",
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                shell=True
            )
            return result.stdout.strip() if result.returncode == 0 else None
        except:
            return None

    def pull_latest(self):
        """Pull latest code from GitHub"""
        try:
            logger.info("Pulling latest code from GitHub...")
            result = subprocess.run(
                "git pull origin main",
                cwd=self.project_dir,
                capture_output=True,
                text=True,
                shell=True,
                timeout=30
            )

            if result.returncode == 0:
                logger.info("✅ Code pulled successfully")
                return True
            else:
                logger.error(f"Git pull failed: {result.stderr}")
                return False
        except Exception as e:
            logger.error(f"Failed to pull code: {e}")
            return False

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

    def restart_required_agents(self):
        """Restart all required agents"""
        for agent_name, agent_type in self.agents.items():
            if agent_type == "required":
                logger.info(f"Restarting {agent_name}...")
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

    def ensure_webhook_uploader_running(self):
        """Ensure webhook uploader is always running"""
        if not self.find_process("agent_webhook_uploader.py"):
            logger.warning("Webhook uploader not running! Starting...")
            self.start_agent("agent_webhook_uploader.py")

    def run(self):
        """Main deployer loop"""
        logger.info("=" * 80)
        logger.info("GIT AUTO DEPLOYER STARTED")
        logger.info("=" * 80)
        logger.info(f"Repo: {self.repo_url}")
        logger.info("Role: Pull latest code from GitHub and manage agents")
        logger.info("")

        # Initialize repo if not already initialized
        if not (self.project_dir / ".git").exists():
            logger.info("Initializing git repository...")
            subprocess.run(
                f"git clone {self.repo_url} .",
                cwd=self.project_dir,
                shell=True,
                capture_output=True
            )

        self.local_commit_hash = self.get_current_commit()

        while True:
            try:
                # Check for updates from GitHub
                new_commit = self.get_current_commit()
                self.pull_latest()
                updated_commit = self.get_current_commit()

                # If code changed, restart agents
                if self.local_commit_hash and updated_commit != self.local_commit_hash:
                    logger.info(f"Code updated! ({self.local_commit_hash[:8]} → {updated_commit[:8]})")
                    logger.info("Restarting all required agents...")
                    self.restart_required_agents()
                    self.local_commit_hash = updated_commit

                # Ensure required agents are running
                self.ensure_required_running()

                # Ensure webhook uploader is running
                self.ensure_webhook_uploader_running()

                # Kill any forbidden agents
                for agent_name, agent_type in self.agents.items():
                    if agent_type == "forbidden":
                        if self.find_process(agent_name):
                            logger.warning(f"Killing forbidden agent: {agent_name}")
                            self.kill_process(agent_name)

                # Check every 60 seconds
                time.sleep(60)

            except Exception as e:
                logger.error(f"Deployer error: {e}")
                time.sleep(60)

if __name__ == "__main__":
    deployer = GitAutoDeployer()
    deployer.run()
