# PostgreSQL Setup for Railway

## 🎯 **Quick Setup Guide**

Follow these steps to set up PostgreSQL for your Railway deployment.

---

## 📋 **Step 1: Add PostgreSQL Database**

1. In your Railway project, click **"+ New"**
2. Select **"Database"**
3. Choose **"PostgreSQL"**
4. Railway will create a new PostgreSQL service

---

## 📋 **Step 2: Get Database URL**

1. Click on the **PostgreSQL** service
2. Go to **"Variables"** tab
3. Find and copy the **`DATABASE_URL`** value
   - It looks like: `postgresql://user:password@host:port/database`

---

## 📋 **Step 3: Add DATABASE_URL to Services**

### **Worker Service**:
1. Go to **worker** service
2. Click **"Variables"** tab
3. Click **"+ New Variable"**
4. Add:
   - **Name**: `DATABASE_URL`
   - **Value**: (paste the PostgreSQL URL from step 2)

### **Web Service**:
1. Go to **web** service
2. Click **"Variables"** tab
3. Click **"+ New Variable"**
4. Add:
   - **Name**: `DATABASE_URL`
   - **Value**: (same PostgreSQL URL from step 2)

---

## 📋 **Step 4: Deploy**

1. Push the code changes:
   ```bash
   git add -A
   git commit -m "Add PostgreSQL support for Railway deployment"
   git push origin main
   ```

2. Railway will auto-deploy both services

3. Check deploy logs for:
   ```
   Using PostgreSQL database
   ```

---

## ✅ **Verification**

After deployment:

1. **Check worker logs** - should see "Using PostgreSQL database"
2. **Check web logs** - should see "Using PostgreSQL database"
3. **Wait for next scraper run** (within 15 minutes)
4. **Refresh dashboard** - signals should appear!

---

## 🎯 **How It Works**

### **Automatic Detection**:
- If `DATABASE_URL` environment variable exists → Use PostgreSQL
- If `DATABASE_URL` doesn't exist → Use SQLite (local development)

### **Local Development**:
- No changes needed!
- Still uses SQLite (`data/mango_scraper.db`)
- Works exactly as before

### **Railway Production**:
- Both services connect to same PostgreSQL database
- Shared data between worker and web
- Production-grade database

---

## 🔍 **Troubleshooting**

### **"Using SQLite database" in Railway logs**

**Cause**: `DATABASE_URL` variable not set

**Fix**:
1. Verify `DATABASE_URL` is added to both services
2. Check the value is correct (starts with `postgresql://`)
3. Redeploy services

### **"psycopg2 not found" error**

**Cause**: PostgreSQL library not installed

**Fix**:
- Already added to `requirements.txt`
- Should install automatically
- Check build logs for errors

### **Connection errors**

**Cause**: Invalid DATABASE_URL or network issues

**Fix**:
1. Verify DATABASE_URL is correct
2. Check PostgreSQL service is running
3. Try restarting PostgreSQL service

---

## 📊 **Benefits of PostgreSQL**

✅ **Shared Data**: Both services access same database
✅ **Production-Ready**: Better than SQLite for production
✅ **Concurrent Access**: Multiple services can read/write
✅ **Railway Managed**: Automatic backups and scaling
✅ **No File Sharing**: No need for volumes

---

## 🚀 **You're Done!**

Once `DATABASE_URL` is set in both services:
- Worker will scrape and save to PostgreSQL
- Web will read from PostgreSQL
- Dashboard will show live signals
- Everything synced in real-time!

---

**Follow the steps above and your dashboard will show signals!** 🎉
