"""Scrapes trend badges and flags from the Mango Research premium dashboard"""
import asyncio
import json
import logging
import os
from pathlib import Path
from datetime import datetime
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

STATE_FILE = "mango_state.json"
CACHE_FILE = Path("data/mango_dashboard.json")

class MangoDashboardScraper:
    """Scrapes Mango Research premium dashboard using Playwright session state"""
    
    def __init__(self, state_file=STATE_FILE):
        self.state_file = Path(state_file)
        self.datastore = None
        
        # Try to restore from Postgres DataStore first
        try:
            from detection.datastore import MangoDataStore
            self.datastore = MangoDataStore()
            db_state = self.datastore.get_setting("MANGO_DASHBOARD_STATE")
            if db_state:
                logger.info("Restoring Mango Dashboard session state from Database...")
                with open(self.state_file, "w") as f:
                    f.write(db_state)
        except Exception as e:
            logger.error(f"Failed to check DB for MANGO_DASHBOARD_STATE: {e}")

        # Restore from Env Var if file missing (cloud support)
        if not self.state_file.exists() and os.getenv("MANGO_DASHBOARD_STATE_JSON"):
            try:
                logger.info("Restoring Mango session state from environment variable...")
                with open(self.state_file, "w") as f:
                    f.write(os.getenv("MANGO_DASHBOARD_STATE_JSON"))
            except Exception as e:
                logger.error(f"Failed to restore state from env: {e}")
                
    def is_enabled(self) -> bool:
        """Check if Mango Dashboard confluence is enabled in settings"""
        try:
            # Check DB settings first
            if self.datastore:
                enabled = self.datastore.get_setting("MANGO_CONFLUENCE_ENABLED")
                if enabled is not None:
                    return str(enabled).lower() == 'true'
            # Fallback to .env
            return os.getenv("MANGO_CONFLUENCE_ENABLED", "false").lower() == "true"
        except Exception:
            return False

    async def scrape_dashboard(self) -> bool:
        """Scrape the dashboard page and cache the results"""
        if not self.state_file.exists():
            logger.error(f"Mango session state file {self.state_file} not found. Please run interactive_login_mango.py first.")
            return False
            
        logger.info("Starting Mango Research Dashboard scraper...")
        
        # In-memory storage for intercepted JSON data
        intercepted_data = {}
        
        async with async_playwright() as p:
            # Launch headless browser
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            
            context = await browser.new_context(
                storage_state=str(self.state_file),
                viewport={'width': 1920, 'height': 1080}
            )
            
            page = await context.new_page()
            
            # --- Network Sniffing Handler ---
            async def handle_response(response):
                try:
                    url = response.url.lower()
                    if "mangoresearch" in url and "json" in response.request.resource_type:
                        try:
                            # Load JSON payload
                            payload = await response.json()
                            
                            # Standardize sniffing keys: looking for objects with trend or volatility indications
                            # Often the response will contain lists of coins
                            found_valid = False
                            
                            def scan_for_trends(obj):
                                nonlocal found_valid
                                if isinstance(obj, dict):
                                    # Does this dictionary have keys resembling coin signals?
                                    if 'symbol' in obj or 'ticker' in obj:
                                        symbol = (obj.get('symbol') or obj.get('ticker', '')).upper()
                                        if symbol:
                                            trend = str(obj.get('trend') or obj.get('badge') or obj.get('direction', '')).upper()
                                            # Validate if it's a known trend type
                                            if any(t in trend for t in ['LONG', 'SHORT', 'NEUTRAL', 'BULLISH', 'BEARISH']):
                                                # Standardize ticker name (e.g. BTCUSDT -> BTC)
                                                clean_sym = symbol.replace('USDT', '').replace('.P', '').split(':')[0]
                                                intercepted_data[clean_sym] = {
                                                    'trend': 'LONG' if 'LONG' in trend or 'BULL' in trend else ('SHORT' if 'SHORT' in trend or 'BEAR' in trend else 'NEUTRAL'),
                                                    'volatility': int(obj.get('volatility') or obj.get('vol') or 0),
                                                    'flags': obj.get('flags') or obj.get('indicators') or []
                                                }
                                                found_valid = True
                                    for v in obj.values():
                                        scan_for_trends(v)
                                elif isinstance(obj, list):
                                    for item in obj:
                                        scan_for_trends(item)
                                        
                            scan_for_trends(payload)
                            if found_valid:
                                logger.info(f"Successfully sniffed API response with coin trends from: {response.url}")
                        except Exception:
                            pass
                except Exception as e:
                    logger.debug(f"Error reading response: {e}")
                    
            page.on("response", handle_response)
            
            # Open the dashboard
            url = "https://app.mangoresearch.co/dashboard"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(10)  # Wait for full SPA page render and network requests to complete
            except Exception as e:
                logger.error(f"Failed to load Mango Dashboard page: {e}")
                await browser.close()
                return False
                
            # Take a premium visual backup screenshot
            screenshots_dir = Path("data/screenshots")
            screenshots_dir.mkdir(parents=True, exist_ok=True)
            screenshot_path = screenshots_dir / "mango_dashboard.png"
            try:
                await page.screenshot(path=str(screenshot_path))
                logger.info(f"Visual backup screenshot saved to {screenshot_path}")
            except Exception as e:
                logger.warning(f"Could not take dashboard screenshot: {e}")
                
            # --- Fallback DOM Parser ---
            # If our API sniffing did not find any signals, parse the DOM directly
            dom_data = {}
            if not intercepted_data:
                logger.info("Sniffer found no API trend signals. Falling back to DOM parsing...")
                try:
                    # Capture inner text of the entire document to extract standard coin names and trend words
                    body_text = await page.inner_text("body")
                    
                    # Common asset tickers to look for
                    tickers = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE"]
                    
                    # Search text for lines matching each coin
                    lines = body_text.split('\n')
                    for ticker in tickers:
                        # Find lines containing the ticker
                        for i, line in enumerate(lines):
                            if ticker in line.upper():
                                # Look at this line and subsequent 3 lines for trend keywords
                                context_block = " ".join(lines[max(0, i-1):min(len(lines), i+4)]).upper()
                                
                                trend = 'NEUTRAL'
                                if 'LONG' in context_block or 'BULLISH' in context_block or '🟢' in context_block:
                                    trend = 'LONG'
                                elif 'SHORT' in context_block or 'BEARISH' in context_block or '🔴' in context_block:
                                    trend = 'SHORT'
                                    
                                dom_data[ticker] = {
                                    'trend': trend,
                                    'volatility': 50,  # Default fallback volatility
                                    'flags': []
                                }
                                break
                    logger.info(f"DOM parsing finished. Found {len(dom_data)} tickers.")
                except Exception as e:
                    logger.error(f"Fallback DOM parsing failed: {e}")
            
            # Combine sniffed and DOM data (sniffed has priority)
            final_assets = {**dom_data, **intercepted_data}
            
            if not final_assets:
                logger.error("No coin data could be extracted from Mango Research Dashboard. Session might be expired!")
                await browser.close()
                return False
                
            # Create standardized payload
            result = {
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "assets": final_assets
            }
            
            # Save locally
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Cached {len(final_assets)} dashboard assets locally to {CACHE_FILE}")
            
            # Save to Postgres database for production persistence
            try:
                if self.datastore:
                    self.datastore.set_setting("MANGO_DASHBOARD_CACHED_DATA", json.dumps(result))
                    logger.info("Persisted cached Mango Dashboard data to the database setting MANGO_DASHBOARD_CACHED_DATA.")
            except Exception as e:
                logger.error(f"Failed to persist cached data to DB: {e}")
                
            # Refresh storage state rolling cookies
            try:
                new_state = await context.storage_state()
                if self.datastore:
                    self.datastore.set_setting("MANGO_DASHBOARD_STATE", json.dumps(new_state))
                with open(self.state_file, "w") as f:
                    json.dump(new_state, f)
                logger.info("Mango Dashboard session state successfully refreshed and saved.")
            except Exception as e:
                logger.error(f"Failed to save refreshed state: {e}")
                
            await context.close()
            await browser.close()
            return True

    def get_cached_confluence(self, asset_name: str) -> dict:
        """Get the cached confluence data for a specific asset"""
        asset_name = asset_name.upper()
        
        # Attempt to load from PostgreSQL first
        try:
            if self.datastore:
                db_data = self.datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
                if db_data:
                    data = json.loads(db_data)
                    assets = data.get("assets", {})
                    if asset_name in assets:
                        return assets[asset_name]
        except Exception as e:
            logger.error(f"Failed to retrieve Mango Dashboard cache from DB: {e}")
            
        # Fallback to local file cache
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    assets = data.get("assets", {})
                    if asset_name in assets:
                        return assets[asset_name]
            except Exception as e:
                logger.error(f"Failed to read local cache file: {e}")
                
        return {}
