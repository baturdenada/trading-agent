"""
STATUS SERVER - HTTP endpoint for monitoring agents
Runs on VPS and exposes real-time status via HTTP
"""

from flask import Flask, jsonify
import psutil
import subprocess
from datetime import datetime
from pathlib import Path
import json

app = Flask(__name__)

def check_process(script_name):
    """Check if a Python script is running"""
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline'] if proc.info['cmdline'] else [])
            if script_name in cmdline and 'python' in cmdline.lower():
                return {
                    'running': True,
                    'pid': proc.info['pid'],
                    'name': script_name
                }
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return {
        'running': False,
        'pid': None,
        'name': script_name
    }

def get_recent_logs(log_file, lines=20):
    """Get recent log lines"""
    try:
        path = Path(log_file)
        if path.exists():
            with open(path, 'r') as f:
                all_lines = f.readlines()
                return all_lines[-lines:]
        return []
    except:
        return []

@app.route('/status', methods=['GET'])
def status():
    """Get complete system status"""
    try:
        # Check processes
        intelligence_hub = check_process('intelligence_hub.py')
        ultimate_trader = check_process('ultimate_trader.py')

        # System info
        memory = psutil.virtual_memory()

        # Recent logs
        log_dir = Path("C:/trading-memory/agent_logs")
        status_logs = get_recent_logs(log_dir / "agent_status.log", 30)
        error_logs = get_recent_logs(log_dir / "agent_errors.log", 10)

        return jsonify({
            'timestamp': datetime.now().isoformat(),
            'processes': {
                'intelligence_hub': intelligence_hub,
                'ultimate_trader': ultimate_trader
            },
            'system': {
                'memory_percent': memory.percent,
                'memory_used_gb': memory.used / (1024**3),
                'memory_total_gb': memory.total / (1024**3)
            },
            'logs': {
                'status': [line.strip() for line in status_logs if line.strip()],
                'errors': [line.strip() for line in error_logs if line.strip()]
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Simple health check"""
    hub = check_process('intelligence_hub.py')
    trader = check_process('ultimate_trader.py')

    both_running = hub['running'] and trader['running']

    return jsonify({
        'health': 'OK' if both_running else 'WARNING',
        'intelligence_hub_running': hub['running'],
        'ultimate_trader_running': trader['running']
    })

@app.route('/logs/<agent>', methods=['GET'])
def get_logs(agent):
    """Get logs for specific agent"""
    log_dir = Path("C:/trading-memory/agent_logs")

    if agent == 'status':
        logs = get_recent_logs(log_dir / "agent_status.log", 50)
    elif agent == 'errors':
        logs = get_recent_logs(log_dir / "agent_errors.log", 20)
    else:
        return jsonify({'error': 'Invalid agent'}), 400

    return jsonify({
        'agent': agent,
        'logs': [line.strip() for line in logs if line.strip()]
    })

if __name__ == '__main__':
    print("Status Server starting on http://0.0.0.0:5555")
    print("Endpoints:")
    print("  GET /status - Complete system status")
    print("  GET /health - Health check")
    print("  GET /logs/status - Status logs")
    print("  GET /logs/errors - Error logs")
    app.run(host='0.0.0.0', port=5555, debug=False)
