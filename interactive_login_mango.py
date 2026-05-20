"""Interactive login helper for Mango Research Dashboard"""
import asyncio
import json
import logging
import os
import sys
import io
from playwright.async_api import async_playwright
from dotenv import load_dotenv

# Force UTF-8 encoding for Windows consoles supporting emojis
if sys.platform.startswith('win'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Load Env
load_dotenv(override=True)

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("MangoInteractiveLogin")

async def interactive_login():
    from detection.datastore import MangoDataStore
    
    print("\n" + "="*60)
    print("🥭 MANGO RESEARCH DASHBOARD SESSION REFRESHER")
    print("="*60)
    print("1. A browser window will open shortly.")
    print("2. Please log into your Mango Research account manually.")
    print("3. Navigate to the dashboard page if not redirected automatically.")
    print("4. Return to this console and press ENTER when you are fully logged in.")
    print("="*60 + "\n")
    
    async with async_playwright() as p:
        # Launch non-headless browser for the user to interact with
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(viewport={'width': 1280, 'height': 800})
        page = await context.new_page()
        
        # Go to Mango Research login/dashboard
        await page.goto("https://app.mangoresearch.co/dashboard")
        
        # Wait for user input in console
        input("\n[ACTION REQUIRED] Press ENTER here *AFTER* you have successfully logged into Mango Research and see the main dashboard...")
        
        print("\nSaving secure session state (cookies & storage)...")
        state = await context.storage_state()
        
        # Save to DB for Railway
        try:
            datastore = MangoDataStore()
            datastore.set_setting("MANGO_DASHBOARD_STATE", json.dumps(state))
            print("✅ SUCCESS! New Mango session state saved directly to the database!")
            print("   The scraper will automatically use this session state in production.")
        except Exception as e:
            print(f"❌ ERROR: Could not save to database: {e}")
            print("Make sure your .env file has the correct DATABASE_URL.")
            
        # Also save locally just in case
        with open("mango_state.json", "w") as f:
            json.dump(state, f)
            print("✅ Backup saved to local mango_state.json")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(interactive_login())
