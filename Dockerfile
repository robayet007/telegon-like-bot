FROM python:3.11-slim

# Optional: system deps (কম রাখলাম, দরকার হলে বাড়াবেন)
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# কাজের ডিরেক্টরি
WORKDIR /app

# প্রথমে শুধু requirements কপি করে ইনস্টল
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# তারপর বাকি পুরো কোড + session ফাইল কপি
COPY . .

# লগ যেন সাথে সাথে দেখা যায়
ENV PYTHONUNBUFFERED=1

# Env var গুলো Render-এ সেট করবেন:
# API_ID, API_HASH, API_KEY (optional, default BSMQ9T)

# Container start হলে bot.py চালাবে
CMD ["python", "bot.py"]