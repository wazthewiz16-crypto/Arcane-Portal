"""
Test live Mango Dashboard detail page scraping for BTC
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

from detection.datastore import MangoDataStore
from scraper.mango_dashboard import MangoDashboardScraper

def safe_print(text):
    try:
        encoded = str(text).encode(sys.stdout.encoding or 'utf-8', errors='replace')
        print(encoded.decode(sys.stdout.encoding or 'utf-8'))
    except Exception:
        print("[Print Error: Unprintable characters]")

async def main():
    scraper = MangoDashboardScraper()
    if not scraper.is_enabled():
        safe_print("Mango Dashboard Confluence is not enabled in settings.")
        return
        
    safe_print("Launching Playwright...")
    from playwright.async_api import async_playwright
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # Load state
        state_file = Path("mango_state.json")
        if not state_file.exists():
            db_state = scraper.datastore.get_setting("MANGO_DASHBOARD_STATE")
            if db_state:
                state_file.write_text(db_state)
                safe_print("Restored session state from DB.")
            else:
                safe_print("No session state found. Please login first.")
                await browser.close()
                return
                
        context = await browser.new_context(storage_state=str(state_file))
        page = await context.new_page()
        
        # Set up sniffer
        detail_intercepted = {}
        async def handle_tf_response(response):
            url = response.url.lower()
            if "mangoresearch" in url:
                try:
                    payload = await response.json()
                    
                    def scan_tf(obj):
                        if isinstance(obj, dict):
                            tf_key = (obj.get('timeframe') or obj.get('tf') or obj.get('interval'))
                            trend  = (obj.get('trend') or obj.get('badge') or obj.get('direction'))
                            if tf_key and trend is not None:
                                tf_label = str(tf_key).upper()
                                clean_flags = scraper.standardize_flags(obj.get('flags') or obj.get('indicators') or [])
                                detail_intercepted[tf_label] = {
                                    'trend': trend,
                                    'flags': clean_flags
                                }
                            for v in obj.values():
                                scan_tf(v)
                        elif isinstance(obj, list):
                            for item in obj:
                                scan_tf(item)
                    scan_tf(payload)
                except Exception:
                    pass
                    
        page.on("response", handle_tf_response)
        
        safe_print("Navigating to BTC detail page...")
        try:
            await page.goto("https://app.mangoresearch.co/dashboard/btc", wait_until="domcontentloaded", timeout=60000)
            safe_print("Sleeping 7 seconds for SPA rendering...")
            await asyncio.sleep(7)
            
            safe_print("\n--- SNIFFED INTERCEPTED DATA ---")
            safe_print(json.dumps(detail_intercepted, indent=2))
            
            safe_print("\n--- DOM CONTENT ANALYSIS ---")
            body_text = await page.inner_text("body")
            safe_print(f"Total DOM text length: {len(body_text)} characters")
            
            # Let's run our DOM parsing logic on this live text and print results!
            trends = {}
            flags = {}
            tf_labels = ["15M", "1H", "2H", "4H", "8H", "12H", "1D", "2D", "3D", "4D", "1W"]
            lines = body_text.split('\n')
            safe_print("\n--- Running DOM Fallback Parser ---")
            for i, line in enumerate(lines):
                line_up = line.upper().strip()
                for label in tf_labels:
                    if label == line_up or (label in line_up and len(line_up) < 20):
                        block = " ".join(lines[i:i+8]).upper()
                        safe_print(f"\nMatched Timeframe label: '{label}' (Line {i}: '{line_up}')")
                        
                        trend_val = 'NEUTRAL'
                        if 'LONG' in block or 'BULLISH' in block:
                            trend_val = 'LONG'
                        elif 'SHORT' in block or 'BEARISH' in block:
                            trend_val = 'SHORT'
                        elif 'NEUTRAL' in block:
                            trend_val = 'NEUTRAL'
                            
                        trends[label] = trend_val
                        
                        # Parse flags
                        tf_flags = []
                        if 'GOLDEN CROSS' in block or 'GOLD_CROSS' in block:
                            tf_flags.append('Golden Cross')
                        if 'DEATH CROSS' in block or 'DEATH_CROSS' in block:
                            tf_flags.append('Death Cross')
                        if 'BULLISH ICHIMOKU' in block or 'ICHIMOKU BULLISH' in block:
                            tf_flags.append('Bullish Ichimoku')
                        if 'BEARISH ICHIMOKU' in block or 'ICHIMOKU BEARISH' in block:
                            tf_flags.append('Bearish Ichimoku')
                        if 'RSI BULLISH DIVERGENCE' in block or 'RSI_BULL_DIV' in block:
                            tf_flags.append('RSI Bullish Divergence')
                        if 'RSI BEARISH DIVERGENCE' in block or 'RSI_BEAR_DIV' in block:
                            tf_flags.append('RSI Bearish Divergence')
                        if 'CHEAP' in block or 'DISCOUNT' in block:
                            tf_flags.append('Cheap / Discount')
                        if 'EXPENSIVE' in block or 'PREMIUM' in block:
                            tf_flags.append('Expensive / Premium')
                        if 'HOTLIST' in block or 'MANGO HOTLIST' in block:
                            tf_flags.append('Mango Hotlist')
                            
                        flags[label] = tf_flags
                        safe_print(f"Parsed Trend: {trend_val} | Parsed Flags: {tf_flags}")
                        break
                        
            safe_print("\n--- DOM PARSER FINAL RESULTS ---")
            safe_print("Trends: " + json.dumps(trends, indent=2))
            safe_print("Flags: " + json.dumps(flags, indent=2))
            
        except Exception as e:
            safe_print(f"Error during page navigation: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
