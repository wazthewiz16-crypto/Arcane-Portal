# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts and Streamlit dashboard.

## Features

- 🔮 **Automated Signal Detection**: Swing and scalp signals using two-timeframe alignment
- 📊 **Real-time Dashboard**: Beautiful Streamlit interface with live updates
- 💬 **Discord Alerts**: Instant notifications with TP/SL/RR details
- 🎯 **Smart Confidence Scoring**: 40% minimum for swings, 65% for scalps
- 📈 **TP/SL Calculation**: Automatic risk-reward based targets
- 🌍 **Multi-Asset Support**: 17 assets (10 crypto, 7 TradFi)
- ⏰ **Market Hours Aware**: TradFi signals only Monday-Friday

## Quick Start

### 1. Installation

```bash
# Clone the repository
cd arcane-portal-v2

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Configuration

Create a `.env` file (copy from `.env.example`):

```bash
# Discord Integration
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# Confidence Thresholds
MIN_CONFIDENCE_SWING=40
MIN_CONFIDENCE_SCALP=65

# Scraper Settings
HEADLESS_BROWSER=true
```

**Get Discord Webhook:**
1. Go to your Discord server settings
2. Integrations → Webhooks → New Webhook
3. Copy the webhook URL
4. Paste into `.env` file

### 3. Add TradingView State

Copy your `tv_state.json` file to the project root. This file contains your TradingView authentication cookies.

### 4. Run the Dashboard

```bash
streamlit run dashboard/app.py
```

Dashboard will be available at: **http://localhost:8501**

## Dashboard Features

### 🚨 Active Signals Tab
- Real-time signal cards with entry/TP/SL
- Filter by signal type (Swing/Scalp)
- Filter by direction (Long/Short)
- Filter by asset type (Crypto/TradFi)
- Color-coded confidence levels

### 📊 History Tab
- View signals from last 6/12/24/48/72 hours
- Summary statistics (total, active, avg confidence, avg RR)
- Sortable table with all signal details

### 👁️ Assets Tab
- Monitor all 17 tracked assets
- Current prices and entry zones
- HTF/LTF timeframe pairs
- Entry zone status indicators

### ⚙️ System Health (Sidebar)
- Scraper status and last run time
- Tracked asset count
- Active signal count
- Auto-refresh toggle (60s intervals)

## Signal Strategy

### Two-Timeframe Alignment
- **HTF** (Higher Timeframe): Determines trend direction
- **LTF** (Lower Timeframe): Determines entry timing

### Timeframe Pairings

**HTF Swings** (Position trades):
- 4 Day HTF → 1 Day LTF
- 1 Day HTF → 4H LTF
- 12H HTF → 1H LTF

**LTF Scalps** (Quick trades):
- 4H HTF → 1H LTF
- 1H HTF → 15m LTF
- 15m HTF → 3m LTF

### Entry Conditions
- Price above/below Mango D2 (HTF direction)
- Price inside Mango Dynamic OR within bid zone (LTF entry)

### TP/SL Logic
- **Stop Loss**: Entry zone boundary (opposite side)
- **Take Profit**: 2.5:1 RR for swings, 2:1 for scalps

## Discord Alert Format

```
🚨 SWING LONG - BTC
━━━━━━━━━━━━━━━━━━
📊 Timeframes: 4h → 1h
💰 Entry Price: $42,250
🎯 Take Profit: $44,500
🛡️ Stop Loss: $41,100
📈 RR: 2.5:1
🎲 Confidence: 85%
⏰ Entry Time: 2026-02-10 09:35 UTC
```

## Testing

Run tests for each phase:

```bash
# Phase 2: Core Infrastructure
python test_phase2.py

# Phase 3: Signal Detection
python test_phase3.py

# Phase 4: Discord Integration
python test_phase4.py

# Phase 5: Streamlit Dashboard
python test_phase5.py
```

## Project Structure

```
arcane-portal-v2/
├── config/
│   ├── assets.py          # 17 trading assets
│   └── settings.py        # Configuration management
├── scraper/
│   ├── tradingview.py     # Playwright scraper
│   └── scheduler.py       # Background jobs
├── detection/
│   ├── datastore.py       # SQLite database
│   └── signals.py         # Signal detection logic
├── integrations/
│   └── discord_notifier.py # Discord webhook alerts
├── dashboard/
│   └── app.py             # Streamlit dashboard
├── utils/
│   └── logger.py          # Logging utilities
├── data/
│   └── mango_scraper.db   # SQLite database (auto-created)
├── .env                   # Environment variables (create this)
├── tv_state.json          # TradingView auth (required)
└── requirements.txt       # Python dependencies
```

## Deployment (Railway)

See deployment guide in Phase 6 documentation.

## Troubleshooting

### Dashboard won't start
- Ensure all dependencies installed: `pip install -r requirements.txt`
- Check Python version: 3.10+ required

### No signals appearing
- Verify `tv_state.json` is in project root
- Check scraper is running (System Health sidebar)
- Ensure assets have recent data in database

### Discord alerts not sending
- Verify `DISCORD_WEBHOOK_URL` in `.env`
- Test webhook: `python -c "from integrations.discord_notifier import DiscordNotifier; DiscordNotifier().send_test_alert()"`

### TradFi signals on weekends
- TradFi signals only generate Monday-Friday
- Crypto signals work 24/7

## Support

For issues or questions, check the implementation plan and task list in `.gemini/antigravity/brain/`.

---

**Built with:** Python • Streamlit • Playwright • SQLite • Discord Webhooks

**Strategy:** Mango Dynamic Indicator • Two-Timeframe Alignment