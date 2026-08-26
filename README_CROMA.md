# Croma Stock & Pincode Availability Checker with Telegram Alerts

A Python script that monitors product stock availability on **Croma.com** across specified postal PIN codes and sends instant alerts to your Telegram chat whenever an item is in stock.

---

## 🚀 Features

- 📱 **Multi-Product Monitoring**: Add any Croma product link (e.g. iPhone variants, colors, laptops, etc.).
- 📍 **Multi-Pincode Support**: Monitor stock availability across multiple Indian postal pincodes simultaneously.
- ⚡ **Dual Checking Strategy**:
  - **Fast API Mode**: Queries Croma delivery APIs for instant results.
  - **Browser Fallback (Playwright)**: Launches headless browser if Croma anti-bot / Cloudflare protection blocks standard API requests.
- 💬 **Rich Telegram Alerts**: Formatted HTML notification with product title, pincode, price, status, and direct purchase link.
- ⏱ **Smart Cooldown**: Configurable cooldown interval to prevent notification spamming for items that remain in stock.

---

## 🛠️ Setup Instructions

### 1. Install Dependencies

Ensure Python 3.8+ is installed on your system. Run:

```bash
pip install -r requirements.txt
```

*(Optional for browser fallback)* If you want Playwright browser fallback enabled:
```bash
playwright install chromium
```

---

### 2. Configure Telegram Bot

1. **Create Telegram Bot**:
   - Open Telegram and search for [@BotFather](https://t.me/BotFather).
   - Send `/newbot` and follow instructions to get your **Bot Token** (e.g., `123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ`).

2. **Get Your Chat ID**:
   - Open Telegram and search for [@userinfobot](https://t.me/userinfobot) (or add your bot to a channel/group).
   - Send any message to [@userinfobot](https://t.me/userinfobot) to get your numeric **Chat ID** (e.g., `987654321`).

---

### 3. Update `config.json`

Edit `config.json` in the project directory:

```json
{
  "telegram": {
    "bot_token": "YOUR_TELEGRAM_BOT_TOKEN",
    "chat_id": "YOUR_TELEGRAM_CHAT_ID"
  },
  "pincodes": [
    "400001",
    "110001",
    "560001"
  ],
  "products": [
    "https://www.croma.com/apple-iphone-17-256gb-black-/p/317396"
  ],
  "settings": {
    "check_interval_seconds": 60,
    "use_playwright_fallback": true
  }
}
```

- **`products`**: Add as many Croma product URLs or variant links as you want.
- **`pincodes`**: Add all pincodes you want to check for delivery stock.
- **`check_interval_seconds`**: Frequency of checking cycle (in seconds).

Each pass sends at most **one** Telegram message, summarizing every city/product/pincode combination found in stock during that pass (grouped as "City → Product → Pincodes"). This avoids a burst of near-duplicate messages when a whole city has stock at once.

---

## ☁️ GitHub Actions Deployment (Automatic 1-Hour Schedule)

The repository includes an automated GitHub Actions workflow (`.github/workflows/croma_checker.yml`) that runs every hour on GitHub's cloud servers for free.

### Step 1: Push Code to GitHub
1. Create a repository on GitHub.
2. Push your project code:
   ```bash
   git init
   git add .
   git commit -m "Add Croma stock checker bot"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/croma-stock-checker.git
   git push -u origin main
   ```

### Step 2: Add GitHub Repository Secrets
To safely pass your Telegram credentials without committing tokens into your git repository:

1. Open your GitHub Repository -> Go to **Settings**.
2. On the left sidebar, click **Secrets and variables** -> **Actions**.
3. Click **New repository secret**:
   - Secret Name: `TELEGRAM_BOT_TOKEN`
   - Secret Value: *Your Telegram Bot Token*
4. Click **New repository secret** again:
   - Secret Name: `TELEGRAM_CHAT_ID`
   - Secret Value: *Your Telegram Chat ID*

---

## 🎯 How to Run Locally

### Test Telegram Configuration
To verify your Telegram Bot Token and Chat ID are working:
```bash
python croma_checker.py --test-telegram
```

### Run a Single Check Pass
To run a one-time check without looping:
```bash
python croma_checker.py --once
```

### Run Continuous Stock Monitoring Loop
To start background monitoring:
```bash
python croma_checker.py
```

---

## 📊 Output Log Example

```text
2026-08-24 00:35:00 [INFO] --- Starting Stock Checking Pass ---
2026-08-24 00:35:01 [INFO] Checking product: https://www.croma.com/apple-iphone-17-256gb-black-/p/317396 | Pincode: 400001
2026-08-24 00:35:02 [INFO] ✅ IN STOCK! Product: Apple iPhone 17 (256GB, Black) | Pincode: 400001 | Price: ₹79,900
2026-08-24 00:35:03 [INFO] Telegram message sent successfully.
```
