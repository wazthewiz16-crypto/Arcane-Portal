# Arcane Portal V2

**Mango Dynamic Trading Signal System** - Real-time signal detection with Discord alerts, Streamlit dashboard, ML-powered market regime detection, and automated self-optimization.

![Arcane Portal Dashboard](https://i.imgur.com/placehold.png)

- 📈 **System Expectancy Optimization Suite**: Engineered to maximize average win size ($R_{\text{win}} \ge 2.5R - 3.0R$) and positive expectancy:
  - **Favorable Zone Entry Positioning:** Requires price to be in the favorable lower 45% (Discount) for LONG entries and upper 45% (Premium) for SHORT entries, guaranteeing tight risk and strong upside room.
  - **Dynamic Target Expansion (+3.0R):** Setups confirmed by Mutanabby AI or TK Cross indicators automatically expand TP2 targets to **+3.0R** (standard +2.2R), driving average win size significantly higher than average losses.
  - **Tiered TPs & Breakeven+ Locking:** Partial TP1 at +1.2R secures 30% profit and locks Stop Loss to **Breakeven+ (+0.1R)**, making the trade 100% risk-free.
  - **Time-Based Dead-Trade Invalidation:** Automatically closes stagnant trades open > 36 hours (swings) or > 12 hours (scalps) without hitting TP1 as `TIME_EXPIRED` to cut chop losses early.
  - **Asset Expectancy Priority Boost:** Grants +5% confidence boost to Tier 1 Major Assets (`BTC`, `ETH`, `SOL`, `NDX`, `SPX`, `US30`).
- 🧠 **Multi-Horizon Self-Improvement Engine (7, 14, 30, 60 Days)**: Continuously evaluates trade performance across rolling 7d, 14d, 30d, and 60d lookback windows:
  - **Adaptive Signal-Type Gating & Auto-Halt:** Automatically halts underperforming signal types (e.g. 0% win rate over 7d) or applies +5%/+10% confidence penalties. Access is automatically restored when 7d win rate recovers to $\ge 50\%$.
  - **Discord Self-Improvement Reports:** Automatically posts multi-horizon performance breakdown matrices and gating summaries directly to Discord.
- 🔄 **Stage 0 Trend Reversal Exits & Contrarian Blockers**:
  - **Reversal Exits:** Instantly closes active open positions with `REVERSAL_EXIT` when 1D or 4H timeframes turn contrary (e.g. closing open shorts when 1D/4H flip green or emit Mutanabby BUY signals).
  - **Mutanabby AI Contrarian Blockers:** Strictly blocks short entries when lower timeframes show Mutanabby BUY labels / green ribbons, and vice versa for long entries.
- 🔮 **Indicator Confluence Suite (Mutanabby AI & Mango Ribbon TK Crosses)**:
  - Scrapes active values for `Buy`, `Sell`, `Strong Buy`, `Strong Sell` (Mutanabby AI) and `TK Bull Cross` / `TK Bear Cross` (Mango Ribbon) directly from TradingView Data Window legends.
  - Applies dynamic confidence boosts (+15% HTF Strong signals, +10% LTF TK Crosses) and counter-signal penalties.
- ⏳ **Expanded Timeframe Coverage (1W, 12H, 1H)**:
  - **Weekly (1W) Scraper Support:** Daily 00:00 UTC weekly candle scraping mapped to layout overrides (`TRADINGVIEW_LAYOUT_1W`).
  - **Intermediate Swings:** `1w->1d`, `4d->1d`, `1w->4h`, `4d->4h`, `1d->4h`, `1d->1h`, `12h->1h`.
  - **Hourly Scalps (`4h->1h`, `12h->1h`):** Evaluates short-term entries on 1H charts to bypass 15m market noise.
- 🌙 **Overnight TradFi Compute Optimization**: Automatically bypasses traditional market indices (`NDX`, `SPX`, `US30`, `DXY`, etc.) overnight (6:00 PM to 8:00 AM EST) when TradFi markets are closed, saving Railway compute for 24/7 crypto scans.

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
DISCORD_BOT_TOKEN=YOUR_DISCORD_BOT_TOKEN

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

# Terminal 3: Run the Discord Command Bot
python run_bot.py
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
- **Fail-safe Heartbeat & Change Detection (NEW):** Instead of exiting silently when no signals are found in the 24-hour analysis window, the script runs fallback calculations (such as a 14-day optimization backtest, regime detection, drawdown circuit breaker, and correlation cap), updates database settings, and posts a daily summary status to Discord (throttled to once every 23 hours if parameters don't change, or immediately if any parameter is adjusted).
*It updates parameters directly in the database and sends reports to Discord.*

**Recommended Schedule:** Run 3x daily (e.g. 3am, 9:30am, 5pm EST) via Railway Cron or external scheduler to capture post-session resolutions.

### Trade Radar (`trade_radar.py`)
A secondary digest system designed for part-time monitoring. Evaluates all active signals and filters for "Prime" setups (trades currently in a slight pullback or resting exactly at entry, avoiding trades that are too close to stop-loss or already heavily in profit). It ranks them by a blend of confidence and pullback depth. It automatically pushes a summary of the top 5 trades to Discord at **8 AM, 12 PM, 4 PM, and 8 PM EST** (natively integrated into `run_signals.py`).

**Upgrades V3:**
- 📊 **Visual Chart Attachments:** Automatically pulls the latest saved chart screenshot from the database (`screenshots` table) for the #1 ranked prime trade setup and attaches it directly to the Discord alert digest (falling back cleanly to text-only if missing).
- 📐 **Dynamic R-Multiple & "Enhanced R:R" Tracker:** Swaps raw percentage distance (e.g., `-1.24%`) for R-multiple distance (e.g., `-0.4R` pullback) and calculates the mathematically improved Risk-to-Reward ratio (e.g., `Original R:R: 2.0:1 ➔ Enhanced: 2.4:1`) resulting from entering on a pullback.

### Continuous Monitoring (`monitor_signals.py`)
The primary execution script.
- Watches the database for new signals.
- Interfaces with `discord_notifier.py` to post high-quality PNG charts.
- Validates the active state to pause execution natively on Windows/Linux environments.

### Discord Command Bot (`run_bot.py`)
A standalone bot client that listens to message channels for control commands:
- `!radar`: Triggers the trade radar on-demand to scan for pullback entry opportunities.
- `!conditions`: Pulls active regime, circuit breaker state, altcoin correlation caps, and Mango dashboard metrics in a clean status card.
- `!optimizer`: Forces an immediate Auto-Optimizer run to tune confidence filters.
- `!brief` / `!afternoon` / `!evening`: Dispatches daily regime briefings and summaries.
- `!help`: Lists all available commands.

It runs continuously on Railway. If `DISCORD_BOT_TOKEN` is not configured, it logs a warning and exits cleanly without crashing.

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

**Latest Update:** 2026-08-11

- **Autonomous Strategy Researcher & Evolutionary Self-Correction Engine (NEW)**:
  - 🔬 **Autonomous Background Researcher (`strategy_researcher.py`):** Runs continuous combinatorial grid-search backtests across 30-day In-Sample training windows and 14-day Out-of-Sample forward-test validation windows.
  - ⚙️ **Self-Correcting Database Tuning:** Automatically adjusts live database settings (`MIN_CONFIDENCE_SWING`, `MIN_CONFIDENCE_SCALP`, `FAVORABLE_ZONE_PCT`, `OPTIMAL_TARGET_RR`) to the configuration that yields the highest positive expectancy.
  - 🌊 **Unchoked Signal Flow:** Relaxed zone entry constraints to 65% and added a 36-hour Signal Drought Safety Valve to ensure high-quality signals fire smoothly without starving signal cadence.
  - 🤖 **Discord Command Bot Integration:** Added `!research` / `!strategy` bot command to trigger walk-forward strategy optimization on-demand.

**Previous Update:** 2026-08-09

- **System Expectancy Optimization Suite & Multi-Horizon Self-Improvement Engine (NEW)**:
  - 📈 **Expectancy & Win Size Optimization:** Overhauled signal criteria to ensure Average Win Size ($R_{\text{win}} \ge 2.5R - 3.0R$) significantly exceeds average losses:
    - **Favorable Zone Entry Positioning:** Requires entries to be in the favorable lower 45% (Discount) for LONGs and upper 45% (Premium) for SHORTs, guaranteeing tight risk and maximum upside room.
    - **Dynamic Target Expansion (+3.0R):** Indicator confluence setups automatically expand TP2 targets to **+3.0R**.
    - **Tiered TPs & Breakeven+ Locking:** Partial TP1 at +1.2R secures 30% profit and locks Stop Loss to **Breakeven+ (+0.1R)**.
    - **Time-Based Dead-Trade Invalidation:** Automatically closes stagnant trades open > 36 hours (swings) or > 12 hours (scalps) without hitting TP1 as `TIME_EXPIRED`.
    - **Asset Expectancy Priority Boost:** Grants +5% confidence boost to Tier 1 Major Assets (`BTC`, `ETH`, `SOL`, `NDX`, `SPX`, `US30`).
  - 🧠 **Multi-Horizon Self-Improvement Engine (7, 14, 30, 60 Days):** Evaluates closed trade performance across rolling 7d, 14d, 30d, and 60d lookback windows. Features adaptive signal-type gating, auto-halt rules (on 0% 7d win rates), and automated Discord reports.
  - 🔄 **Stage 0 Trend Reversal Exits & Contrarian Blockers:** Instantly closes active positions with `REVERSAL_EXIT` when 1D/4H flip green or emit Mutanabby BUY labels, preventing trapped counter-trend shorting.
  - 🔮 **Indicator Confluence Suite:** Integrated `Mutanabby_AI` (`Buy`, `Sell`, `Strong Buy`, `Strong Sell`) and `Mango Ribbon` (`TK Bull Cross`, `TK Bear Cross`) legend parsing with dynamic confidence scoring.
  - ⏳ **Expanded Timeframes (1W, 12H, 1H):** Added 1W weekly candle scraping, intermediate swing combinations (`1w->1d`, `1d->1h`, `12h->1h`), and 1H scalp entries to eliminate 15m noise.
  - 🌙 **Overnight TradFi Compute Optimization:** Bypasses closed TradFi index assets overnight (6:00 PM to 8:00 AM EST) to save Railway compute for 24/7 crypto scans.

**Previous Update:** 2026-07-08

- **End of Day Summary & Interactive Discord Command Bot (NEW)**:
  - 🌙 **EOD Summary & Outlook (9:00 PM EST):** Extended the daily regime check framework to run an Evening EOD Check. Features full-day watchlist returns (6 AM - 9 PM EST), session top gainers/losers, daily signal execution stats (win rate, total trades, realized PnL in R-multipliers), and a bulleted list of today's executed trades with status emojis (🟢 TP_HIT, 🔴 SL_HIT, 🟡 BREAKEVEN, ⚡ ACTIVE).
  - 🤖 **Discord Command Bot:** Created a standalone Discord bot client (`run_bot.py`) that runs 24/7 on Railway (`Procfile`). Listens for prefix commands:
    - `!radar`: Triggers the Arcane Trade Radar and posts active trade metrics (distance-to-SL, R-multiple drift) to Discord.
    - `!conditions`: Displays real-time regime decisions, circuit breaker state, altcoin correlation caps, and cached Mango metrics in a premium Discord embed.
    - `!optimizer`: Triggers the auto-optimizer manually to adjust confidence thresholds.
    - `!brief` / `!afternoon` / `!evening`: Triggers daily briefs on-demand.
    - `!help`: Shows the custom bot command manual.
  - 🔌 **Fail-Safe Design:** If `DISCORD_BOT_TOKEN` is not configured, the bot logs a clear warning and exits gracefully with code `0`, allowing Railway builds to deploy seamlessly without blockages.

**Previous Update:** 2026-06-09

- **Morning Trading Brief & Signal Frequency Optimizations (NEW)**:
  - 🧠 **Discord Morning Brief:** Transformed the 6:00 AM EST daily regime check into a comprehensive Morning Trading Brief. Displays overnight gainers and losers (comparing yesterday's 11:00 PM EST price scrapes to today's 6:00 AM EST scrapes), watchlist sentiment bias counts (LONG/SHORT/NEUTRAL badges parsed from the Mango Dashboard cache), BTC Dominance Cycle status, and altcoin correlation caps in a beautifully styled, color-coded Discord embed.
  - 🚦 **Regime Halt Confidence Tuning:** Raised the `RANGING_NO_TRADE` confidence threshold from `70.0%` to `85.0%` in both morning and afternoon checks. This prevents halting all signals on moderately ranging days (confidence < 85%), transitioning instead to `RANGING_SCALPS_ONLY` where scalp trading remains active.
  - ⚡ **Loosened Scalp Macro Alignment:** Loosened the daily trend Grandmaster Filter for scalps in `detection/signals.py` to allow `NEUTRAL` Daily trend states. This allows scalp signals to fire during consolidation ranges where the daily trend is neutral, increasing signal frequency.
  - ⚙️ **Auto-Optimizer Floor & Safety Valve Tweak:** Lowered confidence floor limits to `55` for swing and `60` for scalp trades, and reduced safety valve throttle duration from 23 hours to 12 hours in `auto_optimizer.py` to allow faster adaptive stepping down when signals dry up.
  - 🔍 **Afternoon Verification Upgrade:** Upgraded the 1:00 PM EST Afternoon Verification check in `detection/daily_regime.py` to incorporate:
    - **Dynamic Volatility Thresholds:** Computes rolling average daily ranges over the past 7 days from database scrapes to scale trending (0.8x) and ranging (0.4x) thresholds adaptively.
    - **Morning Session Mover Tracking:** Tracks directional net session returns (6:00 AM to 1:00 PM EST) and highlights the top session gainers and losers.
    - **Active Signals Feedback Loop & Capital Safeguard:** Evaluates morning trade outcomes; if trades are bleeding (e.g. $\ge 3$ stop-outs or realized PnL $\le -2.0R$), it triggers an automatic downgrade to `RANGING_SCALPS_ONLY` to restrict further swing risk.

**Previous Update:** 2026-06-05

- **Mango-Enriched Weekly ML Retraining & Live Regime Detection (NEW)**:
  - **Historical Tracking (`mango_scrapes`):** Introduced a historical database logging table `mango_scrapes` (PostgreSQL and SQLite) to save the hourly crawlers' cached dashboard data, bypassing the single-key cache overwrites.
  - **Upgraded Feature Vectors:** Added 4 macro dashboard features (`mango_market_trend`, `mango_market_volatility`, `mango_badge_trend_ratio`, and `mango_avg_asset_volatility`) to the rolling training feature pool, expanding classification vectors from 4 to 8 variables.
  - **Robust Fallback Strategy:** Handled missing historical dates prior to deployment by defaulting the dashboard features to neutral values, preserving the training dataset integrity.
  - **Dynamic Inference Compatibility:** Configured the live regime detector to detect the expected feature shape of the loaded ML model (`model.n_features_in_`), ensuring perfect backward-compatibility with 4-feature legacy models while supporting 8-feature models.
  - **Worker Crash Fix:** Fixed a critical weekly retrainer execution bug inside `run_signals.py` by adding the missing `signals_df` parameter to prevent TypeError crashes during automatic Saturday runs.

- **Auto-Optimizer Frequency Safety Valve Override Fix (NEW)**:
  - **Overriding Baseline:** Refactored threshold determination in `auto_optimizer.py` to calculate threshold values using local variables (`proposed_swing` / `proposed_scalp`) before applying regime adjustments, low frequency blocker limits, and the global safety valve.
  - **Low Frequency Clamping:** Implemented a check that prevents the 14-day backtester baseline from increasing/overwriting the safety valve's step-downs when signal frequency is critically low (`freq < 0.3`). This guarantees the safety valve successfully decreases thresholds (by -3) and keeps them lowered to restart trade frequency during dry phases.

**Previous Update:** 2026-06-04

- **Dynamic Crypto Correlation Cap Auto-Loosening (NEW)**:
  - **Auto-Loosening Logic:** Added a mechanism to `auto_optimizer.py` that checks the 24-hour signal frequency (`signals_per_hour`). If it drops below `0.3` signals per hour (indicating critically low activity / a dry spell), the cryptocurrency correlation cap (`MAX_CRYPTO_SAME_DIRECTION`) is automatically loosened by `+1` (capped at a maximum of `3` positions).
  - **Bypassing Redundant DB Writes:** Centralized database updates to the main change-detection loop, removing a premature database write that was bypassing Discord alert notifications. Now, all parameter updates—including correlation cap adjustments—correctly dispatch immediate alerts to Discord.

**Previous Update:** 2026-06-03

- **Auto-Optimizer Fallback Heartbeat & Subtask Error Alerts (NEW)**:
  - **No-Signal Heartbeat:** Modified `auto_optimizer.py` to prevent silent exits when there are no recent signals in the 24-hour analysis window. It now executes all optimizations, runs a 14-day backtest, detects regimes/circuit breakers, saves settings, and posts a daily status summary to Discord (rate-limited to once every 23 hours if nothing changes, or posted immediately upon setting adjustments).
  - **Discord Error Alerts for Subtasks:** Wrapped all critical background tasks inside `run_signals.py` (status updating, Trade Radar execution, and ML retraining) with try-except blocks that send detailed exception warnings directly to Discord on failure.

**Previous Update:** 2026-06-02

- **Gold-Backed Crypto Replacement (PAXGUSDT) (NEW)**:
  - **Asset Swap:** Replaced `GOLD` (OANDA:XAUUSD, type `tradfi`) with `PAXG` (BINANCE:PAXGUSDT, type `crypto`) in `config/assets.py` to maintain a strict limit of 24 active watchlist assets while optimizing for cryptocurrency trading.
  - **24/7 Scraping & Signals:** Since PAXG is classified as `"type": "crypto"`, it is scraped and monitored 24/7 (including weekends), unlike the old TradFi `GOLD` asset which was disabled on weekends.
  - **High-Performance Target Alignment:** Mapped `'PAXG'` in `detection/signals.py` to the high-performing commodity target profile (`2.2:1` swing R:R, `1.75:1` scalp R:R) to preserve the exact technical target math of gold.
  - **Premium Dashboard Confluence Mapping:** Mapped `'PAXG'` to `'GLD'` (Gold ETF) in the Mango Dashboard sniffer `SYMBOL_MAP` in `scraper/mango_dashboard.py` so that it seamlessly inherits identical premium trend, volatility, and technical flag indicators from the dashboard.

- **Trade Radar Scheduler Optimization & Dynamic Retry (NEW)**:
  - **Dynamic Retries:** Upgraded the scheduler in `run_signals.py` to only set the database lock key `LAST_RADAR_RUN_KEY` when the Trade Radar *actually* successfully posts a message to Discord. This prevents the "first-run-lock" issue where an early cron run with no active signals would lock out subsequent runs in the same hour when a signal pulls back into the prime zone.
  - **Active Trade Status Fallback:** Upgraded `trade_radar.py` to fall back to an **"Active Trade Status Update"** containing active trade PnLs, R-multiple drift, and auto-attached screenshots when no active setups meet the narrow prime entry filter (`[-2.0%, +1.5%]`). This guarantees the user always receives the scheduled Discord posts at 7 AM, 1 PM, 6 PM, and 10 PM.
  - **Terminology Update:** Renamed the status label `"Early Profit"` to `"Running Profit"` for clearer terminology.

- **Mid-Cap Altcoin Swing Risk-Reward Tweak (NEW)**:
  - Tuned the asset-specific risk-reward profiles (`ASSET_RR_PROFILES`) in `detection/signals.py` to increase the `swing_rr` targets for all mid-cap altcoins (including **XRP**, **ADA**, **DOGE**, **LINK**, **AVAX**, **ARB**, **HYPE**, **TRX**, **INJ**, **ONDO**, and **NEAR**) from **`1.5` to `1.8`**, bringing swing targets closer to the 2:1 sweet spot while keeping scalps at `1.5` to secure quick wins in fast mean-reverting conditions.

- **Mango Dashboard Flags & Timeframe Merging (NEW)**:
  - Fixed raw sniffer API indicator parsing (mapping `golden_cross`, `ichimoku`, `rsi_divergence`, `premium_discount` direct fields) and implemented cross-timeframe merging across `1D`, `4H`, `12H`, and `1H` in detectors.

**Previous Update:** 2026-05-24

- **Upgraded ML Retraining Pipeline & Dynamic Setup Tiering (NEW)**:
  - **Dynamic Setup Tiering:** Signals are classified into distinct quality tiers: **Tier A+ (Ultra Setup)**, **Tier A (High Conviction)**, and **Tier B (Standard Setup)**. Dynamic border color mapping (Vibrant Gold for Tier A+) and prominent embed banners dynamically isolate "cream of the crop" setups to prevent overtrading.
  - **Outcome-Based Labeling:** Shifted retraining labels from heuristic formulas to actual trade outcomes. Links historical training windows directly to realized TP/SL resolutions with expert heuristic fallbacks.
  - **Recency-Weighted Training:** Applies exponential decay weights with a **30-day half-life** to focus learning on the current active market regimes.
  - **Walk-Forward Chronological Parameter Tuning:** Added chronological time-series splits and walk-forward parameter grid searches over 27 parameters, resolving overfitting and lookahead bias.
  - **Database Persistence & Migrations:** Upgraded PostgreSQL and SQLite datastores to dynamically migrate signal schemas and persistently store signal tiers.
  - **Enriched Retrain Notification:** Displays walk-forward validation accuracy, parameter selections, and label source counts in Discord retrain alerts.

- **Configurable Macro Trend Filters & LTF Alignment (NEW)**:
  - **Weekly Swing Mismatch Bypass (`ALLOW_SWING_WEEKLY_MISMATCH`):** Swing trades can execute when the Daily trend aligns with the 4H entry, even if the Weekly (4D) trend is opposite (default: `True`), unblocking trend reversals off support.
  - **Scalp Daily/Weekly Mismatch Bypass (`ALLOW_SCALP_DAILY_MISMATCH` & `ALLOW_SCALP_WEEKLY_MISMATCH`):** Intraday scalp signals ignore slow-moving Daily and Weekly trend directions (default: `True`).
  - **LTF Ribbon alignment loosening (`STRICT_SCALP_LTF_ALIGNMENT`):** Scalps can trigger when the 15m ribbon is in a temporary pullback transition/neutral state, relying on the 15m entry zone boundaries (default: `False`) instead of requiring perfect alignment during a deep pullback wick.

- **Mango Premium Volatility Rules, Timeframe Upgrades, and New Assets**:
  - **Refined Volatility Rules**: Implemented unified volatility gates. Low volatility (`< 30` - Blue) is safe and encouraged, bypassing all compression blocks and receiving a **`+10%` confidence boost** (capped at `100%`). High volatility indicates extreme trend exhaustion and **blocks trades completely** if the overall volatility or any high timeframe (`4H`, `12H`, `1D`) volatility is `>= MANGO_VOLATILITY_THRESHOLD` (configurable database setting, currently adjusted to `85`).
  - **Base Timeframe Upgrade**: Shifted the default base timeframe for all Mango Dashboard calculations and native signals from `"4H"` to `"1D"` to capture macro structural trends more reliably.
  - **Scraping Coverage Expansion**: Added 4 highly requested crypto assets to both TradingView and Mango Research Dashboard scraping pipelines: `TRXUSDT`, `INJUSDT`, `ONDOUSDT`, and `NEARUSDT`.
  - **Enriched Discord Embeds & Technical Flags**: Enhanced standard TV and Mango-native alerts to display the active timeframe (`📊 Timeframe: 1D`) and format guide-matching technical flags with color-coded bullet points (🟢 green for bullish/confirming flags like `Golden Cross` or `Cheap / Discount`, 🔴 red for contrarian/bearish flags like `Death Cross` or `Expensive / Premium`).

- **Strategy Backtester & Parameter Optimization (Option C Integration)**:
  - **Core Backtest Engine ([backtest_engine.py](file:///c:/Users/wasif/Documents/Arcane%20Portal/backtester/backtest_engine.py))**: Implemented historical trade simulation logic, dynamic column mappings with priority strings, and wick-based stop-loss/take-profit hit tracking.
  - **Grid-Search Optimizer ([parameter_optimizer.py](file:///c:/Users/wasif/Documents/Arcane%20Portal/backtester/parameter_optimizer.py))**: Exhaustive parameter sweep optimization testing multiple configuration ranges of stop-loss buffers, baseline/aggressive reward ratios, and dynamic zone filters.
  - **Saved Backtests Persistence & Comparisons**: Leveraged PostgreSQL/SQLite database schemas to securely save backtest results, manage runs, and compare multiple configurations side-by-side.
  - **Streamlit UI Integration**: Integrated the `"🧪 Backtest Optimizer"` tab in the main Streamlit dashboard.

- **Mango Research Scraper & Dynamic Volatility Resolution (NEW)**:
  - **Sequential Tab Scraping**: Refactored the Playwright scraper into sequential, fully-isolated Crypto and TradFi scraping phases with 8-second tab-switching delays to prevent memory leaks and timeouts on Railway.
  - **Watchlist Filtering Optimization**: Restricted detail-page crawling strictly to core traded assets (`CORE_SCRAPE_ASSETS`) to prevent browser lockups and massive page-goto overhead.
  - **Integer Trend Correction**: Decoded API trends (`0` = NEUTRAL, `1` = LONG, `2` = SHORT) in both global and detail sniffer responses to resolve the issue where crypto/TradFi assets were shown as "UNLISTED".
  - **Bollinger Band Width Percentile (`bbwp`) Volatility**: Switched sniffers to parse `"bbwp"` first to fetch real, high-fidelity volatility values instead of default/neutral `50` values.
- **Swing Trade Volatility Exhaustion Filter (NEW)**:
  - Added a dual-tier volatility gate for Swing trades evaluating both overall asset and timeframe-specific (4H, 12H, 1D) volatilities:
    - **Extreme Volatility (> 90)**: Blocks Swing trade entry completely to avoid entering exhausted trends.
    - **High Volatility (85 to 90)**: Deducts 20.0% from signal confidence and appends a warning badge (`⚠️ High Volatility (Exhaustion Risk)`).
- **Mango Research Premium Dashboard Integration**: Natively scrapes `app.mangoresearch.co` in the background (with 1-hour rate-limiting to capture badge flips twice as fast) using Playwright with robust network sniffing and DOM-parsing fallbacks.
- **Global Market Trend Opposite Blocking**: Blocks standard TradingView signals from firing if they fight the overall global market trend (e.g., blocking LONG signals when the market is in a global SHORT regime).
- **Scalp Volatility Filters**: Enforces individual asset volatility gates for scalp signals, filtering out trades in extreme exhaustion zones (`>85`) or dormant compression zones (`<25`).
- **Custom MTF Button Preset Verification**: Validates signals against custom **Mango Bullish** (4H, 12H, 1D Golden Cross + 2D, 4D LONG) and **Mango Bearish** (4H, 12H, 1D Death Cross + 2D, 4D SHORT) dashboard presets. Standard TradingView Discord embeds now print these preset alignment statuses under a premium "Mango Premium Confluence" panel.
- **Mango-Native Signal Detection (NEW)**: Created a separate, premium gold-colored alert class (`detection/mango_native_signals.py`) triggered by dashboard asset badge flips (e.g. `NEUTRAL ➔ LONG`). Signals generate when ≥60% of timeframes align with the new badge trend.
- **Sleep Schedule Quiet Hours (NEW)**: Restricts all Mango dashboard scraping and native signal generation between 11:00 PM and 5:00 AM EST to align with sleep schedules, conserving resources and preventing late-night noise.
- **Database Session State Capture (NEW)**: Added an interactive session capture helper (`interactive_login_mango.py`) with automatic Windows terminal console UTF-8 wrappers. The script securely uploads authenticated cookie/storage states directly to PostgreSQL (`MANGO_DASHBOARD_STATE`) with a local backup (`mango_state.json`) for seamless background running.
- **Upgraded Arcane Trade Radar (Prime Entries)**: Upgraded `trade_radar.py` with premium visual and quantitative features. Swapped raw percentage distance (e.g. `-1.24%`) for precise **R-Multiple Drift** (e.g. `-0.4R` pullback). Introduced the **Enhanced R:R Tracker**, which mathematically calculates and displays the improved Risk-to-Reward ratio (e.g. `Original R:R: 2.0:1 ➔ Enhanced: 2.4:1`) gained from entering on a pullback. Added **Visual Chart Attachments** that automatically extract the latest saved chart screenshot from the database (`screenshots` table) for the #1 ranked setup and attach it directly to the Discord alert digest (falling back cleanly to text-only if unavailable).
- **UI Cleanup for Screenshots**: Added aggressive CSS rules in the TradingView scraper to automatically hide pop-ups, promotional banners (like Easter sales), and floating toolbars before taking screenshots. This ensures Discord charts remain perfectly clean and unobstructed.
- **LTF Screenshot Fallback (FIX)**: `4d → 1d` swing signals were missing the lower timeframe chart in Discord because the `1d` timeframe is only scraped at specific times. The system now falls back to the most recent `1d` screenshot stored in the database when the LTF chart isn't part of the current scrape batch — ensuring both charts always appear in Discord alerts.
- **1D Scrape Frequency Increased**: The daily (`1d`) timeframe is now scraped **3 times per day** (at 00:00, 08:00, and 16:00 UTC) instead of twice, so the daily chart data and screenshots stay fresh throughout the trading day.
- **Stale Signal Auto-Cleanup (Timezone-Safe)**: Signals that remain `ACTIVE` for more than 5 days (and scalp trades older than 12 hours) are now automatically marked `EXPIRED` on startup using timezone-safe UTC `created_at` timestamps instead of local entry times. This prevents zombie signals from accumulating in the DB and inflating the open position count shown in the auto-optimizer report. `get_active_signals()` also now enforces a 7-day recency window.
- **Partial TP now shown in Discord**: The `⚡ Partial TP (+1R)` level is now displayed in every signal alert between Take Profit and Stop Loss, including the % distance from entry and the breakeven note.
- **Partial Take Profit at 1R + Breakeven SL (NEW)**: Every signal now stores a `partial_tp` level exactly 1R from entry. When price hits this level the monitor automatically moves the stop-loss to the entry price. If the trade subsequently reverses back to entry it is recorded as `BREAKEVEN` instead of `SL_HIT`, materially reducing loss magnitude. Trades that continue to the full target remain `TP_HIT` as usual.
- **Correlated Positions Cap (NEW)**: A global cap of **2 active crypto positions per direction** is now enforced at signal generation time. If ≥2 crypto SHORTs (or LONGs) are already open, any new signal in that direction is suppressed — preventing the scenario where BTC, ETH, SOL and ARB all fire SHORT simultaneously and a single BTC bounce wipes every position at once.
- **Refined Scalp SL Parameters**: The minimum stop-loss distance for crypto scalp trades has been increased from 1.8% to 2.2% (and tradfi to 1.8%) to give positions enough breathing room to survive initial wicks on volatile 15m candles. Scalp stop-loss buffer has also been widened to 1.2% (baseline) and 1.6% (chop protection).
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
- **Advanced Auto-Optimizer (Phase 2 Upgrades)**: Fully implemented the **Drawdown Circuit Breaker** (automatically halts Tier A/B trading for 24 hours if 24h PnL falls below $-3.0R$, allowing only Tier A+ setups to pass), **Dynamic Altcoin Correlation Cap** (adjusts active position limits between 1, 2, and 3 based on live BTC BBWP volatility to expand during alt season decoupling and protect during market-wide correlation flushes), and **Self-Healing Parameter Backtester** (regularly backtests the past 14 days of closed trade data to mathematically find and apply optimal Swing/Scalp confidence thresholds that maximize net R-multiples).
- **Railway Cost Optimization**: ~45% reduction in hourly browser load via smart scheduling.

**Built with:** Python • Streamlit • Playwright • PostgreSQL • Discord • Numpy/Pandas