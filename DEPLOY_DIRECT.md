# Direct Vercel Deployment (Without GitHub)

এই guide অনুসরণ করে Vercel CLI দিয়ে directly deploy করুন।

## Step 1: Vercel CLI Install করুন

PowerShell এ run করুন:
```powershell
npm install -g vercel
```

## Step 2: Vercel Login করুন

```powershell
vercel login
```

Browser open হবে, login করুন।

## Step 3: Environment Variables Setup করুন

`.env` file check করুন - `API_ID` এবং `API_HASH` আছে কিনা।

## Step 4: Deploy করুন

Project directory-তে run করুন:

```powershell
vercel
```

First time-এ কিছু questions আসবে:
- **Set up and deploy?** → `Y`
- **Which scope?** → আপনার account select করুন
- **Link to existing project?** → `N` (new project)
- **Project name?** → `ff-like-bot` (বা আপনার পছন্দের নাম)
- **Directory?** → `.` (current directory)

## Step 5: Environment Variables Add করুন

Deploy হওয়ার পর, Vercel dashboard-এ যান:
1. Project select করুন
2. **Settings** → **Environment Variables**
3. এই variables add করুন:

```
API_ID=your_api_id
API_HASH=your_api_hash
API_KEY=BSMQ9T
SESSION_STRING=1BVtsOJABuyqDGOMuc_PnUB_xa5-Bvmn9UBkXblN_O0aw-mdjx9WdtBZsBegrZyNyAcTQ2VYe4AzWbfo3AiishskcNSb8jLINZRnZoL5VlanB1L7pQit1QktNIEs2qtqspLt9FKVEeS5kR8AA55NYmyy7z0-WLsWGepah6XBJolLh62BiuRoiutq7Gr2Zb-82MhAL3ldbzI_V4d1eefMnNgJZCxAJ-sh1uFWYUBFpxVER3Jduk-DC-hG06w_VF09U98agD4wUSmA0EIldaTg-qsxCXdpIx_i-ZMpUF1KD6ShFBndUZblpHIvARyx-k4MVTf4XyyzCcoc-HAk6lh3KHNh69NPYs9g=
```

## Step 6: Redeploy করুন

Environment variables add করার পর, redeploy করুন:

```powershell
vercel --prod
```

## Step 7: Keep-Alive Setup

### Option A: Vercel Cron (Pro Plan)
Automatic কাজ করবে `vercel.json` থেকে।

### Option B: External Cron (Free)
[cron-job.org](https://cron-job.org) use করুন:
- **URL:** `https://your-project.vercel.app/api/keepalive`
- **Schedule:** Every 5 minutes

## Verification

Deploy হওয়ার পর test করুন:
```
https://your-project.vercel.app/api/status
```

## Quick Commands

```powershell
# Deploy to preview
vercel

# Deploy to production
vercel --prod

# View logs
vercel logs

# List projects
vercel ls
```

## Troubleshooting

**Error: "API_ID not found"**
- Vercel dashboard-এ environment variables check করুন
- Redeploy করুন

**Error: "Session not authorized"**
- SESSION_STRING সঠিক কিনা check করুন
- Local-এ `convert_session.py` run করে নতুন string নিন

**Bot not responding**
- Keep-alive endpoint check করুন
- External cron setup করুন যদি Vercel cron না থাকে

