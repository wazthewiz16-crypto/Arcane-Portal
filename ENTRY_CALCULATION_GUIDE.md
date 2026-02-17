# Signal Entry, Stop Loss & Take Profit Calculation Guide

**Last Updated:** 2026-02-17  
**Version:** Phase 1 (Relaxed Filters)

---

## Table of Contents
1. [Overview](#overview)
2. [Mango Dynamic Indicator Components](#mango-dynamic-indicator-components)
3. [Entry Signal Detection](#entry-signal-detection)
4. [Entry Filters & Validation](#entry-filters--validation)
5. [Stop Loss Calculation](#stop-loss-calculation)
6. [Take Profit Calculation](#take-profit-calculation)
7. [Signal Confidence Scoring](#signal-confidence-scoring)
8. [Examples](#examples)

---

## Overview

The Arcane Portal trading system generates signals based on the **Mango Dynamic Indicator** combined with multi-timeframe trend analysis. Signals are categorized into two types:

- **Swing Trades:** Higher timeframe (4H-4D) signals, held for days/weeks
- **Scalp Trades:** Lower timeframe (3m-15m) signals, held for hours

---

## Mango Dynamic Indicator Components

### What the Scraper Captures from TradingView

For each asset and timeframe, we scrape the following from the Mango Dynamic indicator:

| Field | Description | Example |
|-------|-------------|---------|
| `close` | Current price (close of latest candle) | $42,350 |
| `open` | Open price of latest candle | $42,280 |
| `high` | High of latest candle | $42,450 |
| `low` | Low of latest candle | $42,200 |
| `entry_up` | Top of Mango Dynamic entry zone (resistance) | $42,400 |
| `entry_down` | Bottom of Mango Dynamic entry zone (support) | $42,100 |
| `mango_d1` | Mango Dynamic Line 1 (faster moving average) | $42,250 |
| `mango_d2` | Mango Dynamic Line 2 (slower moving average) | $42,150 |
| `trend` | Scraped trend text ("Bullish", "Bearish", "Neutral") | "Bullish" |

### What These Mean

- **Entry Zone (`entry_down` to `entry_up`):** The optimal entry range for trades
  - For **Longs:** Bottom of zone = support level
  - For **Shorts:** Top of zone = resistance level
  
- **Mango D1/D2:** Dynamic moving averages that define trend strength
  - Price > D1 > D2 = Strong Bullish
  - Price < D1 < D2 = Strong Bearish
  
- **Trend:** The overall trend direction based on Mango indicator calculations

---

## Entry Signal Detection

### Signal Types & Timeframe Pairings

The system checks these specific timeframe combinations:

#### **Swing Trades:**
| HTF (Trend) | LTF (Entry) | Hold Duration |
|-------------|-------------|---------------|
| 4D | 1D | Weeks |
| 1D | 4H | Days-Week |
| 12H | 1H | 1-3 Days |

#### **Scalp Trades:**
| HTF (Trend) | LTF (Entry) | Hold Duration |
|-------------|-------------|---------------|
| 4H | 15m | Hours |
| 1H | 5m | 30min-2hr |
| 30m | 3m | 15-45min |

### Entry Logic Flow

```python
For each timeframe pairing (HTF -> LTF):
    1. Check HTF trend direction (LONG/SHORT/NEUTRAL)
    2. If HTF trend is valid (not NEUTRAL):
        3. Check LTF for entry signal
        4. If entry valid, apply filters
        5. Calculate TP/SL levels
        6. Calculate confidence score
        7. If confidence >= threshold, generate signal
```

---

## Entry Filters & Validation

### Filter 1: Chop Detection
**Purpose:** Avoid trading in sideways/consolidating markets

```python
zone_width = abs(entry_up - entry_down)
zone_width_pct = zone_width / price

if zone_width_pct < 0.003:  # 0.3% minimum
    REJECT - "Chop/Squeeze detected"
```

**Example:**
- Price: $40,000
- Entry Up: $40,100
- Entry Down: $39,900
- Zone Width: $200 / $40,000 = **0.5%** ✓ (Pass - zone is wide enough)

---

### Filter 2: Candle Body Size
**Purpose:** Ensure candle shows conviction (not a doji or tiny candle)

```python
candle_body = abs(close - open)
candle_range = high - low
body_ratio = candle_body / candle_range

# Check 1: Body must be at least 40% of total range
if body_ratio < 0.4:
    REJECT - "Doji/indecision candle"

# Check 2: Body must be at least 0.3% of price
if candle_body / price < 0.003:
    REJECT - "Candle too small"
```

**Example (PASS):**
- Price: $40,000
- Open: $39,900
- Close: $40,100 (bullish)
- High: $40,150
- Low: $39,850
- Body: $200
- Range: $300
- Body Ratio: $200/$300 = **66.7%** ✓
- Body %: $200/$40,000 = **0.5%** ✓

**Example (FAIL - Doji):**
- Body: $50
- Range: $300
- Body Ratio: $50/$300 = **16.7%** ✗ (< 40%)

---

### Filter 3: Candle Color Check
**Purpose:** Ensure momentum aligns with trade direction

```python
is_bullish = close > open
is_bearish = close < open

if direction == 'LONG' and not is_bullish:
    REJECT - "Wrong candle color for long"
    
if direction == 'SHORT' and not is_bearish:
    REJECT - "Wrong candle color for short"
```

---

### Filter 4: Optimal Entry Zone Position
**Purpose:** Enter near support (longs) or resistance (shorts), not in the middle

**Current Setting:** Bottom/Top **80%** of zone is valid

```python
zone_size = entry_up - entry_down

# For LONG trades
optimal_entry_top = entry_down + (zone_size * 0.8)
if price > optimal_entry_top:
    REJECT - "Price too high in zone (want bottom 80%)"

# For SHORT trades
optimal_entry_bottom = entry_up - (zone_size * 0.8)
if price < optimal_entry_bottom:
    REJECT - "Price too low in zone (want top 80%)"
```

**Visual Example (LONG):**
```
entry_up = $40,200      ←─┐
                          │  Top 20% (REJECTED)
$40,160 ←─────────────────┤  ← optimal_entry_top (80% mark)
                          │
                          │  Bottom 80% (VALID for longs)
                          │
entry_down = $40,000    ←─┘

If price = $40,050 → Inside bottom 80% ✓
If price = $40,180 → In top 20% ✗
```

---

### Filter 5: Grandmaster Filter (Scalps Only)
**Purpose:** Ensure scalp direction aligns with Daily trend

```python
# For scalp trades, check Daily trend
daily_trend = get_trend('1d')
htf_trend = get_trend(htf_timeframe)  # e.g., 4H

if daily_trend != htf_trend:
    REJECT - "Scalp doesn't align with Daily trend"
```

**Example:**
- Daily: Bullish
- 4H: Bullish ✓
- Signal: 15m Long ✓ (Pass)

**Example (FAIL):**
- Daily: Bearish
- 4H: Bullish ✗
- Signal: 15m Long ✗ (Rejected)

---

### Filter 6: Swing Trend Alignment
**Purpose:** Don't trade against LTF trend

```python
# For swing trades, ensure LTF doesn't contradict HTF
ltf_trend = get_trend(ltf_timeframe)
htf_trend = get_trend(htf_timeframe)

if htf_trend == 'LONG' and ltf_trend == 'SHORT':
    REJECT - "LTF contradicts HTF (don't long during bearish pullback)"
```

---

## Stop Loss Calculation

### Method: Mango Dynamic Boundaries (Option B)

**Rationale:** The Mango Dynamic zone (`entry_down` to `entry_up`) represents natural support and resistance levels. Using these boundaries as stops aligns with the indicator's logic and provides **wider, more intelligent stops** than fixed percentages.

### Formula

```python
# Small buffer beyond the zone boundary
buffer = 0.005  # 0.5%

# For LONG trades
stop_loss = entry_down * (1 - buffer)
# SL is placed below the support zone

# For SHORT trades
stop_loss = entry_up * (1 + buffer)
# SL is placed above the resistance zone
```

### Why This Works

- **Respects Market Structure:** The zone already defines S/R levels
- **Dynamic Sizing:** Stops widen when volatility increases (wider zones)
- **Prevents Noise:** Gives enough room to survive normal market fluctuations
- **2-5x Wider:** Compared to the old 0.5% fixed buffer method

---

### Example Calculation (LONG)

**Scenario:**
- Asset: Bitcoin
- Timeframe: 15m (scalp)
- Direction: LONG
- Entry Price: $42,150
- Entry Zone Low (`entry_down`): $42,000
- Entry Zone High (`entry_up`): $42,300

**Stop Loss Calculation:**
```python
buffer = 0.005  # 0.5%
stop_loss = entry_down * (1 - buffer)
stop_loss = 42,000 * (1 - 0.005)
stop_loss = 42,000 * 0.995
stop_loss = $41,790
```

**Risk:**
```python
risk = entry_price - stop_loss
risk = 42,150 - 41,790
risk = $360 (0.85% risk)
```

---

### Example Calculation (SHORT)

**Scenario:**
- Asset: Ethereum
- Timeframe: 4H (swing)
- Direction: SHORT
- Entry Price: $2,280
- Entry Zone Low: $2,250
- Entry Zone High: $2,300

**Stop Loss Calculation:**
```python
buffer = 0.005
stop_loss = entry_up * (1 + buffer)
stop_loss = 2,300 * (1 + 0.005)
stop_loss = 2,300 * 1.005
stop_loss = $2,311.50
```

**Risk:**
```python
risk = stop_loss - entry_price
risk = 2,311.50 - 2,280
risk = $31.50 (1.38% risk)
```

---

## Take Profit Calculation

### Timeframe-Based Risk/Reward Ratios

The TP is calculated based on the **risk** (distance from entry to SL) multiplied by a **timeframe-specific RR ratio**.

### RR Ratios by Timeframe

#### **Scalp Trades:**
| Timeframe | RR Ratio | Rationale |
|-----------|----------|-----------|
| 3m, 5m | **1.5R** | Very short-term, quick exits |
| 15m | **2.0R** | Standard scalp target |

#### **Swing Trades:**
| Timeframe | RR Ratio | Rationale |
|-----------|----------|-----------|
| 4H, 12H | **2.5R** | Mid-range swing trades |
| 1D, 4D | **3.0R** | Longer-term position trades |

### Formula

```python
# Calculate risk
risk = abs(entry_price - stop_loss)

# Determine RR ratio based on timeframe
if is_scalp:
    if timeframe in ['3m', '5m']:
        rr_ratio = 1.5
    else:  # 15m
        rr_ratio = 2.0
else:  # swing
    if timeframe in ['4h', '12h']:
        rr_ratio = 2.5
    else:  # 1d, 4d
        rr_ratio = 3.0

# Calculate Take Profit
if direction == 'LONG':
    take_profit = entry_price + (risk * rr_ratio)
else:  # SHORT
    take_profit = entry_price - (risk * rr_ratio)
```

---

### Example TP Calculation (LONG - 15m Scalp)

**From previous example:**
- Entry: $42,150
- SL: $41,790
- Risk: $360
- RR Ratio: **2.0** (15m scalp)

**Take Profit:**
```python
take_profit = entry_price + (risk * rr_ratio)
take_profit = 42,150 + (360 * 2.0)
take_profit = 42,150 + 720
take_profit = $42,870
```

**Expected Profit:** $720 (1.71% gain)  
**Risk/Reward:** $360 risk for $720 reward = **2:1**

---

### Example TP Calculation (SHORT - 1D Swing)

**Scenario:**
- Entry: $2,280
- SL: $2,311.50
- Risk: $31.50
- RR Ratio: **3.0** (1D swing)

**Take Profit:**
```python
take_profit = entry_price - (risk * rr_ratio)
take_profit = 2,280 - (31.50 * 3.0)
take_profit = 2,280 - 94.50
take_profit = $2,185.50
```

**Expected Profit:** $94.50 (4.14% gain)  
**Risk/Reward:** $31.50 risk for $94.50 reward = **3:1**

---

## Signal Confidence Scoring

### Base Confidence: 40%
Every signal starts with 40% confidence.

### Confidence Bonuses

| Criteria | Bonus | Max Contribution |
|----------|-------|------------------|
| **Trend Strength** | Price distance from Mango D2 | +20% |
| **Entry Quality** | Proximity to ideal entry point | +15% |
| **Mango D1/D2 Alignment** | Both lines aligned with trend | +10% |
| **Swing Trade Bonus** | Longer timeframe = more reliable | +5% |
| **Perfect Bounce** | Clean bounce off zone | +10% |

### Calculation Example

**Scenario:** BTC 15m Long Scalp
```python
base = 40%

# Trend strength: Price is 2% above Mango D2
trend_bonus = min((0.02 * 100), 20) = 20%

# Entry quality: Price is 90% close to ideal entry
entry_bonus = 0.9 * 15 = 13.5%

# Mango alignment: Price > D1 > D2 (all aligned)
alignment_bonus = 10%

# Not a swing trade
swing_bonus = 0%

# Clean bounce pattern detected
bounce_bonus = 10%

TOTAL = 40 + 20 + 13.5 + 10 + 0 + 10 = 93.5%
Capped at 100% = 93.5% confidence
```

### Confidence Thresholds

- **Swing Trades:** Minimum **65%** confidence required
- **Scalp Trades:** Minimum **75%** confidence required

If a signal doesn't meet these thresholds, it's **rejected** even if entry conditions are valid.

---

## Complete Examples

### Example 1: Bitcoin 15m Long Scalp

**Market Data (LTF = 15m):**
```
close = $42,150
open = $42,080
high = $42,200
low = $42,050
entry_up = $42,300
entry_down = $42,000
mango_d1 = $42,100
mango_d2 = $41,950
```

**Market Data (HTF = 4H):**
```
trend = "Bullish"
mango_d1 > mango_d2 (aligned)
```

**Market Data (Daily):**
```
trend = "Bullish" (Grandmaster check)
```

---

**Step 1: HTF Trend Check**
```
HTF (4H) trend = "Bullish" → Direction = LONG ✓
```

**Step 2: Entry Filters**

**Filter 1 - Chop Detection:**
```
zone_width = 42,300 - 42,000 = $300
zone_pct = 300 / 42,150 = 0.71% > 0.3% ✓
```

**Filter 2 - Candle Body Size:**
```
body = |42,150 - 42,080| = $70
range = 42,200 - 42,050 = $150
body_ratio = 70/150 = 46.7% > 40% ✓
body_pct = 70/42,150 = 0.17% < 0.3% ✗ REJECT
```

**⚠️ SIGNAL REJECTED:** Candle too small (0.17% < 0.3% minimum)

---

### Example 2: Ethereum 4H Long Swing (PASS)

**Market Data (LTF = 4H):**
```
close = $2,290
open = $2,270
high = $2,295
low = $2,265
entry_up = $2,310
entry_down = $2,250
mango_d1 = $2,280
mango_d2 = $2,260
```

**Market Data (HTF = 1D):**
```
trend = "Bullish"
```

---

**Step 1: HTF Trend**
```
HTF (1D) = Bullish → LONG ✓
```

**Step 2: Entry Filters**

**Chop Detection:**
```
zone_width = 2,310 - 2,250 = $60
zone_pct = 60/2,290 = 2.62% > 0.3% ✓
```

**Candle Body:**
```
body = |2,290 - 2,270| = $20
range = 2,295 - 2,265 = $30
body_ratio = 20/30 = 66.7% > 40% ✓
body_pct = 20/2,290 = 0.87% > 0.3% ✓
```

**Candle Color:**
```
close (2,290) > open (2,270) → Bullish ✓
```

**Entry Zone (80% rule):**
```
zone_size = 60
optimal_top = 2,250 + (60 * 0.8) = $2,298
price (2,290) < 2,298 ✓ (in bottom 80%)
```

**Swing Trend Alignment:**
```
LTF (4H) trend = Bullish
HTF (1D) trend = Bullish
Same direction ✓
```

**✅ ALL FILTERS PASSED**

---

**Step 3: Calculate TP/SL**

**Stop Loss:**
```
buffer = 0.005
SL = entry_down * (1 - buffer)
SL = 2,250 * 0.995 = $2,238.75
```

**Risk:**
```
risk = 2,290 - 2,238.75 = $51.25 (2.24%)
```

**Take Profit:**
```
RR ratio = 2.5 (4H swing)
TP = 2,290 + (51.25 * 2.5)
TP = 2,290 + 128.125 = $2,418.13
```

---

**Step 4: Confidence Score**

```
base = 40%
trend_strength = 15% (moderate)
entry_quality = 12% (good position)
alignment = 10% (D1>D2)
swing_bonus = 5%
bounce = 0%

TOTAL = 82% > 65% threshold ✓
```

---

**Final Signal:**
```json
{
    "asset": "ETH/USD",
    "type": "Swing Long",
    "htf": "1d",
    "ltf": "4h",
    "entry": 2290.00,
    "stop_loss": 2238.75,
    "take_profit": 2418.13,
    "risk_pct": 2.24,
    "reward_pct": 5.59,
    "rr_ratio": 2.5,
    "confidence": 82
}
```

---

## Summary

### Key Takeaways

1. **Entry = Multi-Timeframe Analysis**
   - HTF determines trend direction
   - LTF provides entry timing
   - Filters ensure quality

2. **Stop Loss = Mango Dynamic Boundaries**
   - Uses `entry_down` (longs) or `entry_up` (shorts)
   - Plus 0.5% buffer
   - **2-5x wider** than fixed percentages
   - Respects natural support/resistance

3. **Take Profit = Timeframe-Adaptive RR**
   - Scalps: 1.5-2R (quick exits)
   - Swings: 2.5-3R (ride the trend)
   - Based on actual risk (SL distance)

4. **Confidence = Quality Filter**
   - Multiple factors contribute
   - Min 65% (swings) or 75% (scalps)
   - Higher confidence = better setups

---

### Current Filter Settings (As of 2026-02-17)

| Filter | Setting |
|--------|---------|
| Chop Detection | 0.3% min zone width |
| Candle Body Size | 0.3% of price |
| Body Ratio | 40% of range |
| Entry Zone | Bottom/Top 80% |
| Confidence | 65% (swing), 75% (scalp) |
| Stop Method | Mango boundaries + 0.5% |
| RR Ratios | 1.5-3R (timeframe dependent) |

---

**Document Version:** 1.0  
**Last Updated:** February 17, 2026  
**Code Location:** `detection/signals.py`
