# Routine: Analyze XAUUSD/XAGUSD High/Low Strategy

## Description
Analyzes previous day high/low breakout strategy for Gold and Silver.
Tests TP and SL combinations to find optimal parameters.

## Input Variables (can be overridden)
- SYMBOL: "XAUUSD.s" (or "XAGUSD.s")
- DAYS: 30
- TP_MIN: 100
- TP_MAX: 1000
- TP_STEP: 100
- SL_MIN: 1000
- SL_MAX: 6000
- SL_STEP: 500

## Steps

### Step 1: Fetch Historical Data
```bash
python -c "
import MetaTrader5 as mt5
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta

load_dotenv()
mt5.initialize(
    path=os.getenv('MT5_PATH'),
    login=int(os.getenv('MT5_LOGIN', 0)),
    password=os.getenv('MT5_PASSWORD'),
    server=os.getenv('MT5_SERVER')
)

symbol = os.getenv('SYMBOL', 'XAUUSD.s')
days = int(os.getenv('DAYS', 30))

rates = mt5.copy_rates_from_pos(symbol, mt5.TIMEFRAME_D1, 0, days + 5)
data = []
for rate in rates[:days]:
    data.append({
        'date': datetime.fromtimestamp(rate[0]).strftime('%Y-%m-%d'),
        'high': rate[2],
        'low': rate[3],
        'close': rate[4]
    })

import json
print(json.dumps(data))
mt5.shutdown()
" > C:\trading-memory\data.json