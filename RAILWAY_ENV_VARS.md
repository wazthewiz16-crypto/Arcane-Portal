# Railway Environment Variables Guide

## 🔧 **Required Environment Variables**

Add these in Railway Dashboard → Variables:

### **1. Discord Integration**
```
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR_WEBHOOK_ID/YOUR_TOKEN
```

### **2. Browser Settings**
```
HEADLESS_BROWSER=true
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
```

### **3. Signal Confidence Thresholds**
```
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
```

### **4. Playwright Dependencies (Important!)**
```
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
```

---

## 📋 **Complete List for Copy-Paste**

```
DISCORD_WEBHOOK_URL=your_webhook_url_here
HEADLESS_BROWSER=true
PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=0
MIN_CONFIDENCE_SWING=60
MIN_CONFIDENCE_SCALP=75
```

---

## ✅ **How to Add in Railway**

1. Go to Railway dashboard
2. Click on your service
3. Click **"Variables"** tab
4. Click **"+ New Variable"**
5. Add each variable one by one
6. Railway will automatically redeploy after adding variables

---

## 🎯 **What Each Variable Does**

| Variable | Purpose |
|----------|---------|
| `DISCORD_WEBHOOK_URL` | Where to send signal alerts |
| `HEADLESS_BROWSER` | Run browser without GUI |
| `PLAYWRIGHT_BROWSERS_PATH` | Where to store browser binaries |
| `PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD` | Ensure browser is downloaded |
| `MIN_CONFIDENCE_SWING` | Minimum confidence for swing signals |
| `MIN_CONFIDENCE_SCALP` | Minimum confidence for scalp signals |

---

**After adding these, Railway will redeploy and Playwright should work!** 🚀
