"""
Capture and dump the raw API response from Mango Dashboard detail page
"""
import sys
import os
import json
import asyncio
from pathlib import Path

from dotenv import load_dotenv
load_dotenv(override=True)

# Add project root working directory to path
sys.path.insert(0, os.getcwd())

from scraper.mango_dashboard import MangoDashboardScraper

async def main():
    scraper = MangoDashboardScraper()
    
    print("Launching Playwright...")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Load state
        state_file = Path("mango_state.json")
        if not state_file.exists():
            db_state = scraper.datastore.get_setting("MANGO_DASHBOARD_STATE")
            if db_state:
                state_file.write_text(db_state)
            else:
                print("No state found.")
                await browser.close()
                return
                
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()
        
        payloads = []
        async def handle_tf_response(response):
            url = response.url.lower()
            if "mangoresearch" in url:
                try:
                    payload = await response.json()
                    payloads.append({
                        "url": response.url,
                        "data": payload
                    })
                except Exception:
                    pass
                    
        page.on("response", handle_tf_response)
        
        print("Navigating to detail page...")
        try:
            await page.goto("https://app.mangoresearch.co/dashboard/btc", wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8)
            
            output_file = Path("scratch/raw_payload.txt")
            output_file.parent.mkdir(parents=True, exist_ok=True)
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(payloads, f, indent=2)
            print(f"Successfully captured {len(payloads)} responses and wrote to {output_file}")
            
        except Exception as e:
            print(f"Error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
