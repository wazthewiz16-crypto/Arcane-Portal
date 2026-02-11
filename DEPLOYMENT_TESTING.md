# Railway Deployment Testing Checklist

## 📋 **Pre-Deployment Checklist**

### **Local Testing**
- [ ] Run `generate_signals.bat` locally - confirms scraper works
- [ ] Check Discord - signals should appear
- [ ] Run `start_dashboard.bat` - dashboard should load
- [ ] Verify all 18 assets scrape successfully
- [ ] Confirm 7 timeframes per asset (126 total data points)
- [ ] Check for NEUTRAL trends in output
- [ ] Verify Bybit symbols work correctly

### **Code Preparation**
- [ ] All recent changes committed to git
- [ ] `.env` file NOT committed (sensitive data)
- [ ] `tv_state.json` exists and is valid
- [ ] `requirements.txt` is up to date
- [ ] `railway.json` created
- [ ] `Procfile` created
- [ ] `.railwayignore` created

---

## 🚀 **Deployment Checklist**

### **GitHub Setup**
- [ ] GitHub repository created
- [ ] Code pushed to main branch
- [ ] Repository is accessible

### **Railway Setup**
- [ ] Railway account created
- [ ] New project created from GitHub repo
- [ ] Environment variables added:
  - [ ] `DISCORD_WEBHOOK_URL`
  - [ ] `HEADLESS_BROWSER=true`
  - [ ] `MIN_CONFIDENCE_SWING=60`
  - [ ] `MIN_CONFIDENCE_SCALP=75`
- [ ] `tv_state.json` uploaded or included in repo

### **Cron Configuration**
- [ ] Cron job created
- [ ] Schedule set (recommended: `*/15 * * * *`)
- [ ] Command set: `python run_signals.py`

---

## 🧪 **Post-Deployment Testing**

### **Immediate Tests** (First 30 minutes)

1. **Check Build Logs**
   - [ ] Build completed successfully
   - [ ] No dependency errors
   - [ ] Playwright installed correctly

2. **Check Runtime Logs**
   - [ ] Scraper starts
   - [ ] Browser launches (headless)
   - [ ] TradingView loads
   - [ ] Assets being scraped
   - [ ] No errors in output

3. **Verify Scraping**
   - [ ] All 18 assets scraped
   - [ ] 7 timeframes per asset
   - [ ] NEUTRAL trends detected
   - [ ] Prices look correct

4. **Check Signal Detection**
   - [ ] Signals detected (if market conditions allow)
   - [ ] Confidence thresholds working
   - [ ] TP/SL calculated correctly
   - [ ] Entry times in EST

5. **Verify Discord Alerts**
   - [ ] Alerts sent to Discord
   - [ ] Format looks correct
   - [ ] All signal details included
   - [ ] No rate limit errors

---

## 🔍 **24-Hour Monitoring**

### **First 24 Hours** (Critical)

**Check every 2-4 hours**:

1. **Railway Dashboard**
   - [ ] Service is running
   - [ ] No crashes or restarts
   - [ ] Memory usage stable
   - [ ] CPU usage reasonable

2. **Logs Review**
   - [ ] No repeated errors
   - [ ] Scraper completing successfully
   - [ ] Signals being generated
   - [ ] Discord alerts sending

3. **Discord Channel**
   - [ ] Regular signal updates
   - [ ] No duplicate signals
   - [ ] Signal quality looks good
   - [ ] Timestamps are correct (EST)

4. **Database**
   - [ ] Signals being saved
   - [ ] No duplicate entries
   - [ ] TP/SL tracking working
   - [ ] Status updates (TP_HIT/SL_HIT) working

---

## 🎯 **Success Criteria**

### **Deployment is successful if**:

✅ **Scraper runs every 15 minutes** (or your schedule)
✅ **126 data points scraped** per run (18 assets × 7 timeframes)
✅ **Signals detected** when market conditions allow
✅ **Discord alerts sent** for each new signal
✅ **No duplicate signals** in database
✅ **Dashboard accessible** and updating
✅ **No crashes** or errors in logs
✅ **Completes in ~5-6 minutes** per run

---

## ⚠️ **Common Issues & Solutions**

### **Issue: Browser fails to start**
**Symptoms**: Error about browser not found
**Solution**: 
```bash
# Add to Railway environment variables
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

### **Issue: TradingView login expired**
**Symptoms**: Scraper can't access charts
**Solution**:
1. Run locally: `python scraper/tradingview.py`
2. Login to TradingView when browser opens
3. Upload new `tv_state.json` to Railway

### **Issue: No signals detected**
**Symptoms**: Scraper runs but no signals
**Solution**:
- Check market conditions (might be NEUTRAL trends)
- Verify confidence thresholds aren't too high
- Check logs for detection errors

### **Issue: Discord rate limits**
**Symptoms**: "Rate limited" in logs
**Solution**:
- Increase confidence thresholds (fewer signals)
- Add delay between Discord alerts
- Check for duplicate signals

### **Issue: Slow scraping**
**Symptoms**: Takes >10 minutes per run
**Solution**:
- Check Railway server location
- Verify TradingView isn't rate limiting
- Check for network issues in logs

---

## 📊 **Performance Benchmarks**

### **Expected Performance**:

| Metric | Expected Value |
|--------|---------------|
| Scrape Time | 5-6 minutes |
| Data Points | 126 per run |
| Signals/Run | 0-10 (depends on market) |
| Memory Usage | <512 MB |
| CPU Usage | <50% during scrape |
| Success Rate | >95% |

### **If performance is worse**:
- Check Railway plan limits
- Review logs for bottlenecks
- Consider optimizing scraper further

---

## ✅ **Final Verification**

### **After 24 hours, confirm**:

- [ ] **Stability**: No crashes or errors
- [ ] **Accuracy**: Signals match manual analysis
- [ ] **Reliability**: Runs on schedule consistently
- [ ] **Performance**: Completes in expected time
- [ ] **Quality**: No duplicate or false signals

### **If all checks pass**:
🎉 **Deployment successful!** Your system is live and running 24/7.

### **Next Steps**:
1. Monitor for another 24-48 hours
2. Adjust confidence thresholds if needed
3. Plan Phase 2: Smart Scheduling implementation

---

## 📞 **Support Resources**

- **Railway Docs**: https://docs.railway.app/
- **Railway Discord**: https://discord.gg/railway
- **Playwright Docs**: https://playwright.dev/python/
- **Streamlit Docs**: https://docs.streamlit.io/

---

## 💡 **Pro Tips**

1. **Keep a local backup**: Run locally occasionally to verify
2. **Monitor Railway costs**: Check usage dashboard
3. **Save logs**: Download logs for analysis
4. **Test changes locally**: Before deploying updates
5. **Use Railway CLI**: For faster debugging

---

**Good luck with your deployment!** 🚀
