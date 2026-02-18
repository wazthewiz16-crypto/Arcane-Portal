# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts and Streamlit dashboard.

![Arcane Portal Dashboard](https://i.imgur.com/placehold.png)

## Features

- 🔮 **Automated Signal Detection**: Swing and scalp signals using two-timeframe alignment
- 📊 **Real-time Dashboard**: Beautiful Streamlit interface with live updates
- 💬 **Discord Alerts**: Instant notifications with TP/SL/RR details and charts
- 🎯 **Smart Confidence Scoring**:
  - **Swing**: 68% minimum confidence
  - **Scalp**: 78% minimum confidence
- 📉 **Balanced Signal Logic**:
  - **Entry Zone**: Top/Bottom 85% of Mango Dynamic zone
  - **Candle Validation**: Minimum 0.25% body, Momentum confirmation
  - **Stop Loss**: Mango Dynamic boundaries (Natural support/resistance)
- 🌍 **Multi-Asset Support**: 18 assets (11 Crypto, 7 TradFi)
- ☁️ **Cloud Native**: Deployed on Railway with PostgreSQL database

---

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

# Database (Select ONE)
# Local Development:
DATABASE_URL=sqlite:///data/mango_scraper.db
# Production (Railway):
# DATABASE_URL=postgresql://user:pass@host:port/database

# Confidence Thresholds (Balanced Approach)
MIN_CONFIDENCE_SWING=68
MIN_CONFIDENCE_SCALP=78

# Scraper Settings
HEADLESS_BROWSER=true
```

### 3. Add TradingView State

Copy your `tv_state.json` file to the project root. This file contains your TradingView cookies.

### 4. Run the Dashboard

```bash
python -m streamlit run dashboard/app.py
```

Dashboard will be available at: **http://localhost:8501**

---

## Signal Strategy

### Two-Timeframe Alignment
- **HTF** (Higher Timeframe): Determines trend direction via Mango trend ribbons.
- **LTF** (Lower Timeframe): Determines precise entry timing within the zone.

### Timeframe Pairings
**HTF Swings** (Position trades):
- 4 Day HTF → 1 Day LTF
- 1 Day HTF → 4H LTF
- 12H HTF → 1H LTF

**LTF Scalps** (Quick trades):
- 4H HTF → 1H LTF
- 1H HTF → 15m LTF
*(3m timeframe removed for optimization)*

### Entry Conditions (Balanced Approach)
1. **Trend Alignment**: LTF price must align with HTF trend.
2. **Zone Position**: Price must be in the **optimal 85%** of the Mango Dynamic zone (not at the very edge).
3. **Candle Quality**:
   - Minimum body size: **0.25%**
   - No Dojis (Body > 40% of range)
   - **Momentum**: Close must be in the direction of trade (Upper 50% for Longs).

### TP/SL Logic
- **Stop Loss**: Placed just beyond the **Mango Dynamic boundary** (Natural Support/Resistance).
- **Take Profit**: Calculated based on timeframe-specific RR (2R - 3R).

---

## Database Management

### Cleaning the Database
To reset all signals and start fresh:
```bash
python clean_signals_db.py
```
*Note: This cleans whichever database is set in your `.env` (SQLite or Postgres).*

### Analyzing Performance
To analyze signal quality from the last 24-48 hours:
```bash
python analyze_signals.py --hours 24
```
Generates a report with:
- Win Rate & Frequency
- Performance by Asset/Timeframe
- **Actionable Recommendations** (e.g., "Increase confidence by 2%")

---

## Deployment (Railway)

The system is designed for Railway with two services:

1. **Dashboard (Streamlit)**
   - Displays live signals and history.
   - Connects to PostgreSQL.

2. **Scraper (Worker)**
   - Runs `run_signals.py` via **Cron Schedule**.
   - **Schedule**: `*/10 * * * *` (Every 10 mins).
   - **Operating Hours**: Managed via Railway Cron (e.g., exclude 11pm-5am EST).

---

## Project Structure

```
arcane-portal-v2/
├── config/
│   ├── assets.py          # 18 trading assets configuration
│   └── settings.py        # Global settings & thresholds
├── scraper/
│   ├── tradingview.py     # Playwright scraper logic
│   └── scheduler.py       # Smart timeframe selection
├── detection/
│   ├── datastore.py       # SQLite/PostgreSQL handler
│   └── signals.py         # Signal detection & filtering logic
├── dashboard/
│   └── app.py             # Streamlit dashboard
├── utils/
│   ├── logger.py          # Logging
│   └── time_window.py     # Time utilities
├── clean_signals_db.py    # Database cleanup tool
├── analyze_signals.py     # Performance analysis tool
├── data/
│   └── mango_scraper.db   # Local SQLite database
└── tv_state.json          # TradingView auth
```

---

## Support

**Latest Update:** 2026-02-18
- **Optimized**: 3m timeframe removed.
- **Improved**: Momentum & Zone filters added.
- **Stack**: Multi-DB support (SQLite/Postgres).

**Built with:** Python • Streamlit • Playwright • PostgreSQL • Discord