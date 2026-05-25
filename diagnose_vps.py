"""Diagnose what's happening on the VPS"""
import subprocess
import json
from pathlib import Path

# Try to query the VPS trading system to check what code version is running
print("DIAGNOSTIC REPORT")
print("=" * 60)

# Check local repo status
print("\nLOCAL REPO STATUS (C:\\Users\\user\\Desktop\\DS trading agent):")
result = subprocess.run(["git", "log", "--oneline", "-1"], capture_output=True, text=True, cwd="C:\\Users\\user\\Desktop\\DS trading agent")
print(f"Latest commit: {result.stdout.strip()}")

# Check if manage_position has profit alerts in local code
print("\nLOCAL CODE CHECK:")
with open("C:\\Users\\user\\Desktop\\DS trading agent\\ultimate_trader.py", "r") as f:
    content = f.read()
    if "PROFIT-TAKING ALERTS" in content:
        print("✅ Local code HAS profit alerts (cb9965e)")
    else:
        print("❌ Local code MISSING profit alerts (old code)")

# Try to run ultimate_trader and check what it loads
print("\nCHECKING WHAT ultimate_trader.py LOADS:")
try:
    import sys
    sys.path.insert(0, "C:\\Users\\user\\Desktop\\DS trading agent")

    # Check if we can import and inspect the UltimateTrader class
    exec(open("C:\\Users\\user\\Desktop\\DS trading agent\\ultimate_trader.py").read(), {"__name__": "__check__"})
except Exception as e:
    print(f"Note: Can't fully import (expected): {str(e)[:100]}")

print("\n" + "=" * 60)
print("SUMMARY:")
print("If local code HAS profit alerts but system not sending them:")
print("→ VPS hasn't pulled the code yet")
print("→ Or git_auto_deployer on VPS is failing to restart agents")
