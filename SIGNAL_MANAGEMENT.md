# Signal Database Management & Analysis Guide

**Last Updated:** 2026-02-17

---

## Overview

This guide covers three key signal management features:
1. **Cleaning the signals database** (resetting for fresh tracking)
2. **Verifying signals are being stored** (already implemented)
3. **Analyzing signal performance** (24-48 hour review with recommendations)

---

## 1. Clean Signals Database

### Purpose
Reset the signals database to start fresh tracking with the current filter settings.

### When to Use
- After making significant filter changes
- When starting a new trading period
- To remove old/test signals

### How to Run

**Option A: Python Script (Recommended)**
```bash
python clean_signals_db.py
```

**Interactive confirmation required:**
```
Current signals in database: 47

⚠️  WARNING: This will delete ALL 47 signals from the database!
Type 'DELETE' to confirm: DELETE
```

### What Gets Deleted
- ✅ All signals from `signals` table
- ✅ All signal images from `signal_images` table
- ❌ Scrapes are NOT deleted (historical market data preserved)

### Safety Features
- Requires typing "DELETE" to confirm
- Shows count before deletion
- Verifies deletion was successful

---

## 2. Verify Signals Are Being Saved

### Current Status: ✅ **ACTIVE**

Signals are already being saved automatically in `run_signals.py`.

### How It Works

**Signal Storage Flow:**
```python
# 1. Signal is detected
signals = detector.detect_signals_for_asset(asset_name)

# 2. Signal is saved to database
signal_id = datastore.save_signal(signal)

# 3. Screenshot is attached
datastore.save_signal_image(signal_id, screenshot_bytes)

# 4. Discord alert is sent
notifier.send_signal_alert(signal)
datastore.mark_signal_alerted(signal_id)
```

### Verify Signals Are Saving

**Check SQLite Database:**
```bash
sqlite3 data/mango_scraper.db
```

```sql
-- Count total signals
SELECT COUNT(*) FROM signals;

-- View recent signals
SELECT asset_name, signal_type, confidence, status, entry_time 
FROM signals 
ORDER BY created_at DESC 
LIMIT 10;

-- Check by status
SELECT status, COUNT(*) 
FROM signals 
GROUP BY status;
```

**Check PostgreSQL (Railway):**
```bash
# Use Railway CLI or connection string
psql $DATABASE_URL
```
Then run same SQL queries above.

---

## 3. Signal Performance Analysis

### Purpose
Analyze signals from the last 24-48 hours and get **specific, actionable recommendations** for filter adjustments.

### How to Run

**Option A: Default (24 hours)**
```bash
python analyze_signals.py
```

**Option B: Custom Time Period**
```bash
# Last 48 hours
python analyze_signals.py --hours 48

# Last 12 hours
python analyze_signals.py --hours 12
```

**Option C: Export to JSON**
```bash
python analyze_signals.py --hours 24 --export --output report.json
```

**Option D: Windows Batch File**
```bash
analyze_signals.bat
```

---

### Analysis Output

The analyzer provides a comprehensive report:

#### **Overall Metrics**
- Total signal count
- Signals per hour
- Status breakdown (Active, Hit TP, Hit SL, Closed)
- Win rate percentage
- Average confidence
- Confidence range
- Average RR ratio

#### **Performance Breakdowns**
- **By Signal Type:** Swing Long, Swing Short, Scalp Long, Scalp Short
- **By Timeframe:** Performance per LTF (3m, 5m, 15m, 1h, 4h)
- **Top 5 Assets:** Which coins generate most signals

#### **Intelligent Recommendations**

The system analyzes the data and provides **specific, prioritized actions**:

---

### Example Analysis Output

```
================================================================================
SIGNAL PERFORMANCE ANALYSIS - Last 24 Hours
================================================================================

📊 OVERALL METRICS
   Period: 2026-02-16 19:44:48 to now
   Total Signals: 23
   Frequency: 0.96/hour

   Status Breakdown:
      Active: 18
      Hit TP: 3 ✅
      Hit SL: 2 ❌
      Closed: 0

   Performance:
      Win Rate: 60.0% (3W / 2L)
      Avg Confidence: 72.3%
      Confidence Range: 68.2% - 78.9%
      Avg RR Ratio: 2.3:1

📈 BY SIGNAL TYPE:
   Swing Long:
      Count: 12
      Win Rate: 66.7% (2W/1L)
   Scalp Long:
      Count: 8
      Win Rate: 50.0% (1W/1L)
   Swing Short:
      Count: 3
      Win Rate: 0.0% (0W/0L)

⏱️  BY TIMEFRAME:
   15m:
      Count: 8
      Win Rate: 50.0% (1W/1L)
   4h:
      Count: 12
      Win Rate: 66.7% (2W/1L)
   1h:
      Count: 3
      Win Rate: 0.0% (0W/0L)

🏆 TOP 5 ASSETS:
   BTC/USD: 7 signals
   ETH/USD: 5 signals
   SOL/USD: 3 signals
   AVAX/USD: 3 signals
   DOGE/USD: 2 signals

💡 RECOMMENDATIONS (2):

   1. ℹ️ [INFO] Data
      Issue: Only 5 closed trades (need 10+ for reliable win rate)
      Action: Wait for more data before making adjustments
      Target: Monitor for 24-48 more hours

   2. 🟢 [LOW] Quality
      Issue: High win rate: 60.0% (may be too selective)
      Action: Consider lowering confidence by 2-3 points for more signals
      Target: config/settings.py

================================================================================
Analysis generated at: 2026-02-17 19:44:48
================================================================================
```

---

### Recommendation Types

#### **Priority Levels**
- 🔴 **CRITICAL:** Immediate action required (e.g., win rate <25%)
- 🟠 **HIGH:** Important issue (e.g., win rate <35%)
- 🟡 **MEDIUM:** Should address soon (e.g., specific timeframe performing poorly)
- 🟢 **LOW:** Optional improvement (e.g., too selective)
- ℹ️ **INFO:** Informational (e.g., need more data)

#### **Categories**
1. **Frequency:** Signal generation rate
2. **Quality:** Win rate and performance
3. **Confidence:** Distribution and thresholds
4. **Signal Type Performance:** Swing vs Scalp
5. **Timeframe Performance:** Which timeframes work best
6. **Entry Filters:** Candle body, zone position, etc.
7. **Data:** Sample size adequacy

---

### How Recommendations Work

The system analyzes multiple factors:

#### **1. Frequency Analysis**
```python
if signals_per_hour < 0.5:
    "Lower confidence by 2-3 points"
elif signals_per_hour > 3:
    "Increase confidence by 2-3 points"
```

#### **2. Win Rate Analysis**
```python
if win_rate < 25% and closed_trades >= 10:
    "CRITICAL: Increase confidence by 5 points"
elif win_rate < 35%:
    "HIGH: Increase confidence by 3-5 points"
elif win_rate > 60%:
    "LOW: Consider lowering confidence for more signals"
```

#### **3. Signal Type Performance**
```python
for each signal_type:
    if win_rate < 25% and trades >= 5:
        "Disable {signal_type} or increase its confidence"
```

#### **4. Timeframe Performance**
```python
for each timeframe:
    if win_rate < 25% and trades >= 5:
        "Review {timeframe} entry logic or increase confidence"
```

#### **5. Filter Effectiveness**
```python
if low_frequency AND low_win_rate:
    "Filters not working - review candle body size and body ratio"
```

---

### Implementing Recommendations

When you receive a recommendation, follow these steps:

#### **Example: "Lower confidence by 2-3 points"**

**1. Edit `config/settings.py`:**
```python
# Before
MIN_CONFIDENCE_SWING = 68
MIN_CONFIDENCE_SCALP = 78

# After
MIN_CONFIDENCE_SWING = 65  # Lowered by 3
MIN_CONFIDENCE_SCALP = 75  # Lowered by 3
```

**2. Commit and push:**
```bash
git add config/settings.py
git commit -m "Lower confidence thresholds based on analysis"
git push origin main
```

**3. Wait 24 hours and re-analyze**

---

#### **Example: "Review candle body size"**

**1. Edit `detection/signals.py`:**
```python
# Find _check_ltf_entry() function

# Before
if candle_body / price < 0.0025:  # 0.25%

# After (more permissive)
if candle_body / price < 0.002:  # 0.2%
```

---

### Automated Analysis (Optional)

You can schedule the analyzer to run automatically:

**Option A: Windows Task Scheduler**
1. Open Task Scheduler
2. Create Basic Task
3. Trigger: Daily at 8 AM
4. Action: Start Program
5. Program: `python`
6. Arguments: `C:\path\to\analyze_signals.py --hours 24 --export`

**Option B: Add to Cron (Railway)**
If running on Railway, add to your worker schedule:
```bash
# Daily analysis at midnight
0 0 * * * python analyze_signals.py --hours 48 --export
```

---

## Best Practices

### 1. **Clean Database After Major Changes**
```bash
# After implementing new filters
python clean_signals_db.py

# Wait 24-48 hours
# Then analyze fresh data
python analyze_signals.py --hours 24
```

### 2. **Analyze Regularly**
- **Daily:** Quick check during development
- **Weekly:** Review performance trends
- **After adjustments:** Verify improvements

### 3. **Wait for Data**
- Need **minimum 10 closed trades** for reliable win rate
- Wait **24-48 hours** after changes before adjusting again
- Don't over-optimize on small sample sizes

### 4. **Make Small Adjustments**
- Change confidence by **2-3 points max** at a time
- Adjust **one filter at a time**
- Test for 24 hours before next change

### 5. **Track Changes**
Keep a log of adjustments:
```
2026-02-17: Increased confidence to 68/78 (from 65/75)
   Reason: Win rate 45%, wanted higher quality
   Result: TBD (check 2026-02-18)

2026-02-18: Lowered candle body to 0.2% (from 0.25%)
   Reason: Only 0.5 signals/hour, too low
   Result: TBD (check 2026-02-19)
```

---

## Troubleshooting

### "No signals in database"
**Solution:** Run the scraper first
```bash
python run_signals.py
```

### "Only X closed trades"
**Solution:** Wait for more data. Active signals need time to hit TP/SL.

### Analysis shows 0% win rate
**Solution:** Either all signals hit SL (bad filters) or all signals still active (normal).

### Recommendations conflict
**Example:** "Increase frequency" + "Improve quality"
**Solution:** Prioritize quality. Fix win rate first, then adjust frequency.

---

## Quick Reference

### Clean Database
```bash
python clean_signals_db.py
```

### Analyze Performance
```bash
# Last 24 hours
python analyze_signals.py

# Last 48 hours
python analyze_signals.py --hours 48

# Export to JSON
python analyze_signals.py --export
```

### Check Signal Count
```bash
sqlite3 data/mango_scraper.db "SELECT COUNT(*) FROM signals"
```

### View Latest Signals
```bash
sqlite3 data/mango_scraper.db "SELECT * FROM signals ORDER BY created_at DESC LIMIT 5"
```

---

## Files Created

### Python Scripts
- **`clean_signals_db.py`** - Database cleanup utility
- **`analyze_signals.py`** - Performance analyzer

### Batch Files
- **`analyze_signals.bat`** - Easy Windows execution

### This Documentation
- **`SIGNAL_MANAGEMENT.md`** - This file

---

## Next Steps

1. ✅ **Clean the database** if you want fresh tracking
   ```bash
   python clean_signals_db.py
   ```

2. ✅ **Verify signals are saving** (already active)
   - Check Discord for alerts
   - Check dashboard for signals

3. ✅ **Analyze after 24-48 hours**
   ```bash
   python analyze_signals.py --hours 24
   ```

4. ✅ **Implement recommendations** carefully
   - Make small adjustments
   - Test for 24 hours
   - Re-analyze

5. ✅ **Iterate** until you achieve target metrics:
   - Win rate: 35-50%
   - Frequency: 1-2 signals/hour
   - Quality signals only

---

**Remember:** Good trading systems iterate slowly. Make one change, collect data, analyze, adjust. Don't over-optimize!
