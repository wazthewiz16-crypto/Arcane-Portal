# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts, Streamlit dashboard, and automated self-optimization.

![Arcane Portal Dashboard](https://i.imgur.com/placehold.png)

## Features

- 🔮 **Automated Signal Detection**: Swing and scalp signals using precise two-timeframe alignment
- 🤖 **Auto-Optimizer**: Runs continually to dynamically adjust confidence thresholds up or down based on recent win rates and frequency, preventing dry spells and system death-spirals.
- 📊 **Real-time Dashboard**: Beautiful Streamlit interface with live updates, active signals, historical performance, dynamic levels (15m through 4d), and system health metrics.
- 💬 **Discord Alerts**: Instant notifications with rich embeds (TP/SL/RR details), full TradingView screenshots, and automated optimizer updates.
- 🎯 **Smart Confidence Scoring**:
  - **Swing Default**: 72% minimum confidence (Auto-adjusts between 60-85%)
  - **Scalp Default**: 75% minimum confidence (Auto-adjusts between 65-88%)
- 📉 **Balanced Signal Logic**:
  - **Trend Ribbon Reading**: Accurately calculates trend direction even when TV text is null using D1/D2 structural relationship.
  - **Entry Zone**: Optimized to capture trades within the Mango Dynamic limits.
  - **Candle Validation**: Minimum 15% body (allows pin-bars), Momentum confirmation (Close within top/bottom 65%).
  - **Grandmaster Filter**: Swing trades respect the Daily HTF trend—never fights opposite momentum.
  - **Stop Loss**: Mango Dynamic boundaries + timeframe-specific buffers + enforced minimum risk gaps to avoid micro-wicks.
  - **Risk/Reward Scaling**: Swings target 2.3R to 2.7R; Scalps target 1.2R to 1.6R.
- 🌍 **Multi-Asset Support**: Broad market support handling both Crypto and TradFi asset specifics.
- ☁️ **Cloud Native**: Deployed on Railway using a Neon Serverless PostgreSQL database.

---

## Quick Start

### 1. Installation

```bash
# Clone the repository
git clone https://github.com/wazthewiz16-crypto/Arcane-Portal.git
cd Arcane-Portal

# Create and activate virtual environment
python -m venv venv
venv\Scripts\activate  # Windows
# source venv/bin/activate  # Mac/Linux

# Install dependencies
pip install -r requirements.txt

# Install Playwright browser
playwright install chromium
```

### 2. Configuration

Create a `.env` file in the root directory:

```bash
# Discord Integration
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_URL

# Database (Neon Serverless PostgreSQL recommended)
DATABASE_URL=postgresql://user:pass@ep-host.region.aws.neon.tech/neondb?sslmode=require

# Scraper Settings
HEADLESS_BROWSER=true
```

### 3. Add TradingView State

Copy your `tv_state.json` file to the project root. This file contains your active TradingView session cookies required for headless scraping.

### 4. Run the System

```bash
# Terminal 1: Run the Dashboard
python -m streamlit run dashboard/app.py

# Terminal 2: Run the Background Monitor
python monitor_signals.py
```

Dashboard will be available at: **http://localhost:8501**

---

## Signal Strategy

### Two-Timeframe Alignment
- **HTF** (Higher Timeframe): Determines trend direction via Mango trend ribbons (D1/D2 correlation).
- **LTF** (Lower Timeframe): Determines precise entry timing within the zone.

### Timeframe Pairings
**HTF Swings** (Position trades):
- 4 Day HTF → 1 Day LTF
- 1 Day HTF → 4H LTF
- 4H HTF → 1H LTF  *(Faster reaction)*
- 12H HTF → 1H LTF *(Slower fallback)*

**LTF Scalps** (Quick trades):
- 4H HTF → 15m LTF  *(Primary combo)*
- 1H HTF → 15m LTF  *(Tighter confirmation)*

> **Active scraped timeframes:** `15m`, `1h`, `4h`, `12h`, `4d` — signals only use what the scraper actually provides.

### Entry Conditions (Balanced Approach)
1. **Trend Alignment**: LTF price must align with HTF trend.
2. **Daily Check**: Swings must not go against the 1D trend (Grandmaster filter).
3. **Chase Filter**: Rejects signal if price has already moved > 1.5x the zone width past the entry point.
4. **Candle Quality**:
   - Meaningful body size (≥15% of range, catching hammers/pin-bars).
   - **Momentum**: Close must be in the correct 65% of the candle (e.g. upper 65% for Longs).
   - **Chop Guard**: Rejects squeezing zones narrower than 0.2%.

### TP/SL Logic
- **Stop Loss**: Placed just beyond the **Mango Dynamic boundary** with variable percentage buffers to avoid liquidation wicks. Crypto/TradFi have specific minimum SL gaps.
- **Take Profit**: Calculated based on timeframe-specific RR.

---

## System Components & Automation

### The Auto-Optimizer (`auto_optimizer.py`)
A self-healing loop that runs periodically to evaluate the Win Rate and Signal Frequency of the past 24-48 hours. **It evaluates Swings and Scalps independently.**
- If a signal type's win rate crashes, it raises its confidence threshold tightly (max 85/88).
- If win rate is excellent (>65%), it slightly loosens to catch more moves.
- If signal frequency drops below 0.3/hr, it lowers thresholds (Safety Valve) to ensure the system doesn't starve itself.
*It updates parameters directly in the database and sends plain-text reports to Discord.* 

**Recommended Schedule:** Run 3x daily (e.g. 3am, 9:30am, 5pm EST) via Railway Cron or external scheduler to capture post-session resolutions.

### Continuous Monitoring (`monitor_signals.py`)
The primary execution script.
- Watches the database for new signals.
- Interfaces with `discord_notifier.py` to post high-quality PNG charts.
- Validates the active state to pause execution natively on Windows/Linux environments.

---

## Database Management

To reset all signals and start fresh:
```bash
python clean_signals_db.py
```
*Note: This cleans whichever database is set in your `.env`.*

To manually analyze signal quality from the last 24-48 hours:
```bash
python analyze_signals.py --hours 24
```

---

## Project Structure

```
Arcane-Portal/
├── config/
│   ├── assets.py              # Trading assets configuration
│   └── settings.py            # Global fallback settings
├── scraper/
│   ├── tradingview.py         # Playwright scraper logic
│   └── scheduler.py           # Smart timeframe polling
├── detection/
│   ├── datastore.py           # PostgreSQL / SQLite handler
│   └── signals.py             # Signal detection & filtering logic
├── dashboard/
│   └── app.py                 # Streamlit UI dashboard
├── integrations/
│   └── discord_notifier.py    # Embeds, Webhooks, Image Uploads
├── auto_optimizer.py          # Dynamic threshold control script
├── monitor_signals.py         # Signal dispatcher and observer
├── clean_signals_db.py        # Database cleanup tool
├── analyze_signals.py         # Performance analysis tool
└── tv_state.json              # TradingView auth state
```

---

## Support

**Latest Update:** 2026-02-28
- **Critical Bug Fix**: Scraper was silently storing corrupt `close=1.0` placeholder values into the 1D database table, corrupting the Grandmaster Filter and breaking the 4D→1D swing chain. Fixed and 335 corrupted rows purged.
- **Self-Healing**: Auto-optimizer now evaluating swings vs scalps independently + safety valve.
- **Improved Entries**: Integrated "Chase Filter" to reject late setups when HTF ribbon lags.
- **Tighter Swings**: Added 4H→1H swing combination to catch market reversals faster.
- **Cleanup**: Removed dead scalp combos (5m, 30m) that were never being scraped.

**Built with:** Python • Streamlit • Playwright • PostgreSQL • Discord • Numpy/Pandas