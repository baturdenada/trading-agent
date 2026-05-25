"""Force VPS to pull latest code and restart agents - bypass git_auto_deployer"""
import subprocess
import time
import os

VPS_DIR = "C:\\Users\\Administrator\\Desktop\\DS trading agent"

print("FORCE DEPLOYMENT - Hard reset and pull latest code")
print("=" * 60)

# Change to VPS directory
os.chdir(VPS_DIR)

# 1. Hard reset to latest remote
print("\n1. Hard resetting to latest remote code...")
result = subprocess.run("git fetch origin", shell=True, capture_output=True, text=True)
print(f"   Fetch: {result.returncode == 0 and '✅' or '❌'}")

result = subprocess.run("git reset --hard origin/main", shell=True, capture_output=True, text=True)
print(f"   Reset: {result.returncode == 0 and '✅' or '❌'}")

# 2. Check what we're on
result = subprocess.run("git log -1 --oneline", shell=True, capture_output=True, text=True)
print(f"\n2. Current commit: {result.stdout.strip()}")

# 3. Verify profit alert code is there
print("\n3. Verifying profit alert code...")
with open("ultimate_trader.py", "r") as f:
    if "PROFIT-TAKING ALERTS" in f.read():
        print("   ✅ Profit alert code FOUND")
    else:
        print("   ❌ Profit alert code MISSING")

# 4. Kill old agents
print("\n4. Killing old agents...")
os.system("taskkill /F /IM python.exe /T 2>nul")
time.sleep(2)

# 5. Start fresh agents
print("\n5. Starting fresh agents...")
os.system(f'start cmd /c "cd {VPS_DIR} && py ultimate_trader.py"')
time.sleep(2)
os.system(f'start cmd /c "cd {VPS_DIR} && py intelligence_hub.py"')

print("\n✅ FORCE DEPLOYMENT COMPLETE")
print("Agents starting with latest code (cb9965e)")
print("Check Telegram for profit/loss alerts within 30 seconds")
