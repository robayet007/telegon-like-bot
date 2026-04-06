# Render Deployment Guide

এই bot এখন Render-এ deploy করার জন্য ready।

## Important Security Note

আপনি chat-এ real MongoDB Atlas URI paste করেছেন। যেহেতু এতে username/password আছে, safest হবে MongoDB password rotate করা।

## 1. GitHub-এ push করুন

Repository GitHub-এ push করুন।

## 2. Render-এ new Web Service create করুন

Render dashboard এ:

1. `New +`
2. `Blueprint` অথবা `Web Service`
3. আপনার GitHub repo select করুন

এই repo-তে `render.yaml` আছে, তাই Render settings auto-detect করতে পারবে।

## 3. Required Environment Variables

Render dashboard-এ এই variables add করুন:

- `API_ID`
- `API_HASH`
- `SESSION_STRING`
- `MONGODB_URI`

Optional:

- `API_KEY`
- `MONGODB_DB`
- `MONGODB_STATE_COLLECTION`

## 4. Recommended Values

`API_KEY`
```text
BSMQ9T
```

`MONGODB_DB`
```text
ff_like_bot
```

`MONGODB_STATE_COLLECTION`
```text
bot_state
```

`MONGODB_URI`
```text
mongodb+srv://<username>:<password>@cluster0.lrzc2.mongodb.net/?retryWrites=true&w=majority&appName=Cluster0
```

## 5. Start Command

Render will use:

```text
python bot.py
```

## 6. What to expect in logs

Successful startup logs should look like:

```text
🚀 Starting Free Fire Like Bot...
✅ MongoDB connected: ...
📦 Loaded state: ...
🌐 HTTP server running on port ...
✅ Bot is running! Send /start to begin.
```

## 7. Important Notes

- `SESSION_STRING` must be valid for the main admin account
- verified super admins will also start their own Telegram sessions from MongoDB
- local `bot_state.json` is no longer needed for production
- if MongoDB is unreachable, bot may run but state persistence will not work
