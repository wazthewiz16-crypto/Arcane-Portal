# Dashboard Deployment Guide

## 🖥️ **Deploy Streamlit Dashboard to Railway**

Your dashboard is ready to deploy! Follow these steps to access it via web browser.

---

## 📋 **Step-by-Step Deployment**

### **Step 1: Verify Procfile**

Your `Procfile` should have both services:
```
web: streamlit run dashboard/app.py --server.port=$PORT --server.address=0.0.0.0
worker: python run_signals.py
```

✅ **This is already configured!**

---

### **Step 2: Create a New Service in Railway**

Railway needs two separate services:
1. **worker** - Runs the scraper (already deployed)
2. **web** - Runs the dashboard (new)

**How to add the web service**:

1. Go to your Railway project
2. Click **"+ New"** → **"Service"**
3. Select **"GitHub Repo"**
4. Choose your `arcane-portal-v2` repository
5. Railway will detect it's the same repo

---

### **Step 3: Configure the Web Service**

In the new service settings:

#### **A. Set the Start Command**
- Go to **"Settings"** → **"Deploy"**
- **Custom Start Command**: `streamlit run dashboard/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`

#### **B. Add Environment Variables**
Copy these from your worker service:
```
DISCORD_WEBHOOK_URL=your_webhook_url
HEADLESS_BROWSER=true
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
```

#### **C. Expose Public Port**
- Go to **"Settings"** → **"Networking"**
- Click **"Generate Domain"**
- Railway will create a public URL like: `https://arcane-portal-xxxxx.railway.app`

---

### **Step 4: Deploy**

1. Click **"Deploy"**
2. Wait for build to complete (~2-3 minutes)
3. Once deployed, click the generated URL
4. Your dashboard should load! 🎉

---

## 🎯 **Alternative: Single Service with Multiple Processes**

If you prefer one service instead of two:

### **Option A: Use Railway's Process Management**

1. Keep your current worker service
2. In **"Settings"** → **"Deploy"**
3. Look for **"Processes"** or **"Procfile"**
4. Railway should detect both `web` and `worker` from Procfile
5. Enable both processes

### **Option B: Modify Dockerfile**

Update the `CMD` in Dockerfile to run both:

```dockerfile
# At the end of Dockerfile, replace:
CMD ["python", "run_signals.py"]

# With:
CMD ["sh", "-c", "streamlit run dashboard/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true & python run_signals.py"]
```

**Note**: This runs both in one container, but Railway prefers separate services.

---

## ✅ **Verify Dashboard is Working**

Once deployed, visit your Railway URL and you should see:

### **Dashboard Features**:
1. **Runic Alerts** - Live trading signals
2. **Signal History** - Past signals and performance
3. **Mana Pool** - Prop firm account tracking
4. **Shield** - Position size calculator
5. **Oracle/Sorcerer** - Strategy performance

### **What to Check**:
- ✅ Dashboard loads without errors
- ✅ Signals appear in Runic Alerts
- ✅ History shows past signals
- ✅ Data updates when scraper runs

---

## 🔧 **Troubleshooting**

### **Dashboard won't load**

**Check**:
1. Build logs for errors
2. Deploy logs for Streamlit startup
3. Port is set to `$PORT` (Railway's dynamic port)

**Fix**:
- Ensure `--server.port=$PORT` is in start command
- Check environment variables are set

### **Dashboard loads but no data**

**Cause**: Dashboard and worker use different databases

**Fix**:
1. Both services must share the same database file
2. Use Railway's **Volumes** to share `mango_scraper.db`

**Steps**:
1. Go to worker service → **"Settings"** → **"Volumes"**
2. Create volume: `/app/data`
3. Go to web service → **"Settings"** → **"Volumes"**
4. Mount same volume: `/app/data`
5. Update code to use `/app/data/mango_scraper.db`

### **"Database is locked" error**

**Cause**: Both services trying to write to database simultaneously

**Fix**:
- Worker writes to database
- Dashboard only reads from database
- This is already configured in your code ✅

---

## 📊 **Database Sharing (Important!)**

For the dashboard to show data from the scraper, they need to share the database.

### **Option 1: Railway Volumes (Recommended)**

1. **Create Volume in Worker**:
   - Service: `worker`
   - Mount Path: `/app/data`
   - This stores `mango_scraper.db`

2. **Mount Same Volume in Web**:
   - Service: `web`
   - Mount Path: `/app/data`
   - Reads from same database

3. **Update Database Path**:
   - Change `mango_scraper.db` → `/app/data/mango_scraper.db`
   - In `detection/datastore.py`

### **Option 2: External Database (Advanced)**

Use PostgreSQL or MySQL instead of SQLite:
- Railway provides PostgreSQL
- Requires code changes
- Better for production

---

## 🚀 **Quick Start (Recommended Approach)**

**Easiest way to deploy dashboard**:

1. **In Railway Dashboard**:
   - Go to your project
   - Click **"+ New"** → **"Service"**
   - Select your GitHub repo
   - Name it: `web`

2. **Configure**:
   - Start Command: `streamlit run dashboard/app.py --server.port=$PORT --server.address=0.0.0.0 --server.headless=true`
   - Add environment variables (copy from worker)
   - Generate domain

3. **Deploy**:
   - Click deploy
   - Wait for build
   - Visit generated URL

4. **Share Database** (if needed):
   - Create volume in worker: `/app/data`
   - Mount same volume in web: `/app/data`
   - Update database path in code

---

## 📝 **Post-Deployment**

After dashboard is live:

1. **Bookmark the URL** for easy access
2. **Check data updates** after scraper runs
3. **Monitor performance** over 24-48 hours
4. **Adjust settings** as needed

---

## 🎯 **Expected Result**

You'll have:
- ✅ **Worker service**: Runs scraper every 15 minutes
- ✅ **Web service**: Dashboard accessible via URL
- ✅ **Shared database**: Both services see same data
- ✅ **24/7 access**: View signals anytime, anywhere

---

**Ready to deploy? Follow the steps above!** 🚀

Let me know if you need help with any step!
