"""
Enhanced Trading Agent Dashboard
Real-time monitoring of trading signals, positions, risk metrics
Run: python dashboard_enhanced.py
Access: http://localhost:5001
"""
import json
import time
import threading
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

from flask import Flask, render_template, jsonify, request
from flask_socketio import SocketIO, emit
import MetaTrader5 as mt5
from dotenv import load_dotenv
import os

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading-secret-key-enhanced'
socketio = SocketIO(app, cors_allowed_origins="*")

# MT5 connection
mt5_initialized = False
symbol = "XAGUSD.s"

# Data cache
current_data = {
    'price': 0,
    'balance': 0,
    'equity': 0,
    'positions': [],
    'recent_trades': [],
    'system_status': 'LOADING',
    'market_regime': 'UNKNOWN',
    'pending_signals': [],
    'risk_metrics': {
        'max_positions': 5,
        'current_positions': 0,
        'daily_loss_limit': 100,
        'current_loss': 0,
        'correlation_risk': 'LOW'
    }
}

def init_mt5():
    global mt5_initialized
    login = int(os.getenv("MT5_LOGIN", 0))
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")
    path = os.getenv("MT5_PATH", "")

    if not mt5_initialized:
        try:
            mt5.initialize(path=path, login=login, password=password, server=server)
            mt5.symbol_select(symbol, True)
            mt5_initialized = True
            print("✓ MT5 connected")
            return True
        except Exception as e:
            print(f"✗ MT5 connection failed: {e}")
            return False

def get_live_data():
    try:
        if not mt5_initialized:
            init_mt5()

        tick = mt5.symbol_info_tick(symbol)
        account = mt5.account_info()
        positions = mt5.positions_get(symbol=symbol)

        positions_list = []
        total_pnl = 0
        max_loss = 0
        if positions:
            for p in positions:
                pnl = p.profit
                total_pnl += pnl
                max_loss = min(max_loss, pnl)
                positions_list.append({
                    'ticket': p.ticket,
                    'type': 'BUY' if p.type == 0 else 'SELL',
                    'volume': p.volume,
                    'open_price': p.price_open,
                    'current_price': p.price_current,
                    'pnl': pnl,
                    'pnl_pct': (pnl / (p.volume * p.price_open * 100)) * 100 if p.price_open > 0 else 0,
                    'open_time': datetime.fromtimestamp(p.time).strftime('%Y-%m-%d %H:%M:%S')
                })

        system_status = 'TRADING' if account and account.balance > 0 else 'ERROR'

        return {
            'price': tick.ask if tick else 0,
            'balance': account.balance if account else 0,
            'equity': account.equity if account else 0,
            'total_pnl': total_pnl,
            'max_loss': max_loss,
            'positions': positions_list,
            'positions_count': len(positions_list),
            'system_status': system_status,
            'timestamp': datetime.now().isoformat()
        }
    except Exception as e:
        print(f"Live data error: {e}")
        return None

def background_updater():
    while True:
        live = get_live_data()
        if live:
            current_data.update(live)
            socketio.emit('data_update', {
                'price': current_data['price'],
                'balance': current_data['balance'],
                'equity': current_data['equity'],
                'total_pnl': current_data['total_pnl'],
                'max_loss': current_data['max_loss'],
                'positions_count': current_data['positions_count'],
                'positions': current_data['positions'],
                'system_status': current_data['system_status'],
                'risk_metrics': current_data['risk_metrics'],
                'timestamp': datetime.now().isoformat()
            }, broadcast=True)
        time.sleep(1)

@app.route('/')
def index():
    return render_template('dashboard_enhanced.html')

@app.route('/api/data')
def api_data():
    return jsonify(current_data)

@app.route('/api/execute', methods=['POST'])
def execute_trade():
    data = request.json
    action = data.get('action')
    lot = float(data.get('lot', 0.05))

    tick = mt5.symbol_info_tick(symbol)
    if not tick:
        return jsonify({'success': False, 'error': 'No price data'})

    if action == 'BUY':
        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 987654,
            "comment": "Dashboard_Manual",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
    elif action == 'SELL':
        request_data = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "deviation": 20,
            "magic": 987654,
            "comment": "Dashboard_Manual",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
    else:
        return jsonify({'success': False, 'error': 'Invalid action'})

    result = mt5.order_send(request_data)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        return jsonify({'success': True, 'order': result.order})
    else:
        error = result.comment if result is not None else 'Order send failed'
        return jsonify({'success': False, 'error': error})

@app.route('/api/close/<int:ticket>', methods=['POST'])
def close_position(ticket):
    position = mt5.positions_get(ticket=ticket)
    if not position:
        return jsonify({'success': False, 'error': 'Position not found'})

    pos = position[0]
    order_type = mt5.ORDER_TYPE_SELL if pos.type == 0 else mt5.ORDER_TYPE_BUY

    request_data = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": ticket,
        "deviation": 20,
        "magic": 987654,
        "comment": "Dashboard_Close",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }

    result = mt5.order_send(request_data)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        return jsonify({'success': True})
    else:
        error = result.comment if result is not None else 'Order send failed'
        return jsonify({'success': False, 'error': error})

@app.route('/api/status')
def api_status():
    """Get system status information"""
    return jsonify({
        'connected': mt5_initialized,
        'symbol': symbol,
        'data': current_data,
        'timestamp': datetime.now().isoformat()
    })

# Create templates folder and HTML
TEMPLATES_DIR = Path(__file__).parent / 'templates'
TEMPLATES_DIR.mkdir(exist_ok=True)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Advanced Trading Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
            color: #e0e0e0;
            padding: 20px;
        }
        .container { max-width: 1400px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #00d4aa; font-size: 2.5em; text-shadow: 0 0 10px rgba(0,212,170,0.3); }
        .header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px; }
        .status-badge {
            display: inline-block;
            padding: 8px 16px;
            border-radius: 20px;
            font-weight: bold;
            font-size: 0.9em;
        }
        .status-active { background: #00ff88; color: #000; }
        .status-error { background: #ff4444; color: #fff; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .card {
            background: linear-gradient(135deg, #141832 0%, #1a1f3a 100%);
            border-radius: 15px;
            padding: 25px;
            border: 1px solid rgba(0,212,170,0.2);
            box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            transition: all 0.3s ease;
        }
        .card:hover {
            border-color: rgba(0,212,170,0.5);
            box-shadow: 0 12px 48px rgba(0,212,170,0.15);
        }
        .card h3 { color: #00d4aa; margin-bottom: 15px; font-size: 0.95em; text-transform: uppercase; letter-spacing: 1px; }
        .price { font-size: 2.5em; font-weight: bold; color: #00d4aa; text-shadow: 0 0 20px rgba(0,212,170,0.3); }
        .pnl-positive { color: #00ff88; font-weight: bold; }
        .pnl-negative { color: #ff4444; font-weight: bold; }
        .stat {
            display: flex;
            justify-content: space-between;
            padding: 10px 0;
            border-bottom: 1px solid rgba(0,212,170,0.1);
            font-size: 0.95em;
        }
        .stat:last-child { border-bottom: none; }
        .stat-label { color: #aaa; }
        .stat-value { color: #00d4aa; font-weight: bold; }
        button {
            background: linear-gradient(135deg, #00d4aa 0%, #00b893 100%);
            color: #0a0e27;
            border: none;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            font-weight: bold;
            transition: all 0.3s ease;
            margin-top: 15px;
            width: 100%;
        }
        button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(0,212,170,0.3);
        }
        .trade-form { display: flex; gap: 10px; flex-direction: column; }
        .trade-form input, .trade-form select {
            background: rgba(10,14,39,0.5);
            border: 1px solid rgba(0,212,170,0.3);
            color: #e0e0e0;
            padding: 10px;
            border-radius: 8px;
            font-size: 0.95em;
        }
        .trade-form input:focus, .trade-form select:focus {
            outline: none;
            border-color: #00d4aa;
            box-shadow: 0 0 10px rgba(0,212,170,0.2);
        }
        .position-item {
            background: rgba(0,212,170,0.05);
            border-left: 3px solid #00d4aa;
            padding: 15px;
            margin-bottom: 10px;
            border-radius: 5px;
            font-size: 0.9em;
        }
        .position-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 10px;
        }
        .position-type {
            display: inline-block;
            padding: 3px 8px;
            border-radius: 3px;
            font-weight: bold;
            font-size: 0.85em;
        }
        .type-buy { background: #00ff88; color: #000; }
        .type-sell { background: #ff4444; color: #fff; }
        .close-btn {
            background: #ff4444;
            color: white;
            padding: 5px 10px;
            font-size: 0.85em;
            width: auto;
            margin: 0;
        }
        .close-btn:hover { background: #cc3333; }
        .chart-container { background: rgba(0,0,0,0.2); padding: 20px; border-radius: 10px; margin-bottom: 20px; }
        .flex { display: flex; gap: 10px; }
        .flex-1 { flex: 1; }
        .risk-high { color: #ff4444; }
        .risk-medium { color: #ffaa00; }
        .risk-low { color: #00ff88; }
        .online-indicator {
            display: inline-block;
            width: 10px;
            height: 10px;
            border-radius: 50%;
            background: #00ff88;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.5; }
        }
    </style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1><span class="online-indicator"></span>Advanced Trading Dashboard</h1>
        <div>
            <span id="status-badge" class="status-badge status-error">CONNECTING...</span>
        </div>
    </div>

    <div class="grid">
        <div class="card">
            <h3>Live Price</h3>
            <div class="price" id="price">--</div>
            <div class="stat" style="margin-top: 15px;">
                <span class="stat-label">Last Update</span>
                <span class="stat-value" id="price-time">--:--:--</span>
            </div>
        </div>

        <div class="card">
            <h3>Account Balance</h3>
            <div style="font-size: 1.8em; color: #00d4aa; font-weight: bold;">
                $<span id="balance">--</span>
            </div>
            <div class="stat" style="margin-top: 15px;">
                <span class="stat-label">Equity</span>
                <span class="stat-value">$<span id="equity">--</span></span>
            </div>
        </div>

        <div class="card">
            <h3>Profit & Loss</h3>
            <div id="pnl-display" style="font-size: 2em; font-weight: bold; margin: 10px 0;">$<span id="total_pnl">0.00</span></div>
            <div class="stat">
                <span class="stat-label">Daily Loss</span>
                <span class="stat-value" id="max_loss">--</span>
            </div>
        </div>

        <div class="card">
            <h3>Positions</h3>
            <div style="font-size: 2em; color: #00d4aa; font-weight: bold; margin: 10px 0;" id="pos_count">0</div>
            <div class="stat">
                <span class="stat-label">Max Allowed</span>
                <span class="stat-value">5</span>
            </div>
        </div>
    </div>

    <div class="flex">
        <div class="flex-1">
            <div class="card">
                <h3>Risk Metrics</h3>
                <div class="stat">
                    <span class="stat-label">Correlation Risk</span>
                    <span class="stat-value" id="corr-risk">LOW</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Max Daily Loss</span>
                    <span class="stat-value">$100</span>
                </div>
                <div class="stat">
                    <span class="stat-label">Volatility Regime</span>
                    <span class="stat-value" id="regime">UNKNOWN</span>
                </div>
            </div>
        </div>

        <div class="flex-1">
            <div class="card">
                <h3>Quick Trade</h3>
                <div class="trade-form">
                    <select id="trade-action">
                        <option value="BUY">BUY</option>
                        <option value="SELL">SELL</option>
                    </select>
                    <input type="number" id="trade-lot" value="0.05" step="0.01" placeholder="Lot size">
                    <button onclick="executeTrade()">Execute Trade</button>
                </div>
            </div>
        </div>
    </div>

    <div class="card" style="margin-top: 20px;">
        <h3>Open Positions</h3>
        <div id="positions-list" style="max-height: 400px; overflow-y: auto;">
            <div style="text-align: center; color: #666; padding: 40px 20px;">No open positions</div>
        </div>
    </div>
</div>

<script>
var socket = io();

socket.on('connect', function() {
    console.log('Connected to server');
    document.getElementById('status-badge').className = 'status-badge status-active';
    document.getElementById('status-badge').textContent = 'CONNECTED';
});

socket.on('data_update', function(data) {
    // Update price
    document.getElementById('price').innerHTML = '$' + data.price.toFixed(3);
    document.getElementById('price-time').innerHTML = new Date().toLocaleTimeString();

    // Update balance & equity
    document.getElementById('balance').innerHTML = data.balance.toFixed(2);
    document.getElementById('equity').innerHTML = data.equity.toFixed(2);

    // Update PnL
    var pnlDisplay = document.getElementById('pnl-display');
    var pnlValue = document.getElementById('total_pnl');
    pnlValue.innerHTML = data.total_pnl.toFixed(2);
    pnlDisplay.className = data.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative';

    // Update position count
    document.getElementById('pos_count').innerHTML = data.positions_count;

    // Update max loss
    if (data.max_loss !== 0) {
        document.getElementById('max_loss').innerHTML = '$' + data.max_loss.toFixed(2);
    }

    // Update positions list
    if (data.positions && data.positions.length > 0) {
        var html = '';
        for (var i = 0; i < data.positions.length; i++) {
            var p = data.positions[i];
            var pnlClass = p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            var typeClass = p.type === 'BUY' ? 'type-buy' : 'type-sell';

            html += '<div class="position-item">';
            html += '<div class="position-header">';
            html += '<span><span class="position-type ' + typeClass + '">' + p.type + '</span> ' + p.volume + 'L @ $' + p.open_price.toFixed(3) + '</span>';
            html += '<span class="' + pnlClass + '">$' + p.pnl.toFixed(2) + ' (' + p.pnl_pct.toFixed(2) + '%)</span>';
            html += '</div>';
            html += '<div style="font-size: 0.85em; color: #999;">';
            html += 'Current: $' + p.current_price.toFixed(3) + ' | Opened: ' + p.open_time;
            html += '</div>';
            html += '<button class="close-btn" onclick="closePosition(' + p.ticket + ')">CLOSE</button>';
            html += '</div>';
        }
        document.getElementById('positions-list').innerHTML = html;
    } else {
        document.getElementById('positions-list').innerHTML = '<div style="text-align: center; color: #666; padding: 40px 20px;">No open positions</div>';
    }
});

socket.on('disconnect', function() {
    console.log('Disconnected from server');
    document.getElementById('status-badge').className = 'status-badge status-error';
    document.getElementById('status-badge').textContent = 'DISCONNECTED';
});

function executeTrade() {
    var action = document.getElementById('trade-action').value;
    var lot = parseFloat(document.getElementById('trade-lot').value);

    if (lot <= 0) {
        alert('Please enter a valid lot size');
        return;
    }

    fetch('/api/execute', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({action: action, lot: lot})
    })
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert('✓ Trade executed successfully');
            document.getElementById('trade-lot').value = '0.05';
        } else {
            alert('✗ Trade failed: ' + data.error);
        }
    })
    .catch(e => alert('Error: ' + e));
}

function closePosition(ticket) {
    if (!confirm('Close this position?')) return;

    fetch('/api/close/' + ticket, {method: 'POST'})
    .then(r => r.json())
    .then(data => {
        if (data.success) {
            alert('✓ Position closed');
        } else {
            alert('✗ Failed to close: ' + data.error);
        }
    })
    .catch(e => alert('Error: ' + e));
}

// Request initial data
fetch('/api/data').then(r => r.json()).then(data => {
    console.log('Initial data loaded');
});
</script>
</body>
</html>'''

# Write template
with open(TEMPLATES_DIR / 'dashboard_enhanced.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("🚀 ENHANCED TRADING DASHBOARD")
    print("="*60)
    print("Starting server on http://0.0.0.0:5001")
    print("Open in browser: http://localhost:5001")
    print("="*60 + "\n")

    init_mt5()

    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()

    socketio.run(app, host='0.0.0.0', port=5001, debug=False, allow_unsafe_werkzeug=True)
