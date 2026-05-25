"""
TRADE EXECUTION TEST
Diagnoses why trades aren't being placed
"""

import logging
import MetaTrader5 as mt5
from config import Config
from ultimate_trader import UltimateTrader

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s | %(message)s')
logger = logging.getLogger(__name__)

print("=" * 60)
print("TRADE EXECUTION DIAGNOSTICS")
print("=" * 60)

try:
    trader = UltimateTrader()

    print("\n1. MT5 Connection Status:")
    print(f"   Connected: {mt5.terminal_info() is not None}")
    print(f"   Account: {mt5.account_info().login if mt5.account_info() else 'N/A'}")

    print("\n2. Risk Manager Status:")
    print(f"   Trading allowed: {trader.risk_manager.is_trading_allowed()}")
    print(f"   Daily limit check: {trader.risk_manager.check_daily_loss_limit(4353, 4353)[0]}")

    print("\n3. Market Status:")
    print(f"   Market open: {trader.check_market_status()}")

    print("\n4. Test Symbol Analysis:")
    test_symbol = "XAUUSD.s"
    indicators = trader.calculate_indicators(test_symbol)
    if indicators:
        print(f"   Symbol: {test_symbol}")
        print(f"   Price: ${indicators['price']:.2f}")
        print(f"   RSI: {indicators['rsi']:.1f}")
        print(f"   ATR: {indicators['atr']:.4f}")
        print(f"   Trend: {indicators['trend']}")
    else:
        print(f"   ERROR: Could not get indicators for {test_symbol}")

    print("\n5. Decision Test:")
    account = mt5.account_info()
    if account and indicators:
        decision = trader.get_ai_decision(
            {'name': test_symbol, 'base_risk': 0.02, 'pip_value': 0.01},
            indicators,
            account,
            False
        )
        if decision:
            print(f"   Action: {decision.get('action')}")
            print(f"   Confidence: {decision.get('confidence')}%")
            print(f"   Reasoning: {decision.get('reasoning', 'N/A')[:100]}")
        else:
            print(f"   ERROR: No decision returned")
    else:
        print(f"   ERROR: Missing account or indicators")

    print("\n6. Execution Test (DRY RUN - NO REAL TRADE):")
    print(f"   Would open: {decision.get('action')} order")
    print(f"   Confidence level: {decision.get('confidence')}% (need >60% to trade)")

    if decision.get('confidence', 0) > 60:
        print(f"   STATUS: Ready to trade (confidence sufficient)")
    else:
        print(f"   STATUS: Insufficient confidence to open trade")

    print("\n" + "=" * 60)
    print("DIAGNOSTICS COMPLETE")
    print("=" * 60)

except Exception as e:
    print(f"\nERROR: {e}")
    import traceback
    traceback.print_exc()
