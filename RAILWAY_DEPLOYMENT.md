# Railway Deployment Guide - Arcane Portal V2

## 📋 **Prerequisites**

Before deploying, make sure you have:
- ✅ GitHub account
- ✅ Railway account (sign up at railway.app)
- ✅ Discord webhook URL
- ✅ TradingView account with Mango Dynamic indicator

---

## 🚀 **Step 1: Prepare Your Code**

### **1.1 Create Railway Configuration**

We'll create a `railway.json` file that tells Railway how to run your app.

**File**: `railway.json` (already created in your project)

### **1.2 Create Procfile**

This tells Railway what commands to run.

**File**: `Procfile` (already created in your project)

### **1.3 Update requirements.txt**

Make sure all dependencies are listed.

**File**: `requirements.txt` (already exists)

---

## 📦 **Step 2: Push to GitHub**

### **2.1 Initialize Git (if not already done)**

```bash
git init
git add .
git commit -m "Prepare for Railway deployment"
```

### **2.2 Create GitHub Repository**

1. Go to https://github.com/new
2. Create a new repository (e.g., `arcane-portal-v2`)
3. **Don't** initialize with README (we already have code)

### **2.3 Push Your Code**

```bash
git remote add origin https://github.com/YOUR_USERNAME/arcane-portal-v2.git
git branch -M main
git push -u origin main
```

---

## 🚂 **Step 3: Deploy to Railway**

### **3.1 Create New Project**

1. Go to https://railway.app/dashboard
2. Click **"New Project"**
3. Select **"Deploy from GitHub repo"**
4. Authorize Railway to access your GitHub
5. Select your `arcane-portal-v2` repository

### **3.2 Configure Environment Variables**

Railway will automatically detect your project. Now add environment variables:

1. Click on your service
2. Go to **"Variables"** tab
3. Add the following variables:

```bash
# Required Variables
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
HEADLESS_BROWSER=true

# Optional (use defaults if not set)
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
STREAMLIT_SERVER_PORT=8501
```

### **3.3 Add TradingView State**

You need to upload your `tv_state.json` file:

**Option A: Manual Upload**
1. In Railway dashboard, go to **"Settings"**
2. Under **"Volumes"**, create a volume
3. Upload your `tv_state.json` file

**Option B: Include in Git** (Recommended)
1. Make sure `tv_state.json` is in your repository
2. Railway will use it automatically

---

## ⏰ **Step 4: Set Up Cron Schedule**

### **4.1 Add Cron Job**

Railway uses cron syntax for scheduling:

1. In your service settings, go to **"Cron"** tab
2. Add a new cron job:

```
# Run every 15 minutes
*/15 * * * *
```

**Command to run**:
```bash
python run_signals.py
```

### **4.2 Alternative Cron Schedules**

Choose based on your needs:

```bash
# Every 5 minutes (aggressive)
*/5 * * * *

# Every 15 minutes (balanced - recommended)
*/15 * * * *

# Every 30 minutes (conservative)
*/30 * * * *

# Every hour
0 * * * *
```

---

## 🧪 **Step 5: Test Your Deployment**

### **5.1 Manual Test**

1. In Railway dashboard, go to **"Deployments"**
2. Click **"Deploy"** to trigger a deployment
3. Watch the build logs
4. Once deployed, check the logs for:
   - ✅ Scraper starting
   - ✅ Assets being scraped
   - ✅ Signals detected
   - ✅ Discord alerts sent

### **5.2 Check Discord**

1. Go to your Discord channel
2. You should see signal alerts appearing
3. Verify the format looks correct

### **5.3 Check Dashboard**

1. In Railway, find your service URL
2. Add `:8501` to access Streamlit dashboard
3. Example: `https://your-service.railway.app:8501`
4. Verify signals appear in the dashboard

---

## 🔍 **Step 6: Monitor & Debug**

### **6.1 View Logs**

In Railway dashboard:
1. Click on your service
2. Go to **"Logs"** tab
3. Watch for:
   - Scraper output
   - Signal detection
   - Discord notifications
   - Any errors

### **6.2 Common Issues**

**Issue**: Browser fails to start
**Solution**: Make sure `HEADLESS_BROWSER=true` is set

**Issue**: No signals detected
**Solution**: 
- Check confidence thresholds
- Verify TradingView state file exists
- Check scraper logs for errors

**Issue**: Discord alerts not sending
**Solution**:
- Verify webhook URL is correct
- Check Discord channel permissions
- Look for rate limit errors in logs

**Issue**: Timeframe scraping fails
**Solution**:
- Check TradingView login state
- Verify indicator is loaded
- Check for TradingView rate limits

---

## 📊 **Step 7: Verify Everything Works**

### **Checklist**:

- [ ] Code pushed to GitHub
- [ ] Railway project created
- [ ] Environment variables set
- [ ] `tv_state.json` uploaded/included
- [ ] Cron schedule configured
- [ ] First deployment successful
- [ ] Scraper runs without errors
- [ ] Signals detected and saved
- [ ] Discord alerts received
- [ ] Dashboard accessible

---

## 🎯 **Expected Behavior**

**Every 15 minutes** (or your chosen schedule):

1. **Scraper starts**: Logs show "Running TradingView scraper..."
2. **Assets scraped**: All 18 assets × 7 timeframes = 126 data points
3. **Signals detected**: Based on confidence thresholds
4. **Discord alerts**: Sent for each new signal
5. **Database updated**: Signals saved to SQLite
6. **Dashboard updated**: New signals visible

**Time per run**: ~5-6 minutes

---

## 🔧 **Railway Configuration Files**

### **railway.json**
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "python run_signals.py",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 3
  }
}
```

### **Procfile**
```
web: streamlit run dashboard/app.py --server.port=$PORT
worker: python run_signals.py
```

---

## 📈 **Next Steps After Deployment**

Once deployed and working:

1. **Monitor for 24 hours**
   - Check signal quality
   - Verify no errors
   - Confirm Discord alerts working

2. **Optimize if needed**
   - Adjust confidence thresholds
   - Modify cron schedule
   - Fine-tune TP/SL calculations

3. **Add Smart Scheduling** (Phase 2)
   - Implement timeframe-specific schedules
   - Reduce unnecessary scraping
   - Optimize Railway usage

---

## 🆘 **Need Help?**

**Railway Docs**: https://docs.railway.app/
**Discord Support**: Check Railway Discord for help
**Logs**: Always check Railway logs first for errors

---

## 💡 **Pro Tips**

1. **Start with 15-minute schedule**: Test stability before going more frequent
2. **Monitor Railway usage**: Check your plan limits
3. **Keep logs**: Railway keeps logs for debugging
4. **Test locally first**: Run `generate_signals.bat` locally before deploying
5. **Backup database**: Download `mango_scraper.db` periodically

---

## ✅ **Deployment Complete!**

Once you see signals in Discord and the dashboard updates, you're live! 🎉

Your trading signal system is now running 24/7 on Railway, automatically scraping markets and sending alerts.
