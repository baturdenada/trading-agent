"""
Webhook Bridge - Receives commands from Claude Code and executes them
Fixed version with error handling
"""

from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import json
from datetime import datetime
import traceback

load_dotenv()

app = Flask(__name__)

# Lazy MT5 initialization (only when needed)
mt5 = None

def get_mt5():
    global mt5
    if mt5 is None:
        import MetaTrader5 as mt5_module
        mt5 = mt5_module
        mt5.initialize(
            path=os.getenv("MT5_PATH"),
            login=int(os.getenv("MT5_LOGIN", 0)),
            password=os.getenv("MT5_PASSWORD"),
            server=os.getenv("MT5_SERVER")
        )
    return mt5

@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.json
        command = data.get('command')
        params = data.get('params', {})
        
        print(f"Received command: {command}")
        
        if command == 'get_account':
            mt5 = get_mt5()
            account = mt5.account_info()
            if account:
                return jsonify({
                    'balance': account.balance,
                    'equity': account.equity,
                    'profit': account.profit,
                    'margin': account.margin
                })
            else:
                return jsonify({'error': 'Failed to get account info'}), 500
        
        elif command == 'get_candles':
            symbol = params.get('symbol', 'XAUUSD.s')
            days = params.get('days', 30)
            mt5 = get_mt5()
            rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days)
            
            if rates is None:
                return jsonify({'error': f'Failed to get candles for {symbol}'}), 500
            
            result = []
            for r in rates:
                result.append({
                    'date': datetime.fromtimestamp(r[0]).strftime('%Y-%m-%d'),
                    'open': r[1],
                    'high': r[2],
                    'low': r[3],
                    'close': r[4]
                })
            return jsonify(result)
        
        elif command == 'get_positions':
            mt5 = get_mt5()
            symbols = ['XAUUSD.s', 'XAGUSD.s', 'EURUSD.s', 'USDCAD.s', 'USDJPY.s', 'USDCHF.s', 'USOUSD.s', 'SP500.s', 'NAS100.s']
            positions = []
            for s in symbols:
                pos = mt5.positions_get(symbol=s)
                if pos:
                    for p in pos:
                        positions.append({
                            'symbol': p.symbol,
                            'type': 'BUY' if p.type == 0 else 'SELL',
                            'volume': p.volume,
                            'price': p.price_open,
                            'profit': p.profit
                        })
            return jsonify(positions)
        
        elif command == 'ping':
            return jsonify({'status': 'ok', 'message': 'Webhook bridge is running'})
        
        else:
            return jsonify({'error': f'Unknown command: {command}'}), 400
    
    except Exception as e:
        error_msg = str(e)
        print(f"Error: {error_msg}")
        traceback.print_exc()
        return jsonify({'error': error_msg}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'Webhook bridge is running'})

if __name__ == '__main__':
    print("🌐 Webhook Bridge running on port 5001")
    print("Commands: get_account, get_candles, get_positions, ping")
    print("Test: curl http://localhost:5001/health")
    app.run(host='0.0.0.0', port=5001, debug=False)