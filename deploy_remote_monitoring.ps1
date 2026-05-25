# DEPLOY_REMOTE_MONITORING.ps1
# One-command setup for remote monitoring on VPS
# Usage: .\deploy_remote_monitoring.ps1 -WebhookURL "https://webhook.site/your-id"

param(
    [string]$WebhookURL = "https://webhook.site/placeholder"
)

Write-Host "========================================" -ForegroundColor Green
Write-Host "REMOTE MONITORING DEPLOYMENT" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green

# 1. Create agent_webhook_uploader.py with correct webhook URL
$uploaderCode = @"
import subprocess, json, time, psutil, requests
from datetime import datetime
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

WEBHOOK_URL = "$WebhookURL"

class AgentMonitor:
    def __init__(self):
        self.log_dir = Path('C:/trading-memory/agent_logs')
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.status_log = self.log_dir / 'agent_status.log'
        self.error_log = self.log_dir / 'agent_errors.log'

    def check_process(self, script_name):
        for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
                if script_name in cmdline and 'python' in cmdline.lower():
                    return {'running': True, 'pid': proc.info['pid']}
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return {'running': False, 'pid': None}

    def get_recent_logs(self, log_file, lines=20):
        try:
            if log_file.exists():
                with open(log_file, 'r') as f:
                    return f.readlines()[-lines:]
        except:
            pass
        return []

    def get_status(self):
        return {
            'timestamp': datetime.now().isoformat(),
            'agents': {
                'intelligence_hub': self.check_process('intelligence_hub.py'),
                'ultimate_trader': self.check_process('ultimate_trader.py')
            },
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
        try:
            status = self.get_status()
            response = requests.post(WEBHOOK_URL, json=status, timeout=10)
            logger.debug(f'Status sent: {response.status_code}')
        except Exception as e:
            logger.warning(f'Failed to send status: {e}')

    def run(self):
        logger.info(f'Agent Monitor started - webhook: {WEBHOOK_URL}')
        while True:
            try:
                self.send_status()
                time.sleep(10)
            except Exception as e:
                logger.error(f'Monitor error: {e}')
                time.sleep(10)

if __name__ == '__main__':
    monitor = AgentMonitor()
    monitor.run()
"@

$uploaderPath = "C:\Users\Administrator\Desktop\DS trading agent\agent_webhook_uploader.py"
$uploaderCode | Out-File -FilePath $uploaderPath -Encoding UTF8 -Force
Write-Host "✅ Created agent_webhook_uploader.py with webhook URL" -ForegroundColor Green

# 2. Start the webhook uploader in a new window
Write-Host "Starting Agent Monitor in new window..." -ForegroundColor Yellow
$monitorProc = Start-Process -FilePath "py" -ArgumentList $uploaderPath -WindowStyle Normal -PassThru
Write-Host "✅ Agent Monitor started (PID: $($monitorProc.Id))" -ForegroundColor Green

# 3. Create a status check script
$checkCode = @"
import psutil
import json

def check_agents():
    hub = False
    trader = False

    for proc in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] or [])
            if 'intelligence_hub.py' in cmdline: hub = True
            if 'ultimate_trader.py' in cmdline: trader = True
        except: pass

    return {'intelligence_hub': hub, 'ultimate_trader': trader, 'webhook': '$WebhookURL'}

if __name__ == '__main__':
    status = check_agents()
    print(json.dumps(status, indent=2))
"@

$checkPath = "C:\Users\Administrator\Desktop\DS trading agent\check_status.py"
$checkCode | Out-File -FilePath $checkPath -Encoding UTF8 -Force

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Monitor is now running and sending status to:" -ForegroundColor Cyan
Write-Host "$WebhookURL" -ForegroundColor Yellow
Write-Host ""
Write-Host "To verify, visit the webhook URL and you should see incoming POSTs" -ForegroundColor Cyan
Write-Host ""
Write-Host "Remote monitoring is now ACTIVE" -ForegroundColor Green
