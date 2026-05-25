"""Check what git commit is running on VPS"""
import subprocess
import os

os.chdir("C:\\Users\\Administrator\\Desktop\\DS trading agent")

# Get current commit
result = subprocess.run(["git", "log", "-1", "--oneline"], capture_output=True, text=True)
print("VPS Current Commit:")
print(result.stdout)

# Check if we have the new manage_position code
with open("ultimate_trader.py", "r") as f:
    content = f.read()
    if "PROFIT-TAKING ALERTS" in content:
        print("\n✅ NEW CODE DETECTED - manage_position() has profit alerts")
    else:
        print("\n❌ OLD CODE RUNNING - manage_position() doesn't have profit alerts")
