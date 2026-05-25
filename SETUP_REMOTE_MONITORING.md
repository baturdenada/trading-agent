# Remote VPS Monitoring Setup

This setup allows me to monitor and control the VPS without requiring SSH, direct network access, or user interaction.

## Architecture

```
VPS Agents (Intelligence Hub, Ultimate Trader)
    ↓ (sends status every 10 seconds)
Agent Webhook Uploader (Python script on VPS)
    ↓ (POSTs to public webhook)
Public Webhook Endpoint (webhook.site or cloud service)
    ↓ (I poll this endpoint)
Claude (Remote Monitoring)
    ↓ (issues commands and reads logs)
Full Remote Control
```

## Step 1: Get a Public Webhook URL

**Option A: Use webhook.site (easiest, no setup)**
1. Visit https://webhook.site
2. Copy the unique URL shown (e.g., https://webhook.site/12345abc)
3. Use this as your WEBHOOK_URL

**Option B: Use ngrok to expose local port (if you want a persistent endpoint)**
```bash
ngrok http 5000
```
This gives you a public URL like https://abc123.ngrok.io

## Step 2: Update agent_webhook_uploader.py

Edit line 21 in agent_webhook_uploader.py:
```python
WEBHOOK_URL = "https://webhook.site/your-unique-id"  # Replace with your URL
```

## Step 3: Deploy to VPS

Copy agent_webhook_uploader.py to VPS:
```powershell
scp agent_webhook_uploader.py Administrator@13.62.20.69:"C:\Users\Administrator\Desktop\DS trading agent\"
```

## Step 4: Run on VPS

On the VPS, start the uploader in a new terminal:
```powershell
cd "C:\Users\Administrator\Desktop\DS trading agent"
py agent_webhook_uploader.py
```

This will continuously POST agent status to your webhook.

## Step 5: Monitor Remotely

**Option A: View webhook.site dashboard**
- Visit your webhook.site URL
- You'll see all incoming POSTs from the VPS
- Each request contains: agent PIDs, system status, logs, errors

**Option B: Start local monitor server**
```bash
py remote_monitor_server.py
```
Then visit: http://localhost:5000/dashboard

## Step 6: What I Can Now Do Remotely

✅ Monitor both agents in real-time
✅ See system resources (CPU, memory)
✅ Check recent logs and errors
✅ Detect when agents crash
✅ Download files from VPS via HTTP
✅ Issue restart commands
✅ See trade execution logs
✅ Fully automated monitoring without user intervention

## Testing

Once set up, the webhook will receive status POSTs like:
```json
{
  "timestamp": "2026-05-25T06:30:00",
  "intelligence_hub": {"running": true, "pid": 3796},
  "ultimate_trader": {"running": true, "pid": 5492},
  "system": {"memory_percent": 35.2, "cpu_percent": 12.5},
  "logs": {
    "status": ["[timestamp] Agent X started", ...],
    "errors": [...]
  }
}
```

## Troubleshooting

If webhook is not receiving data:
1. Check VPS agent_webhook_uploader.py is running
2. Verify WEBHOOK_URL is correct
3. Confirm agents are running (should show in status)
4. Check firewall isn't blocking outbound HTTPS on VPS

## Security Note

- webhook.site URLs are public (anyone with the URL can see data)
- For production, use a private endpoint or authentication
- Never include sensitive credentials in logs
