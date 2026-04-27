import asyncio
from playwright.async_api import async_playwright
import json
import logging
import os
from dotenv import load_dotenv

# Load Env
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("InteractiveLogin")

async def interactive_login():
    from detection.datastore import MangoDataStore
    
    print("\n" + "="*60)
    print("🚀 AUTOMATED TRADINGVIEW SESSION REFRESHER")
    print("="*60)
    print("1. A browser window will open shortly.")
    print("2. Please log into TradingView manually (solve any captchas).")
    print("3. Return to this console and press ENTER when you are fully logged in.")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        await page.goto("https://www.tradingview.com/#signin")
        
        # Wait for user to hit enter in console
        input("\n[ACTION REQUIRED] Press ENTER here *AFTER* you have successfully logged into TradingView in the browser...")
        
        print("\nSaving new session cookies...")
        state = await context.storage_state()
        
        # Save to DB
        try:
            datastore = MangoDataStore()
            datastore.set_setting("TV_STATE", json.dumps(state))
            print("✅ SUCCESS! New session saved directly to the Railway Database!")
            print("   The auto-optimizer and scraper will automatically use this new session.")
            print("   (It will also automatically extend itself in the future!)")
        except Exception as e:
            print(f"❌ ERROR: Could not save to database: {e}")
            print("Make sure your .env file has the correct DATABASE_URL.")
            
        # Also save locally just in case
        with open("tv_state.json", "w") as f:
            json.dump(state, f)
            print("✅ Backup saved to local tv_state.json")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(interactive_login())
