# Free Fire Like Bot

A Telegram user bot built with Telethon that sends likes to Free Fire players using their UID.

## Features

- Send likes to Free Fire players via Telegram commands
- Real-time API integration with FF Like API
- Formatted response messages showing:
  - Likes given
  - Player information
  - Daily and monthly usage statistics
  - Status updates

## Prerequisites

- Python 3.7 or higher
- Telegram API ID and API Hash (get from [my.telegram.org/apps](https://my.telegram.org/apps))
- FF API Key (default: BSMQ9T)

## Installation

1. **Clone or download this repository**

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Set up environment variables:**
   - Copy `.env.example` to `.env`
   - Edit `.env` and fill in your credentials:
     ```
     API_ID=your_api_id_here
     API_HASH=your_api_hash_here
     API_KEY=BSMQ9T
     ```

## Usage

1. **Run the bot:**
   ```bash
   python bot.py
   ```

2. **First time setup:**
   - Enter your phone number when prompted
   - Enter the verification code sent to your Telegram
   - If you have 2FA enabled, enter your password

3. **Using the bot:**
   - Send `/like <uid>` to give likes to a player
   - Example: `/like 1711537287`
   - The bot will respond with formatted results

## Commands

- `/start` - Show welcome message
- `/help` - Show help information
- `/like <uid>` - Send likes to a Free Fire player (e.g., `/like 1711537287`)

## Example Response

```
🎮 Free Fire Like Bot

✅ Likes Given: 100
👤 Player: —RATUL 3>❤️
🆔 UID: 1711537287
📊 Status: ✅ Success

📈 Daily Usage: 8/100 (92 remaining)
📅 Monthly Usage: 15/3000 (2985 remaining)

🔑 Key: xpopu02
```

## Notes

- This is a **user bot** (not a bot account), so it uses your personal Telegram account
- The bot will create a session file (`ff_like_bot.session`) for authentication
- Keep your `.env` file secure and never share it
- API rate limits apply based on your API key configuration

## Troubleshooting

**Error: "API_ID not found"**
- Make sure you've created a `.env` file from `.env.example`
- Verify your API_ID and API_HASH are correct

**Error: "Session password needed"**
- Enter your 2FA password when prompted

**Error: "Request timeout"**
- The API server may be slow or unavailable
- Try again after a few moments

## License

This project is for educational purposes.

