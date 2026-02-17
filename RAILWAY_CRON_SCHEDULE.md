# Railway Cron Schedule - Change to 10 Minutes

## Current Schedule
**15 minutes:** `*/15 * * * *`

## New Schedule (10 Minutes)
**10 minutes:** `*/10 * * * *`

---

## How to Update in Railway

### Step 1: Go to Railway Dashboard
1. Navigate to https://railway.app/dashboard
2. Select your Arcane Portal project
3. Click on the worker/service that runs the scraper

### Step 2: Update Cron Schedule

**Option A: If using Railway Cron Jobs:**
1. Go to the **"Cron"** tab in your service
2. Find the existing cron job (`*/15 * * * *`)
3. Edit it to: `*/10 * * * *`
4. Save changes

**Option B: If using a Custom Start Command:**
If you're using a loop in your start command, you may need to adjust the sleep interval instead.

### Step 3: Verify the Change
1. Check the logs after saving
2. You should see scraper runs every 10 minutes instead of 15
3. Expected runs per hour: **6** (up from 4)

---

## Impact

### Before (15 min intervals):
- **4 runs per hour**
- **96 runs per 24 hours**
- Each run scrapes ~18 assets × 7 timeframes = 126 data points

### After (10 min intervals):
- **6 runs per hour**
- **144 runs per 24 hours** (+50% more data)
- More frequent signal detection
- Better capture of rapid market moves

---

## Alternative: Use Railway CLI

If you prefer command line:

```bash
# Login to Railway
railway login

# Link to your project
railway link

# Update environment variable (if using a variable)
railway variables set CRON_SCHEDULE="*/10 * * * *"

# Or update via railway.json and redeploy
```

---

## Cron Syntax Reference

| Schedule | Cron Expression | Runs Per Hour |
|----------|----------------|---------------|
| Every 5 min | `*/5 * * * *` | 12 |
| Every 10 min | `*/10 * * * *` | 6 |
| Every 15 min | `*/15 * * * *` | 4 |
| Every 30 min | `*/30 * * * *` | 2 |

---

## Note on Operating Hours

Remember: The scraper already skips execution between 11pm - 5am EST (see `utils/time_window.py`).

So even with 10-minute intervals:
- **Active hours:** 5am - 11pm (18 hours)
- **Runs per day:** 18 hours × 6 = **108 runs** (not 144)
- **Sleep hours:** 11pm - 5am (6 hours) → 0 runs

This is still a 50% increase in scraping frequency during active hours.

---

## Railway Credit Usage

**Current (15 min):**
- ~96 runs/day
- Each run takes ~5-6 minutes
- Total runtime: ~480-576 min/day = **8-10 hours/day**

**New (10 min):**
- ~108 runs/day (during active hours)
- Each run takes ~5-6 minutes
- Total runtime: ~540-648 min/day = **9-11 hours/day**

**Increase:** ~10-15% more Railway usage

This is acceptable since you have the sleep mode reducing costs.

---

## Recommendation

**Start with 10-minute intervals** and monitor for 24 hours:
- ✅ More signal opportunities
- ✅ Faster reaction to market moves
- ✅ Still manageable Railway costs
- ⚠️ If too expensive, can revert to 15 min

If you want even MORE aggressive:
- **5-minute intervals:** `*/5 * * * *` (12 runs/hour)
- But this doubles Railway usage - only if budget allows
