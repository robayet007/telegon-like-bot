# Quick Start Guide - Vercel Deployment

## Step 1: Session String তৈরি করুন

Local machine-এ run করুন:
```bash
python convert_session.py
```

Output থেকে `SESSION_STRING` copy করুন।

## Step 2: Vercel Environment Variables

Vercel project settings → Environment Variables এ add করুন:

```
API_ID=your_api_id
API_HASH=your_api_hash  
API_KEY=BSMQ9T
SESSION_STRING=your_string_session_here
```

## Step 3: Deploy

1. GitHub-এ push করুন
2. Vercel-এ import করুন
3. Deploy করুন

## Step 4: Keep-Alive Setup

### Option A: Vercel Cron (Pro Plan)
`vercel.json` file-এ already configured আছে - automatic কাজ করবে।

### Option B: External Cron (Free)
[cron-job.org](https://cron-job.org) বা [UptimeRobot](https://uptimerobot.com) use করুন:

- **URL:** `https://your-project.vercel.app/api/keepalive`
- **Interval:** Every 5 minutes

## Important Notes

⚠️ **Vercel Serverless Limitations:**
- Functions have execution time limits (10s free, 60s pro)
- Bot connection will be active during function execution
- External cron pings keep the bot "warm" and ready

✅ **This setup will:**
- Initialize bot connection on each keepalive call
- Process messages during function execution
- Stay responsive through frequent pings

## Test

Visit: `https://your-project.vercel.app/api/status`

Expected response:
```json
{
  "status": "running",
  "bot_active": true
}
```

