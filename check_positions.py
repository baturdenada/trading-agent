"""Quick script to check current MT5 positions and account status"""
import MetaTrader5 as mt5
import json
from datetime import datetime
from config import Config

# Initialize MT5
if not mt5.initialize(path=Config.MT5_PATH, login=Config.MT5_LOGIN, password=Config.MT5_PASSWORD, server=Config.MT5_SERVER):
    print("Failed to initialize MT5")
    exit(1)

# Get account info
account = mt5.account_info()
print(f"ACCOUNT STATUS")
print(f"Balance: ${account.balance}")
print(f"Equity: ${account.equity}")
print(f"Margin: ${account.margin}")
print(f"Free Margin: ${account.margin_free}")
print(f"Margin Level: {account.margin_level if account.margin_level > 0 else 'N/A'}%")
print("")

# Get all positions
all_positions = mt5.positions_get()
print(f"OPEN POSITIONS: {len(all_positions) if all_positions else 0}")
print("")

if all_positions:
    for pos in all_positions:
        print(f"{pos.symbol} | {'BUY' if pos.type == 0 else 'SELL'} {pos.volume} lots | Entry: {pos.price_open:.4f} | P&L: ${pos.profit:+.2f}")
        print(f"  Ticket: {pos.ticket} | SL: {pos.sl:.4f} | TP: {pos.tp:.4f}")
        print("")

mt5.shutdown()
