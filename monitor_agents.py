"""
AGENT MONITOR - Real-time status logging for Intelligence Hub and Ultimate Trader
Writes detailed logs that can be read remotely
"""

import subprocess
import time
import json
import psutil
from datetime import datetime
import os
from pathlib import Path

# Create logs directory
log_dir = Path("C:/trading-memory/agent_logs")
log_dir.mkdir(parents=True, exist_ok=True)

status_log = log_dir / "agent_status.log"
error_log = log_dir / "agent_errors.log"

def log_status(msg):
    """Write to status log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] {msg}"
    print(log_msg)
    with open(status_log, "a") as f:
        f.write(log_msg + "\n")

def log_error(msg):
    """Write to error log"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_msg = f"[{timestamp}] ERROR: {msg}"
    print(log_msg)
    with open(error_log, "a") as f:
        f.write(log_msg + "\n")

def check_process(script_name):
    """Check if a Python script is running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
            if script_name in cmdline and 'python' in cmdline.lower():
                return True, proc.info['pid']
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False, None

def start_agent(script_name):
    """Start an agent in a new window"""
    try:
        project_dir = Path("C:/Users/Administrator/Desktop/DS trading agent")
        subprocess.Popen(
            f'start cmd /c "cd {project_dir} && py {script_name}"',
            shell=True
        )
        log_status(f"Started {script_name}")
        return True
    except Exception as e:
        log_error(f"Failed to start {script_name}: {e}")
        return False

def get_mt5_status():
    """Check MT5 connection status"""
    try:
        import MetaTrader5 as mt5
        info = mt5.terminal_info()
        if info:
            return True, f"MT5 Connected - Account: {mt5.account_info().login if mt5.account_info() else 'N/A'}"
        else:
            return False, "MT5 Not Connected"
    except Exception as e:
        return False, f"MT5 Error: {str(e)[:50]}"

def get_telegram_status():
    """Check if telegram messages are being received"""
    try:
        from config import Config
        Config.validate_credentials()
        return True, f"Telegram configured - Chat ID: {Config.TELEGRAM_CHAT_ID}"
    except Exception as e:
        return False, f"Telegram Error: {str(e)[:50]}"

def main():
    log_status("=" * 80)
    log_status("AGENT MONITOR STARTED")
    log_status("=" * 80)

    agents = {
        "intelligence_hub.py": "Telegram Listener + Conversational Router",
        "ultimate_trader.py": "Autonomous Trading Brain"
    }

    check_interval = 10  # Check every 10 seconds

    while True:
        try:
            # Check each agent
            for script_name, description in agents.items():
                running, pid = check_process(script_name)
                status_emoji = "✅" if running else "❌"
                log_status(f"{status_emoji} {script_name} ({description}) - PID: {pid if pid else 'N/A'}")

                if not running:
                    log_status(f"   Attempting to restart {script_name}...")
                    start_agent(script_name)

            # Check system status
            mem = psutil.virtual_memory()
            log_status(f"System Memory: {mem.percent}% used")

            # Check MT5
            mt5_connected, mt5_msg = get_mt5_status()
            log_status(f"MT5: {'✅' if mt5_connected else '❌'} {mt5_msg}")

            # Check Telegram
            tg_ok, tg_msg = get_telegram_status()
            log_status(f"Telegram: {'✅' if tg_ok else '❌'} {tg_msg}")

            log_status("-" * 80)
            time.sleep(check_interval)

        except Exception as e:
            log_error(f"Monitor error: {e}")
            time.sleep(check_interval)

if __name__ == "__main__":
    main()
