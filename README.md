# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts, Streamlit dashboard, ML-powered market regime detection, and automated self-optimization.

![Arcane Portal Dashboard](https://i.imgur.com/placehold.png)

## Features

- 🔮 **Automated Signal Detection**: Swing and scalp signals using precise two-timeframe alignment
- 🥭 **Mango Research Premium Dashboard Integration**: Natively scrapes `app.mangoresearch.co` in the background (with 2-hour rate-limiting to optimize compute costs) using Playwright. Captures high-fidelity individual asset trend badges, asset volatility, global market trend, and overall market volatility:
  - **Global Trend Opposite Blocking:** Blocks LONG signals if overall market trend is SHORT, and SHORT signals if overall market trend is LONG.
  - **Refined Volatility Quality Gates:** Low volatility (`<30` - Blue) bypasses compression filters and gets a `+10%` confidence boost, while high overall or high timeframe (`4H`, `12H`, `1D`) volatility `>=80` (Red) blocks entries completely.
  - **Custom MTF Button Preset Verification:** Automatically validates your signals against the custom **Mango Bullish** (4H, 12H, 1D Golden Cross + 2D, 4D LONG) and **Mango Bearish** (4H, 12H, 1D Death Cross + 2D, 4D SHORT) dashboard presets.
  - **Gold Embed Alerts:** Standard signals display dedicated premium confluence metrics, while dashboard-native badge flips fire separate, visually stunning gold-coloured alerts with a multi-timeframe alignment grid.
- 🧠 **Market Regime Detection**: Machine Learning (Random Forest) based system trained on historical 4H rolling data that classifies market conditions as TRENDING or RANGING and dynamically adjusts filters. The model automatically retrains itself every Saturday at 5:00 AM EST and pushes its accuracy metrics and feature importances straight to Discord!
- 🤖 **Auto-Optimizer**: Runs continually to dynamically adjust confidence thresholds up or down based on recent win rates, frequency, and detected market regime, preventing dry spells and system death-spirals.
- 📡 **Trade Radar**: Automatically pushes the top 5 "Prime" active trades (ideal pullbacks and near-entry trades) to Discord 4 times a day, allowing you to catch high-probability setups without watching charts.
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
  - **Partial Take Profit (1R → Breakeven)**: When price moves +1R in your favour the system marks partial TP hit, moves the stop-loss to the entry price (breakeven) and lets the remaining position ride to the full target. Losing trades that reached +1R before reversing now close as `BREAKEVEN` instead of `SL_HIT`.
  - **Risk/Reward Scaling**: Swings target 2.75R; Scalps target 1.75R.
- 🚫 **Correlated Positions Cap**: Prevents stacking more than 2 crypto positions in the same direction simultaneously (e.g. BTC + ETH + SOL + ARB all SHORT at once). When the cap is reached new signals in that direction are suppressed until an existing one closes, capping portfolio-wide correlated risk.
- 📐 **Minimum SL Floor for Crypto Scalps**: Crypto scalp stop-losses are now enforced to a minimum of 1.8% from entry (up from 1.5%) to avoid being wick-hunted on volatile 15m candles.
- 🌍 **Multi-Asset Support**: Broad market support handling both Crypto and TradFi asset specifics.
- ₿ **BTC Macro Context Filter**: All altcoin signals are validated against the live BTC price trend and BTC Dominance (BTC.D) direction before firing. The system implements the full Bitcoin Dominance Cycle:
  - **ALT_DUMP** (BTC.D ↑ + BTC ↓): Altcoin LONG signals blocked entirely; SHORT signals get +7 confidence bonus.
  - **ALT_BEARISH** (BTC.D ↑ + BTC ↑): Altcoin LONG signals blocked; SHORT signals get +3 confidence bonus.
  - **ALT_SEASON** (BTC.D ↓ + BTC ↑): Altcoin SHORT signals blocked; LONG signals get +5 confidence bonus.
  - **ALT_NEUTRAL / ALT_SLIGHTLY_BULLISH**: Small confidence adjustments with no hard blocks.
  - BTC itself and all TradFi assets are exempt from this filter.
- 🧹 **Automated Database Maintenance**: The system runs a silent self-cleaning protocol on every startup. It permanently deletes massive Discord screenshots older than 7 days and raw scraper data older than 60 days, ensuring your Railway PostgreSQL database stays highly optimized and never breaches the 500 MB capacity limit.
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

Run the automated interactive login script to securely authenticate your TradingView session:
```bash
python interactive_login.py
```
A browser will open—log into TradingView, return to the terminal, and press ENTER. The script will securely rip the active session cookies and upload them directly to your Railway PostgreSQL database. 

The background scraper pulls the authentication state from the database and uses **Rolling Sessions** (it re-uploads its fresh cookies back to the database at the end of every hour) so your TradingView session theoretically never expires!

### 4. Add Mango Research Session State

Run the automated interactive login script for Mango Research to securely capture your dashboard session:
```bash
python interactive_login_mango.py
```
A browser will open—manually log into your premium Mango Research account. Once logged in and viewing the main dashboard, return to the terminal and press ENTER. The script will securely rip the active session storage and cookies, uploading them directly to your Railway PostgreSQL database as `MANGO_DASHBOARD_STATE` (and creating a local backup in `mango_state.json`).

The background scraper retrieves this state from the database to securely run Playwright headless tasks on Railway without needing login credentials.

### 5. Run the System

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

### Trade Radar (`trade_radar.py`)
A secondary digest system designed for part-time monitoring. Evaluates all open positions and filters for "Prime" setups (trades currently in a slight pullback or resting exactly at entry, avoiding trades that are too close to stop-loss or already heavily in profit). It ranks them by a blend of confidence and PnL%, then automatically pushes a summary of the top 5 trades to Discord at **8 AM, 12 PM, 4 PM, and 8 PM EST**. No separate cron required; it's integrated natively into `run_signals.py`.

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

**Latest Update:** 2026-05-22

- **Mango Premium Volatility Rules, Timeframe Upgrades, and New Assets (NEW)**:
  - **Refined Volatility Rules**: Implemented unified volatility gates. Low volatility (`< 30` - Blue) is safe and encouraged, bypassing all compression blocks and receiving a **`+10%` confidence boost** (capped at `100%`). High volatility (`>= 80` - Red) indicates extreme trend exhaustion and **blocks trades completely** if the overall volatility or any high timeframe (`4H`, `12H`, `1D`) volatility is `>= 80`.
  - **Base Timeframe Upgrade**: Shifted the default base timeframe for all Mango Dashboard calculations and native signals from `"4H"` to `"1D"` to capture macro structural trends more reliably.
  - **Scraping Coverage Expansion**: Added 4 highly requested crypto assets to both TradingView and Mango Research Dashboard scraping pipelines: `TRXUSDT`, `INJUSDT`, `ONDOUSDT`, and `NEARUSDT`.
  - **Enriched Discord Embeds & Technical Flags**: Enhanced standard TV and Mango-native alerts to display the active timeframe (`📊 Timeframe: 1D`) and format guide-matching technical flags with color-coded bullet points (🟢 green for bullish/confirming flags like `Golden Cross` or `Cheap / Discount`, 🔴 red for contrarian/bearish flags like `Death Cross` or `Expensive / Premium`).

- **Mango Research Scraper & Dynamic Volatility Resolution (NEW)**:
  - **Sequential Tab Scraping**: Refactored the Playwright scraper into sequential, fully-isolated Crypto and TradFi scraping phases with 8-second tab-switching delays to prevent memory leaks and timeouts on Railway.
  - **Watchlist Filtering Optimization**: Restricted detail-page crawling strictly to core traded assets (`CORE_SCRAPE_ASSETS`) to prevent browser lockups and massive page-goto overhead.
  - **Integer Trend Correction**: Decoded API trends (`0` = NEUTRAL, `1` = LONG, `2` = SHORT) in both global and detail sniffer responses to resolve the issue where crypto/TradFi assets were shown as "UNLISTED".
  - **Bollinger Band Width Percentile (`bbwp`) Volatility**: Switched sniffers to parse `"bbwp"` first to fetch real, high-fidelity volatility values instead of default/neutral `50` values.
- **Swing Trade Volatility Exhaustion Filter (NEW)**:
  - Added a dual-tier volatility gate for Swing trades evaluating both overall asset and timeframe-specific (4H, 12H, 1D) volatilities:
    - **Extreme Volatility (> 90)**: Blocks Swing trade entry completely to avoid entering exhausted trends.
    - **High Volatility (85 to 90)**: Deducts 20.0% from signal confidence and appends a warning badge (`⚠️ High Volatility (Exhaustion Risk)`).
- **Mango Research Premium Dashboard Integration**: Natively scrapes `app.mangoresearch.co` in the background (with 2-hour rate-limiting to optimize compute costs) using Playwright with robust network sniffing and DOM-parsing fallbacks.
- **Global Market Trend Opposite Blocking**: Blocks standard TradingView signals from firing if they fight the overall global market trend (e.g., blocking LONG signals when the market is in a global SHORT regime).
- **Scalp Volatility Filters**: Enforces individual asset volatility gates for scalp signals, filtering out trades in extreme exhaustion zones (`>85`) or dormant compression zones (`<25`).
- **Custom MTF Button Preset Verification**: Validates signals against custom **Mango Bullish** (4H, 12H, 1D Golden Cross + 2D, 4D LONG) and **Mango Bearish** (4H, 12H, 1D Death Cross + 2D, 4D SHORT) dashboard presets. Standard TradingView Discord embeds now print these preset alignment statuses under a premium "Mango Premium Confluence" panel.
- **Mango-Native Signal Detection (NEW)**: Created a separate, premium gold-colored alert class (`detection/mango_native_signals.py`) triggered by dashboard asset badge flips (e.g. `NEUTRAL ➔ LONG`). Signals generate when ≥60% of timeframes align with the new badge trend.
- **Sleep Schedule Quiet Hours (NEW)**: Restricts all Mango dashboard scraping and native signal generation between 11:00 PM and 5:00 AM EST to align with sleep schedules, conserving resources and preventing late-night noise.
- **Database Session State Capture (NEW)**: Added an interactive session capture helper (`interactive_login_mango.py`) with automatic Windows terminal console UTF-8 wrappers. The script securely uploads authenticated cookie/storage states directly to PostgreSQL (`MANGO_DASHBOARD_STATE`) with a local backup (`mango_state.json`) for seamless background running.
- **Automated Trade Radar (NEW)**: Added a new `trade_radar.py` script that evaluates all open positions, identifies "Prime" setups (ideal pullbacks and near-entry opportunities), ranks them by confidence, and sends a top-5 digest to Discord. This runs automatically 4 times a day (8 AM, 12 PM, 4 PM, 8 PM EST) natively integrated into the `run_signals.py` loop.
- **UI Cleanup for Screenshots**: Added aggressive CSS rules in the TradingView scraper to automatically hide pop-ups, promotional banners (like Easter sales), and floating toolbars before taking screenshots. This ensures Discord charts remain perfectly clean and unobstructed.
- **LTF Screenshot Fallback (FIX)**: `4d → 1d` swing signals were missing the lower timeframe chart in Discord because the `1d` timeframe is only scraped at specific times. The system now falls back to the most recent `1d` screenshot stored in the database when the LTF chart isn't part of the current scrape batch — ensuring both charts always appear in Discord alerts.
- **1D Scrape Frequency Increased**: The daily (`1d`) timeframe is now scraped **3 times per day** (at 00:00, 08:00, and 16:00 UTC) instead of twice, so the daily chart data and screenshots stay fresh throughout the trading day.
- **Stale Signal Auto-Cleanup**: Signals that remain `ACTIVE` for more than 5 days are now automatically marked `EXPIRED` on every startup — preventing zombie signals from accumulating in the DB and inflating the open position count shown in the auto-optimizer Discord report. `get_active_signals()` also now enforces a 7-day recency window.
- **Partial TP now shown in Discord**: The `⚡ Partial TP (+1R)` level is now displayed in every signal alert between Take Profit and Stop Loss, including the % distance from entry and the breakeven note.
- **Partial Take Profit at 1R + Breakeven SL (NEW)**: Every signal now stores a `partial_tp` level exactly 1R from entry. When price hits this level the monitor automatically moves the stop-loss to the entry price. If the trade subsequently reverses back to entry it is recorded as `BREAKEVEN` instead of `SL_HIT`, materially reducing loss magnitude. Trades that continue to the full target remain `TP_HIT` as usual.
- **Correlated Positions Cap (NEW)**: A global cap of **2 active crypto positions per direction** is now enforced at signal generation time. If ≥2 crypto SHORTs (or LONGs) are already open, any new signal in that direction is suppressed — preventing the scenario where BTC, ETH, SOL and ARB all fire SHORT simultaneously and a single BTC bounce wipes every position at once.
- **Crypto Scalp SL Floor raised to 1.8%**: The minimum stop-loss distance for crypto scalp trades has been increased from 1.5% to 1.8% to give positions enough breathing room to survive initial wicks on volatile 15m candles.
- **BTC Macro Context Filter (NEW)**: Altcoin signals are now filtered and adjusted based on the live Bitcoin price direction (4H) and Bitcoin Dominance (BTC.D 4H). Implements the full Dominance Cycle: `ALT_DUMP` (BTC.D ↑ + BTC ↓) hard-blocks alt LONGs and boosts alt SHORTs by +7; `ALT_BEARISH` (BTC.D ↑ + BTC ↑) blocks alt LONGs and boosts SHORTs by +3; `ALT_SEASON` (BTC.D ↓ + BTC ↑) blocks alt SHORTs and boosts LONGs by +5. BTC.D is now scraped as a context-only asset (`CRYPTOCAP:BTC.D`) on every run. BTC and all TradFi assets are exempt from the filter.
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