"""
AGENT WEBHOOK UPLOADER
Runs on VPS - continuously sends agent status and logs to remote webhook
Allows me to monitor everything remotely without VPS access
"""

import subprocess
import json
import time
import psutil
import requests
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

# WEBHOOK URL - change this to where logs are sent
WEBHOOK_URL = "https://webhook.site/bea315f4-eaa5-4c4f-9838-7add8cc702bd"

class AgentMonitor:
    def __init__(self):
        self.log_dir = Path("C:/trading-memory/agent_logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.status_log = self.log_dir / "agent_status.log"
        self.error_log = self.log_dir / "agent_errors.log"

    def check_process(self, script_name):
        """Check if process is running"""
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                if script_name in cmdline and 'python' in cmdline.lower():
                    return {'running': True, 'pid': proc.info['pid']}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {'running': False, 'pid': None}

    def get_recent_logs(self, log_file, lines=30):
        """Get recent log lines"""
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    return f.readlines()[-lines:]
        except:
            pass
        return []

    def get_status(self):
        """Get complete system status"""
        return {
            'timestamp': datetime.now().isoformat(),
            'intelligence_hub': self.check_process('intelligence_hub.py'),
            'ultimate_trader': self.check_process('ultimate_trader.py'),
            'system': {
                'memory_percent': psutil.virtual_memory().percent,
                'cpu_percent': psutil.cpu_percent(interval=1)
            },
            'logs': {
                'status': [l.strip() for l in self.get_recent_logs(self.status_log, 20)],
                'errors': [l.strip() for l in self.get_recent_logs(self.error_log, 10)]
            }
        }

    def send_status(self):
        """Send status to webhook and write to local JSON"""
        try:
            status = self.get_status()

            # Write to local JSON file
            status_file = Path('C:/trading-memory/agent_status.json')
            with open(status_file, 'w') as f:
                json.dump(status, f, indent=2)

            # Also try webhook
            try:
                response = requests.post(WEBHOOK_URL, json=status, timeout=10)
                logger.debug(f"Status sent to webhook: {response.status_code}")
            except:
                pass

        except Exception as e:
            logger.error(f"Failed to send status: {e}")

    def run(self):
        """Continuously send status"""
        logger.info("Agent Monitor started - sending status every 10 seconds")
        while True:
            try:
                self.send_status()
                time.sleep(10)
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                time.sleep(10)

if __name__ == "__main__":
    monitor = AgentMonitor()
    monitor.run()
