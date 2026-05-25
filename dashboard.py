"""
Trading Agent Web Dashboard
Run: python dashboard.py
Access: http://localhost:5000
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
import requests

load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = 'trading-secret-key'
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
    'recent_trades': []
}

def init_mt5():
    global mt5_initialized
    login = int(os.getenv("MT5_LOGIN", 0))
    password = os.getenv("MT5_PASSWORD", "")
    server = os.getenv("MT5_SERVER", "")
    path = os.getenv("MT5_PATH", "")
    
    if not mt5_initialized:
        mt5.initialize(path=path, login=login, password=password, server=server)
        mt5.symbol_select(symbol, True)
        mt5_initialized = True
        print("MT5 connected")

def get_live_data():
    try:
        if not mt5_initialized:
            init_mt5()
        
        tick = mt5.symbol_info_tick(symbol)
        account = mt5.account_info()
        positions = mt5.positions_get(symbol=symbol)
        
        positions_list = []
        total_pnl = 0
        if positions:
            for p in positions:
                pnl = p.profit
                total_pnl += pnl
                positions_list.append({
                    'ticket': p.ticket,
                    'type': 'BUY' if p.type == 0 else 'SELL',
                    'volume': p.volume,
                    'open_price': p.price_open,
                    'current_price': p.price_current,
                    'pnl': pnl
                })
        
        return {
            'price': tick.ask if tick else 0,
            'balance': account.balance if account else 0,
            'equity': account.equity if account else 0,
            'total_pnl': total_pnl,
            'positions': positions_list,
            'positions_count': len(positions_list)
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
                'positions_count': current_data['positions_count'],
                'positions': current_data['positions']
            })
        time.sleep(1)

@app.route('/')
def index():
    return render_template('dashboard.html')

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
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_BUY,
            "price": tick.ask,
            "deviation": 20,
            "magic": 987654,
            "comment": "Web_Dashboard",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
    elif action == 'SELL':
        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": lot,
            "type": mt5.ORDER_TYPE_SELL,
            "price": tick.bid,
            "deviation": 20,
            "magic": 987654,
            "comment": "Web_Dashboard",
            "type_filling": mt5.ORDER_FILLING_IOC,
        }
    else:
        return jsonify({'success': False, 'error': 'Invalid action'})
    
    result = mt5.order_send(request)
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
    
    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": pos.volume,
        "type": order_type,
        "position": ticket,
        "deviation": 20,
        "magic": 987654,
        "comment": "Close_Web",
        "type_filling": mt5.ORDER_FILLING_IOC,
    }
    
    result = mt5.order_send(request)
    if result is not None and result.retcode == mt5.TRADE_RETCODE_DONE:
        return jsonify({'success': True})
    else:
        error = result.comment if result is not None else 'Order send failed'
        return jsonify({'success': False, 'error': error})

# Create templates folder and HTML
TEMPLATES_DIR = Path(__file__).parent / 'templates'
TEMPLATES_DIR.mkdir(exist_ok=True)

HTML_TEMPLATE = '''<!DOCTYPE html>
<html>
<head>
    <title>Trading Dashboard</title>
    <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: Arial, sans-serif; background: #0a0e27; color: #e0e0e0; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        h1 { margin-bottom: 20px; color: #00d4aa; }
        .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 20px; }
        .card { background: #141832; border-radius: 10px; padding: 20px; border: 1px solid #2a2f4f; }
        .price { font-size: 32px; font-weight: bold; color: #00d4aa; }
        .pnl-positive { color: #00ff88; }
        .pnl-negative { color: #ff4444; }
        .stat { display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #2a2f4f; }
        button { background: #00d4aa; color: #0a0e27; border: none; padding: 8px 16px; border-radius: 5px; cursor: pointer; }
        .trade-form { display: flex; gap: 10px; margin-top: 15px; }
        .trade-form input, .trade-form select { background: #0a0e27; border: 1px solid #2a2f4f; color: #e0e0e0; padding: 8px; border-radius: 5px; }
        .close-btn { background: #ff4444; color: white; padding: 4px 12px; font-size: 12px; }
        .flex { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
    </style>
</head>
<body>
<div class="container">
    <div class="flex">
        <h1>Trading Dashboard</h1>
        <button onclick="location.reload()">Refresh</button>
    </div>
    
    <div class="grid">
        <div class="card">
            <h3>Live Price</h3>
            <div class="price" id="price">--</div>
        </div>
        <div class="card">
            <h3>Account</h3>
            <div class="stat"><span>Balance</span><span id="balance">--</span></div>
            <div class="stat"><span>Equity</span><span id="equity">--</span></div>
            <div class="stat"><span>PnL</span><span id="total_pnl">--</span></div>
            <div class="stat"><span>Positions</span><span id="pos_count">--</span></div>
        </div>
    </div>
    
    <div class="card">
        <h3>Quick Trade</h3>
        <div class="trade-form">
            <select id="trade-action"><option value="BUY">BUY</option><option value="SELL">SELL</option></select>
            <input type="number" id="trade-lot" value="0.05" step="0.01">
            <button onclick="executeTrade()">Execute</button>
        </div>
    </div>
    
    <div class="card">
        <h3>Open Positions</h3>
        <div id="positions-list">No open positions</div>
    </div>
</div>

<script>
var socket = io();
socket.on('data_update', function(data) {
    document.getElementById('price').innerHTML = '$' + data.price.toFixed(3);
    document.getElementById('balance').innerHTML = '$' + data.balance.toFixed(2);
    document.getElementById('equity').innerHTML = '$' + data.equity.toFixed(2);
    document.getElementById('pos_count').innerHTML = data.positions_count;
    var pnl = document.getElementById('total_pnl');
    pnl.innerHTML = '$' + data.total_pnl.toFixed(2);
    pnl.className = data.total_pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
    
    if (data.positions && data.positions.length > 0) {
        var html = '';
        for (var i = 0; i < data.positions.length; i++) {
            var p = data.positions[i];
            var cls = p.pnl >= 0 ? 'pnl-positive' : 'pnl-negative';
            html += '<div class="stat"><span>' + p.type + ' ' + p.volume + ' @ ' + p.open_price.toFixed(3) + '</span>';
            html += '<span class="' + cls + '">$' + p.pnl.toFixed(2) + '</span>';
            html += '<button class="close-btn" onclick="closePosition(' + p.ticket + ')">Close</button></div>';
        }
        document.getElementById('positions-list').innerHTML = html;
    } else {
        document.getElementById('positions-list').innerHTML = 'No open positions';
    }
});

function executeTrade() {
    var action = document.getElementById('trade-action').value;
    var lot = parseFloat(document.getElementById('trade-lot').value);
    fetch('/api/execute', {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify({action: action, lot: lot})})
    .then(r=>r.json()).then(data => {if(data.success){alert('Trade executed'); location.reload();}else{alert('Failed: '+data.error);}});
}

function closePosition(ticket) {
    fetch('/api/close/'+ticket, {method: 'POST'}).then(r=>r.json()).then(data => {if(data.success){alert('Closed'); location.reload();}else{alert('Failed: '+data.error);}});
}
</script>
</body>
</html>'''

with open(TEMPLATES_DIR / 'dashboard.html', 'w', encoding='utf-8') as f:
    f.write(HTML_TEMPLATE)

if __name__ == '__main__':
    print("Starting Trading Dashboard...")
    print("Open http://localhost:5000 in your browser")
    
    updater_thread = threading.Thread(target=background_updater, daemon=True)
    updater_thread.start()
    
    socketio.run(app, host='0.0.0.0', port=5000, debug=False, allow_unsafe_werkzeug=True)