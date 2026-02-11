# Railway Deployment - Quick Reference

## 🚀 **Quick Start (5 Steps)**

### **1. Pre-Flight Check**
```bash
prepare_deployment.bat
```
This checks if you're ready to deploy.

### **2. Push to GitHub**
```bash
git add .
git commit -m "Ready for Railway deployment"
git push origin main
```

### **3. Deploy to Railway**
1. Go to https://railway.app/new
2. Select "Deploy from GitHub repo"
3. Choose `arcane-portal-v2`
4. Wait for build to complete

### **4. Add Environment Variables**
In Railway dashboard → Variables:
```
DISCORD_WEBHOOK_URL=your_webhook_url_here
HEADLESS_BROWSER=true
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
```

### **5. Set Up Cron**
In Railway dashboard → Cron:
- Schedule: `*/15 * * * *` (every 15 minutes)
- Command: `python run_signals.py`

---

## 📋 **Essential Files**

| File | Purpose | Required |
|------|---------|----------|
| `railway.json` | Railway config | ✅ Yes |
| `Procfile` | Process definitions | ✅ Yes |
| `requirements.txt` | Python dependencies | ✅ Yes |
| `tv_state.json` | TradingView login | ✅ Yes |
| `.env` | Local env vars | ❌ No (use Railway vars) |

---

## 🔧 **Railway Environment Variables**

### **Required**:
```bash
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/...
HEADLESS_BROWSER=true
```

### **Optional** (have defaults):
```bash
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
STREAMLIT_SERVER_PORT=8501
```

---

## ⏰ **Cron Schedules**

| Schedule | Frequency | Use Case |
|----------|-----------|----------|
| `*/5 * * * *` | Every 5 min | Aggressive |
| `*/15 * * * *` | Every 15 min | **Recommended** |
| `*/30 * * * *` | Every 30 min | Conservative |
| `0 * * * *` | Every hour | Light usage |

---

## 🧪 **Testing Commands**

### **Local Test**:
```bash
generate_signals.bat
```

### **Check Railway Logs**:
```bash
railway logs
```
(Requires Railway CLI)

### **Manual Deploy**:
In Railway dashboard → Deployments → Deploy

---

## 📊 **Expected Behavior**

**Every run (15 min)**:
1. Scraper starts (~0s)
2. Scrapes 126 data points (~5-6 min)
3. Detects signals (~10s)
4. Sends Discord alerts (~5s)
5. Updates database (~1s)
6. **Total**: ~6 minutes

**Output**:
- ✅ 18 assets scraped
- ✅ 7 timeframes each
- ✅ 0-10 signals (varies)
- ✅ Discord alerts sent

---

## ⚠️ **Common Issues**

### **"Browser not found"**
**Fix**: Add to Railway vars:
```
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

### **"TradingView login expired"**
**Fix**: 
1. Run locally
2. Login when browser opens
3. Upload new `tv_state.json`

### **"No signals detected"**
**Cause**: Market might be NEUTRAL (choppy)
**Fix**: Normal behavior, wait for clear trends

### **"Discord rate limit"**
**Fix**: Increase confidence thresholds:
```
MIN_CONFIDENCE_SWING=70
MIN_CONFIDENCE_SCALP=80
```

---

## 📖 **Full Documentation**

- **Deployment Guide**: `RAILWAY_DEPLOYMENT.md`
- **Testing Checklist**: `DEPLOYMENT_TESTING.md`
- **Configuration Changes**: `CONFIGURATION_CHANGES.md`
- **Scraper Optimization**: `SCRAPER_OPTIMIZATION.md`

---

## 🎯 **Success Checklist**

After deployment:
- [ ] Build successful
- [ ] Scraper runs on schedule
- [ ] Signals appear in Discord
- [ ] Dashboard accessible
- [ ] No errors in logs
- [ ] Runs complete in ~6 minutes

---

## 💡 **Pro Tips**

1. **Test locally first**: Always run `generate_signals.bat` before deploying
2. **Monitor first 24h**: Check logs frequently initially
3. **Start conservative**: 15-min schedule, then adjust
4. **Keep backups**: Download database periodically
5. **Use Railway CLI**: Faster debugging

---

## 🆘 **Need Help?**

1. Check `RAILWAY_DEPLOYMENT.md` for detailed guide
2. Review `DEPLOYMENT_TESTING.md` for troubleshooting
3. Check Railway logs for errors
4. Visit Railway Discord for support

---

**Ready to deploy?** Run `prepare_deployment.bat` to get started! 🚀
