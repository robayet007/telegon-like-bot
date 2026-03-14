# Keep-Alive Setup Guide

Vercel free plan-এ cron jobs limited, তাই external service use করতে হবে bot-কে 24/7 active রাখার জন্য।

## Option 1: cron-job.org (Recommended - Free)

1. Visit: https://cron-job.org
2. Free account তৈরি করুন
3. "Create cronjob" click করুন
4. Settings:
   - **Title:** FF Like Bot Keep-Alive
   - **Address (URL):** `https://ff-lke-bot.vercel.app/api/keepalive`
     (আপনার actual Vercel URL use করুন)
   - **Schedule:** Every 5 minutes
   - **Request Method:** GET
   - **Save** করুন

## Option 2: UptimeRobot (Free - 50 monitors)

1. Visit: https://uptimerobot.com
2. Free account তৈরি করুন
3. "Add New Monitor" click করুন
4. Settings:
   - **Monitor Type:** HTTP(s)
   - **Friendly Name:** FF Like Bot Keep-Alive
   - **URL:** `https://ff-lke-bot.vercel.app/api/keepalive`
   - **Monitoring Interval:** 5 minutes
   - **Save** করুন

## Option 3: EasyCron (Free - Limited)

1. Visit: https://www.easycron.com
2. Account তৈরি করুন
3. New cron job create করুন
4. Settings:
   - **URL:** `https://ff-lke-bot.vercel.app/api/keepalive`
   - **Schedule:** `*/5 * * * *` (every 5 minutes)
   - **Save** করুন

## Option 4: PythonAnywhere (Free - Daily Task)

যদি PythonAnywhere account থাকে:
1. Dashboard → Tasks
2. New task create করুন
3. Code:
   ```python
   import requests
   requests.get('https://ff-lke-bot.vercel.app/api/keepalive')
   ```
4. Schedule: Every 5 minutes

## Test Your Keep-Alive

Deploy হওয়ার পর test করুন:
```
https://ff-lke-bot.vercel.app/api/keepalive
```

Expected response:
```json
{
  "status": "ok",
  "message": "Bot is alive"
}
```

## Important Notes

- Keep-alive service প্রতি 5 মিনিটে ping করবে
- এটি bot-কে active রাখবে এবং connection maintain করবে
- Free service use করলে কিছু limitations থাকতে পারে
- Multiple services use করতে পারেন backup-এর জন্য

## Troubleshooting

**Bot not responding:**
- Keep-alive URL check করুন (correct Vercel URL)
- Vercel logs check করুন
- Environment variables verify করুন

**Connection timeout:**
- Vercel function timeout (10s free, 60s pro)
- Keep-alive endpoint optimize করা হয়েছে

