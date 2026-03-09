# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts, Streamlit dashboard, ML-powered market regime detection, and automated self-optimization.

![Arcane Portal Dashboard](https://i.imgur.com/placehold.png)

## Features

- 🔮 **Automated Signal Detection**: Swing and scalp signals using precise two-timeframe alignment
- 🧠 **Market Regime Detection**: Heuristic-based system that classifies market conditions as TRENDING or RANGING and dynamically adjusts filters — wider breakout capture on trend days, standard parameters when ranging.
- 🤖 **Auto-Optimizer**: Runs continually to dynamically adjust confidence thresholds up or down based on recent win rates, frequency, and detected market regime, preventing dry spells and system death-spirals.
- 📊 **Real-time Dashboard**: Beautiful Streamlit interface with live updates, active signals, historical performance, dynamic levels (15m through 4d), and system health metrics.
- 💬 **Discord Alerts**: Instant notifications with rich embeds (TP/SL/RR details), **dual TradingView screenshots** (HTF context chart + LTF entry chart), and automated optimizer updates.
- 🕒 **Weekend Optimization Protocol**: Automatically reduces Railway compute costs by 75% on weekends by skipping 15-minute cron intervals, completely blacking out closed TradFi markets, and lowering Crypto scraping to scalp-only timeframes.
- 🎯 **Smart Confidence Scoring**:
  - **Swing Default**: 72% minimum confidence (Auto-adjusts between 60-85%)
  - **Scalp Default**: 75% minimum confidence (Auto-adjusts between 65-88%)
- 📉 **Balanced Signal Logic**:
  - **Trend Ribbon Reading**: Accurately calculates trend direction even when TV text is null using D1/D2 structural relationship.
  - **Entry Zone**: Price must be within the Mango Dynamic zone boundaries. No additional zone position filter — the indicator defines valid entries.
  - **Candle Validation**: Minimum 15% body (allows pin-bars), Momentum confirmation (Close within top/bottom 80%).
  - **Equilibrium Tracker**: Color-aware band filtering — GREEN/RED (expanding) confirms directional conviction, BLUE/ORANGE (compressing) signals caution.
  - **Grandmaster Filter**: Swing trades respect the Daily HTF trend—never fights opposite momentum.
  - **Stop Loss**: Mango Dynamic boundaries + timeframe-specific buffers + enforced minimum risk gaps to avoid micro-wicks.
  - **Risk/Reward Scaling**: Swings target 2.75R; Scalps target 1.75R.
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
- 1D HTF → 15m LTF  *(Wider context)*

> **Active scraped timeframes:** `15m`, `1h`, `4h`, `12h`, `4d` — signals only use what the scraper actually provides.

### Entry Conditions (Balanced Approach)
1. **Trend Alignment**: LTF price must align with HTF trend.
2. **Daily Check**: Swings must not go against the 1D trend (Grandmaster filter).
3. **Chase Filter**: Rejects signal if price has already moved > 1.5x the zone width past the entry point.
4. **Candle Quality**:
   - Meaningful body size (≥15% of range, catching hammers/pin-bars).
   - **Momentum**: Close must be in the correct 80% of the candle (e.g. upper 80% for Longs). Only the worst 20% of closes are rejected.
   - **Chop Guard**: Rejects squeezing zones narrower than 0.2%.
5. **Dynamic Breakout Capture**: On trending days (detected by Market Regime Detector), price can be up to 1% beyond the zone instead of the standard 0.3%.

### TP/SL Logic
- **Stop Loss**: Placed just beyond the **Mango Dynamic boundary** with variable percentage buffers to avoid liquidation wicks. Crypto/TradFi have specific minimum SL gaps.
- **Take Profit**: Calculated based on timeframe-specific RR (Swings: 2.75R, Scalps: 1.75R).

---

## System Components & Automation

### Market Regime Detector (`detection/market_regime.py`)
Classifies the market as **TRENDING** or **RANGING** using 4 heuristic features computed from recent scrape data:

| Feature | What it measures | TRENDING signal |
|---|---|---|
| Zone escape ratio | % of assets with price far outside zone | ≥50% |
| Directional alignment | % of assets with HTF/LTF agreement | ≥60% |
| Range expansion | Candle ranges vs zone width | ≥1.5x |
| EQ expansion ratio | % of assets with expanding EQ bands | ≥60% |

When TRENDING is detected, the system automatically widens breakout capture (0.3% → 1%) and lowers confidence thresholds by 3 to capture more directional setups.

### The Auto-Optimizer (`auto_optimizer.py`)
A self-healing loop that runs periodically to evaluate the Win Rate, Signal Frequency, and Market Regime of the past 24-48 hours. **It evaluates Swings and Scalps independently.**
- If a signal type's win rate crashes, it raises its confidence threshold tightly (max 85/88).
- If win rate is excellent (>65%), it slightly loosens to catch more moves.
- If signal frequency drops below 0.3/hr, it lowers thresholds (Safety Valve) to ensure the system doesn't starve itself.
- Detects market regime and adjusts breakout capture accordingly.
- Blacklists toxic assets (0W/3L+) and enforces "Too Perfect" confidence caps.
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
│   ├── signals.py             # Signal detection & filtering logic
│   └── market_regime.py       # TRENDING/RANGING regime detector
├── dashboard/
│   └── app.py                 # Streamlit UI dashboard
├── integrations/
│   └── discord_notifier.py    # Embeds, Webhooks, Dual Image Uploads
├── auto_optimizer.py          # Dynamic threshold + regime control
├── monitor_signals.py         # Signal dispatcher and observer
├── run_signals.py             # Scraper + signal pipeline runner
├── clean_signals_db.py        # Database cleanup tool
├── analyze_signals.py         # Performance analysis tool
└── tv_state.json              # TradingView auth state
```

---

## Changelog

**Latest Update:** 2026-03-09

- **Weekend Optimization Protocol (NEW)**: Slashes Railway server costs by ~75% on Saturdays and Sundays. The system automatically shifts to 30-minute cron intervals, completely removes TradFi assets from the scraping queue (since markets are closed), and reduces Crypto scraping strictly to short-term timeframes (4H, 1H, 15m) to catch quick weekend scalps without burning compute on stationary macro charts.
- **TradingView Scraper Fixes**: Resolved an issue where the `1D` timeframe was incorrectly sending a symbol search command (`"D"`) to TradingView, resulting in placeholder $1 prices. Fixed layout parameter dropping by forcing explicit keyboard symbol entry for each asset.
- **Correlated Signal Blocker**: Added strict active signal checks to prevent identical asset/direction pairs from spamming Discord (e.g., blocking a 15m BTC Long if a 1H BTC Long is already active).
- **Stop-Loss Cooldown**: Enforces a mandatory 2-hour timeout period after an asset hits a Stop-Loss before allowing a new signal in that exact same direction.
- **Extreme Zone Penalties**: Added a `-5%` confidence penalty if price enters at the extreme outer edges (top 90% or bottom 10%) of the Mango Dynamic zone to protect against overextended "chase" entries.
- **Market Regime Detector (NEW)**: Rule-based system that classifies market conditions as TRENDING or RANGING using zone escape ratio, directional alignment, candle range expansion, and EQ band state. On trending days, the system automatically widens breakout capture from 0.3% to 1% and lowers confidence thresholds to catch more directional setups. Future Phase 2 will replace heuristics with an sklearn ML model once sufficient labeled data accumulates (~60+ days).
- **Dual Discord Screenshots**: Signal alerts now include **two charts** — the HTF context chart and the LTF entry chart. Falls back to DB-stored screenshots when the HTF timeframe wasn't scraped in the current cycle.
- **Loosened Entry Filters**: Weak close threshold reduced from 35% to 20% (pullback candles naturally close in the lower range — this was killing legitimate dip-buy entries). Zone position filter (TOO_HIGH_85%) removed entirely — if price is within the Mango Dynamic zone, that's a valid entry by definition.
- **Equilibrium Tracker Scraper Fix**: Fixed regex in `findVal` to handle dashes and negative signs in TradingView labels (e.g. `Lower VolB - 0.956`). Fixed `eqband1` matching to use negative lookahead to avoid matching `eqband2`.
- **Color-Aware Equilibrium Filtering**: Equilibrium tracker now considers band colors (GREEN=bullish expansion, RED=bearish expansion, BLUE=bullish compression, ORANGE=bearish compression) for directional confirmation.
- **Updated RR Ratios**: Swing trades unified to 2.75R across all timeframes. Scalp trades updated to 1.75R for 15m.
- **Confidence Thresholds Lowered**: Swing 85→80, Scalp 87→82 to capture near-miss setups.
- **Mango Equilibrium Tracker (Secondary Confirmation)**: Integrated the Mango Equilibrium Tracker as a secondary filter on all signals. Signals are blocked when both eqband1 AND eqband2 are below 1.0 (volatility compressing). When both are above 1.0 (expanding), a +3 confidence bonus is applied.
- **Core Direction Detection Fix**: Rewrote `_get_htf_direction` to use price position relative to the actual ribbon bands instead of comparing to entry zones.
- **Swing/Scalp LTF Ribbon Confirmation**: The LTF ribbon must explicitly confirm direction before signals fire. NEUTRAL states no longer pass through.
- **EST Day-Bookend Full Scans**: The scheduler performs full scrapes at market open (5AM EST) and close (10:30PM EST).
- **Advanced Auto-Optimizer**: Dynamic SL widening, toxic asset blacklisting, and "Too Perfect" confidence caps.
- **Railway Cost Optimization**: ~45% reduction in hourly browser load via smart scheduling.

**Built with:** Python • Streamlit • Playwright • PostgreSQL • Discord • Numpy/Pandas