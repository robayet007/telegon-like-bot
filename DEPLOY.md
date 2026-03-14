# Vercel Deployment Guide

এই guide অনুসরণ করে আপনার bot Vercel-এ deploy করুন যাতে এটি 24 ঘণ্টা active থাকে।

## Prerequisites

1. Vercel account (free tier works)
2. GitHub account (Vercel-এ deploy করার জন্য)
3. Session file (`ff_like_bot.session`) local machine-এ থাকতে হবে

## Step 1: Session String তৈরি করুন

1. Local machine-এ এই command run করুন:
   ```bash
   python convert_session.py
   ```

2. Output থেকে `SESSION_STRING` copy করুন (এটি একটি long string হবে)

## Step 2: GitHub-এ Push করুন

1. এই project-টি GitHub-এ push করুন:
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin your-github-repo-url
   git push -u origin main
   ```

## Step 3: Vercel-এ Deploy করুন

1. [Vercel](https://vercel.com) এ login করুন
2. "New Project" click করুন
3. আপনার GitHub repository select করুন
4. Project settings:
   - **Framework Preset:** Other
   - **Root Directory:** ./
   - **Build Command:** (leave empty)
   - **Output Directory:** (leave empty)

## Step 4: Environment Variables Setup করুন

Vercel project settings-এ "Environment Variables" section-এ এই variables add করুন:

```
API_ID=your_api_id_here
API_HASH=your_api_hash_here
API_KEY=BSMQ9T
SESSION_STRING=your_string_session_from_step_1
```

⚠️ **Important:** `SESSION_STRING` হল সবচেয়ে important - এটি আপনার bot-এর authentication key।

## Step 5: Deploy করুন

1. "Deploy" button click করুন
2. Deployment complete হওয়ার জন্য wait করুন

## Step 6: Cron Job Setup (24h Active রাখার জন্য)

Vercel automatically `vercel.json` file থেকে cron jobs setup করবে। 

Cron job প্রতি 5 মিনিটে `/api/keepalive` endpoint call করবে, যা bot-কে active রাখবে।

## Verification

1. Deploy হওয়ার পর, এই URL visit করুন:
   ```
   https://your-project.vercel.app/api/status
   ```

2. Response দেখুন:
   ```json
   {
     "status": "running",
     "bot_active": true
   }
   ```

3. Keep-alive check করুন:
   ```
   https://your-project.vercel.app/api/keepalive
   ```

## Troubleshooting

### Bot active হচ্ছে না
- Check করুন environment variables সঠিকভাবে set করা হয়েছে কিনা
- Vercel logs check করুন (Project → Deployments → View Function Logs)

### Session expired
- Local machine-এ `convert_session.py` run করুন
- নতুন `SESSION_STRING` Vercel environment variables-এ update করুন
- Redeploy করুন

### Cron job কাজ করছে না
- Vercel Pro plan প্রয়োজন হতে পারে free tier-এ cron jobs-এর জন্য
- Alternative: External cron service ব্যবহার করুন (যেমন cron-job.org) যা প্রতি 5 মিনিটে `/api/keepalive` call করবে

## Free Alternative (Cron Jobs)

যদি Vercel free tier-এ cron jobs না থাকে, তাহলে:

1. [cron-job.org](https://cron-job.org) এ account তৈরি করুন
2. New cron job create করুন:
   - **URL:** `https://your-project.vercel.app/api/keepalive`
   - **Schedule:** Every 5 minutes
   - **Request Method:** GET

এটি bot-কে 24/7 active রাখবে।

## Notes

- Bot Vercel-এ serverless function হিসেবে run হবে
- প্রতি 5 মিনিটে keep-alive ping bot-কে active রাখবে
- Session string secure রাখুন - কখনো public করবেন না
- Environment variables update করতে হলে Vercel dashboard থেকে update করুন এবং redeploy করুন

