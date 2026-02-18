# ⚠️ IMPORTANT: Database Location

When you run `python clean_signals_db.py`, it cleans the database based on your `.env` file:

## Current Setup (based on your .env)

Your `.env` file shows:
```
DATABASE_URL=sqlite:///data/mango_scraper.db
```

This means:
- ✅ **Local scripts** (clean_signals_db.py, analyze_signals.py, run_signals.py) use **SQLite**
- ❓ **Dashboard** may use **PostgreSQL on Railway/Neon**

---

## Why You Still See Signals in Dashboard

If you cleaned the database but still see signals in the Signal History tab, it's because:

1. **Dashboard is reading from PostgreSQL** (Neon database)
2. **Clean script cleaned SQLite** (local file)
3. They are **different databases**!

---

## Solution: Clean the Correct Database

### Option 1: Clean PostgreSQL (Railway/Neon)

**Step 1:** Temporarily update your `.env` to use PostgreSQL:
```bash
# Comment out SQLite
#DATABASE_URL=sqlite:///data/mango_scraper.db

# Add your Neon/Railway connection string
DATABASE_URL=postgresql://user:password@host/database
```

**Step 2:** Run the clean script:
```bash
python clean_signals_db.py
```

**Step 3:** Change `.env` back to SQLite for local development

---

### Option 2: Clean Directly via SQL

**For PostgreSQL (Railway/Neon):**
```bash
# Use Railway CLI or psql
psql postgresql://your-connection-string

# Delete all signals
DELETE FROM signals;

# Verify
SELECT COUNT(*) FROM signals;
```

**For SQLite (Local):**
```bash
sqlite3 data/mango_scraper.db

-- Delete all signals
DELETE FROM signals;

-- Verify
SELECT COUNT(*) FROM signals;

.quit
```

---

### Option 3: Align Databases

Make everything use the same database:

**Use PostgreSQL for Everything:**
1. Update `.env` to use PostgreSQL connection string
2. All scripts will now use the same database
3. Run clean script once

**Use SQLite for Everything:**
1. Ensure `.env` has `DATABASE_URL=sqlite:///data/mango_scraper.db`
2. Make sure dashboard isn't overriding this
3. Run clean script

---

## How to Check Which Database Dashboard Uses

Run the dashboard and check the startup logs:
```bash
python -m streamlit run dashboard/app.py
```

Look for:
```
Using PostgreSQL database  ← Using Neon/Railway
# OR
Using SQLite database: data/mango_scraper.db  ← Using local file
```

---

## Recommended Setup

**For Local Development:**
- Use **SQLite** (simpler, no external dependencies)
- Set in `.env`: `DATABASE_URL=sqlite:///data/mango_scraper.db`

**For Production (Railway):**
- Use **PostgreSQL** (persistent, shared across instances)
- Railway automatically sets `DATABASE_URL` environment variable

---

## Quick Fix

If you just want to clean whatever the dashboard is showing:

**Step 1:** Check which database the dashboard uses
```bash
# Look at dashboard startup logs
python -m streamlit run dashboard/app.py
```

**Step 2:** If it says "PostgreSQL", get the connection string
```bash
# From Railway dashboard > Variables > DATABASE_URL
```

**Step 3:** Clean that database
```bash
# Temporarily set in .env
DATABASE_URL=postgresql://your-neon-connection-string

# Run clean script
python clean_signals_db.py

# Restore .env
DATABASE_URL=sqlite:///data/mango_scraper.db
```

---

## Summary

✅ **You cleaned SQLite successfully** (0 signals confirmed)  
❌ **Dashboard still shows signals** = Reading from PostgreSQL  
🎯 **Solution:** Clean the PostgreSQL database too

The clean script works correctly - you just need to point it at the right database!
