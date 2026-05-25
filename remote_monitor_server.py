"""
REMOTE MONITOR SERVER
Runs on local machine - receives webhook data from VPS agents
Provides endpoints to query agent status, logs, and issue commands
"""

from flask import Flask, request, jsonify
import json
from datetime import datetime
from pathlib import Path
import requests
import subprocess

app = Flask(__name__)

# Store latest status
latest_status = {
    'timestamp': None,
    'agents': {},
    'system': {},
    'logs': {'status': [], 'errors': []}
}

VPS_IP = "172.31.26.233"
VPS_HTTP_PORT = 8888

@app.route('/webhook/agent-status', methods=['POST'])
def webhook_agent_status():
    """Receive status updates from VPS agents"""
    global latest_status
    try:
        data = request.json
        latest_status = data
        latest_status['received_at'] = datetime.now().isoformat()

        # Log to file for persistence
        log_file = Path("C:/trading-memory/remote_monitor.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a") as f:
            f.write(json.dumps(latest_status) + "\n")

        return jsonify({'status': 'ok', 'message': 'Status received'}), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@app.route('/status', methods=['GET'])
def get_status():
    """Get latest agent status"""
    return jsonify(latest_status), 200

@app.route('/agents/health', methods=['GET'])
def agents_health():
    """Get quick health check"""
    agents = latest_status.get('intelligence_hub', {})
    trader = latest_status.get('ultimate_trader', {})

    return jsonify({
        'intelligence_hub_running': agents.get('running', False),
        'ultimate_trader_running': trader.get('running', False),
        'both_healthy': agents.get('running', False) and trader.get('running', False),
        'last_update': latest_status.get('received_at')
    }), 200

@app.route('/logs/status', methods=['GET'])
def get_status_logs():
    """Get status logs from latest update"""
    logs = latest_status.get('logs', {}).get('status', [])
    return jsonify({'logs': logs}), 200

@app.route('/logs/errors', methods=['GET'])
def get_error_logs():
    """Get error logs from latest update"""
    logs = latest_status.get('logs', {}).get('errors', [])
    return jsonify({'logs': logs}), 200

@app.route('/system', methods=['GET'])
def get_system():
    """Get system info"""
    sys_info = latest_status.get('system', {})
    return jsonify(sys_info), 200

@app.route('/command/restart-agent/<agent_name>', methods=['POST'])
def restart_agent(agent_name):
    """Issue command to restart an agent on VPS"""
    try:
        valid_agents = ['intelligence_hub.py', 'ultimate_trader.py', 'strategy_agent.py', 'news_agent.py']

        if agent_name not in valid_agents:
            return jsonify({'error': f'Unknown agent: {agent_name}'}), 400

        # For now, return instruction for user to run
        command = f'cd "C:\\Users\\Administrator\\Desktop\\DS trading agent" && py {agent_name}'

        return jsonify({
            'status': 'command_generated',
            'agent': agent_name,
            'instruction': f'Run this command on VPS: {command}'
        }), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/vps/files/<path:filepath>', methods=['GET'])
def get_vps_file(filepath):
    """Download a file from VPS via HTTP server"""
    try:
        url = f"http://{VPS_IP}:{VPS_HTTP_PORT}/{filepath}"
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            return response.content, 200, {'Content-Type': response.headers.get('Content-Type')}
        else:
            return jsonify({'error': f'File not found: {filepath}'}), 404
    except requests.exceptions.Timeout:
        return jsonify({'error': 'VPS HTTP server timeout'}), 504
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/dashboard', methods=['GET'])
def dashboard():
    """HTML dashboard showing agent status"""
    agents = latest_status.get('agents', {})
    hub_status = "✅ RUNNING" if agents.get('intelligence_hub', {}).get('running') else "❌ STOPPED"
    trader_status = "✅ RUNNING" if agents.get('ultimate_trader', {}).get('running') else "❌ STOPPED"

    logs = latest_status.get('logs', {}).get('status', [])
    errors = latest_status.get('logs', {}).get('errors', [])

    html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>VPS Agent Monitor</title>
        <meta http-equiv="refresh" content="10">
        <style>
            body {{ font-family: monospace; background: #1e1e1e; color: #00ff00; padding: 20px; }}
            .agent {{ border: 1px solid #00ff00; padding: 10px; margin: 10px 0; }}
            .running {{ color: #00ff00; }}
            .stopped {{ color: #ff0000; }}
            .logs {{ background: #0a0a0a; border: 1px solid #333; padding: 10px; max-height: 400px; overflow-y: auto; }}
            h1 {{ color: #00ff00; }}
            .timestamp {{ color: #888; font-size: 0.8em; }}
        </style>
    </head>
    <body>
        <h1>🔥 VPS AGENT MONITOR</h1>
        <p class="timestamp">Last update: {latest_status.get('received_at', 'Never')}</p>

        <h2>Agent Status</h2>
        <div class="agent">
            <p>Intelligence Hub: <span class="{'running' if agents.get('intelligence_hub', {}).get('running') else 'stopped'}">{hub_status}</span> (PID: {agents.get('intelligence_hub', {}).get('pid', 'N/A')})</p>
        </div>
        <div class="agent">
            <p>Ultimate Trader: <span class="{'running' if agents.get('ultimate_trader', {}).get('running') else 'stopped'}">{trader_status}</span> (PID: {agents.get('ultimate_trader', {}).get('pid', 'N/A')})</p>
        </div>

        <h2>System Status</h2>
        <div class="agent">
            <p>Memory: {latest_status.get('system', {}).get('memory_percent', 'N/A')}% used</p>
            <p>CPU: {latest_status.get('system', {}).get('cpu_percent', 'N/A')}% used</p>
        </div>

        <h2>Recent Logs</h2>
        <div class="logs">
            {'<br/>'.join(logs[-20:]) if logs else 'No logs yet'}
        </div>

        <h2>Errors</h2>
        <div class="logs" style="color: #ff6666;">
            {'<br/>'.join(errors) if errors else 'No errors'}
        </div>
    </body>
    </html>
    """
    return html, 200, {'Content-Type': 'text/html'}

if __name__ == '__main__':
    print("=" * 80)
    print("REMOTE MONITOR SERVER STARTED")
    print("=" * 80)
    print("Listening on http://localhost:5000")
    print("\nEndpoints:")
    print("  GET  http://localhost:5000/dashboard - HTML dashboard (auto-refresh)")
    print("  GET  http://localhost:5000/status - JSON status")
    print("  GET  http://localhost:5000/agents/health - Quick health check")
    print("  GET  http://localhost:5000/logs/status - Status logs")
    print("  GET  http://localhost:5000/logs/errors - Error logs")
    print("\nTo enable VPS → Monitor communication:")
    print("  1. Start this server: py remote_monitor_server.py")
    print("  2. Update WEBHOOK_URL in agent_webhook_uploader.py with your public IP")
    print("  3. Run agent_webhook_uploader.py on VPS")
    print("=" * 80)

    app.run(host='0.0.0.0', port=5000, debug=False)
