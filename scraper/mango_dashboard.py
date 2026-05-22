"""Scrapes trend badges and flags from the Mango Research premium dashboard"""
import asyncio
import json
import logging
import os
import re
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

    def standardize_flags(self, raw_flags) -> list:
        """Standardize raw scraped flags/indicators into official Mango premium flag names from the guide."""
        if not raw_flags:
            return []
        if isinstance(raw_flags, str):
            raw_flags = [raw_flags]
            
        mapped = []
        for f in raw_flags:
            if not f:
                continue
            f_up = str(f).upper().strip()
            
            # Standardize using the guide names:
            if "GOLDEN" in f_up or "GOLD_CROSS" in f_up:
                mapped.append("Golden Cross")
            elif "DEATH" in f_up or "DEATH_CROSS" in f_up:
                mapped.append("Death Cross")
            elif "BULLISH ICHIMOKU" in f_up or "ICHIMOKU_BULL" in f_up or ("ICHIMOKU" in f_up and "BULL" in f_up):
                mapped.append("Bullish Ichimoku")
            elif "BEARISH ICHIMOKU" in f_up or "ICHIMOKU_BEAR" in f_up or ("ICHIMOKU" in f_up and "BEAR" in f_up):
                mapped.append("Bearish Ichimoku")
            elif "RSI BULLISH DIVERGENCE" in f_up or "RSI_BULL_DIV" in f_up or ("RSI" in f_up and "BULL" in f_up and "DIV" in f_up):
                mapped.append("RSI Bullish Divergence")
            elif "RSI BEARISH DIVERGENCE" in f_up or "RSI_BEAR_DIV" in f_up or ("RSI" in f_up and "BEAR" in f_up and "DIV" in f_up):
                mapped.append("RSI Bearish Divergence")
            elif "CHEAP" in f_up or "DISCOUNT" in f_up:
                mapped.append("Cheap / Discount")
            elif "EXPENSIVE" in f_up or "PREMIUM" in f_up:
                mapped.append("Expensive / Premium")
            elif "HOTLIST" in f_up:
                mapped.append("Mango Hotlist")
            else:
                mapped.append(str(f).title())
                
        seen = set()
        return [x for x in mapped if not (x in seen or seen.add(x))]
                
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
        
        # In-memory storage for intercepted data
        intercepted_data = {}
        intercepted_global = {
            "market_trend": "NEUTRAL",
            "market_volatility": 50
        }
        
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
                    # Playwright resource types for API calls are standard 'fetch' or 'xhr'
                    is_api_request = (
                        "mangoresearch" in url and 
                        (
                            response.request.resource_type in ["fetch", "xhr"] or 
                            "application/json" in response.headers.get("content-type", "").lower() or
                            "json" in url
                        )
                    )
                    if is_api_request:
                        try:
                            # Load JSON payload
                            payload = await response.json()
                            
                            # Standardize sniffing keys: looking for objects with trend or volatility indications
                            found_valid = False
                            
                            def scan_for_trends(obj):
                                nonlocal found_valid
                                if isinstance(obj, dict):
                                    # Scan for global market metrics in root or sub-objects
                                    for k, v in obj.items():
                                        k_low = k.lower()
                                        if "market_trend" in k_low or "global_trend" in k_low or "overall_trend" in k_low:
                                            if isinstance(v, int) or str(v).isdigit():
                                                v_int = int(v)
                                                intercepted_global['market_trend'] = 'NEUTRAL' if v_int == 0 else ('LONG' if v_int == 1 else ('SHORT' if v_int == 2 else 'NEUTRAL'))
                                            else:
                                                v_str = str(v).upper()
                                                if any(t in v_str for t in ['LONG', 'SHORT', 'NEUTRAL', 'BULLISH', 'BEARISH']):
                                                    intercepted_global['market_trend'] = 'LONG' if 'LONG' in v_str or 'BULL' in v_str else ('SHORT' if 'SHORT' in v_str or 'BEAR' in v_str else 'NEUTRAL')
                                        elif "market_vol" in k_low or "global_vol" in k_low or "overall_vol" in k_low:
                                            try:
                                                intercepted_global['market_volatility'] = int(v)
                                            except ValueError:
                                                pass
                                                
                                    # Does this dictionary have keys resembling coin signals?
                                    if 'symbol' in obj or 'ticker' in obj:
                                        symbol = (obj.get('symbol') or obj.get('ticker', '')).upper()
                                        if symbol:
                                            trend_val = obj.get('trend')
                                            if trend_val is not None:
                                                if isinstance(trend_val, int) or str(trend_val).isdigit():
                                                    t_int = int(trend_val)
                                                    trend = 'NEUTRAL' if t_int == 0 else ('LONG' if t_int == 1 else ('SHORT' if t_int == 2 else 'NEUTRAL'))
                                                else:
                                                    trend = str(trend_val).upper()
                                            else:
                                                trend = str(obj.get('badge') or obj.get('direction', '')).upper()

                                            # Validate if it's a known trend type
                                            if any(t in trend for t in ['LONG', 'SHORT', 'NEUTRAL', 'BULLISH', 'BEARISH']):
                                                # Standardize ticker name (e.g. BTCUSDT -> BTC)
                                                clean_sym = symbol.replace('USDT', '').replace('.P', '').split(':')[0]
                                                
                                                # Parse bbwp volatility float/int safely
                                                bbwp_val = obj.get('bbwp') or obj.get('volatility') or obj.get('vol')
                                                try:
                                                    vol_int = int(round(float(bbwp_val))) if bbwp_val is not None else 50
                                                except (ValueError, TypeError):
                                                    vol_int = 50

                                                intercepted_data[clean_sym] = {
                                                    'trend': 'LONG' if 'LONG' in trend or 'BULL' in trend else ('SHORT' if 'SHORT' in trend or 'BEAR' in trend else 'NEUTRAL'),
                                                    'volatility': vol_int,
                                                    'flags': self.standardize_flags(obj.get('flags') or obj.get('indicators') or [])
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
                        except Exception as e:
                            logger.debug(f"JSON parsing failed for sniffed URL {url}: {e}")
                except Exception as e:
                    logger.debug(f"Error in sniffing handler: {e}")
                    
            page.on("response", handle_response)
            
            # Open the dashboard (defaults to CRYPTO tab)
            url = "https://app.mangoresearch.co/dashboard"
            try:
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(10)  # Wait for full SPA page render and network requests to complete
            except Exception as e:
                logger.error(f"Failed to load Mango Dashboard page: {e}")
                await browser.close()
                return False
                
            # --- Switch to CRYPTO Tab explicitly first ---
            try:
                logger.info("Ensuring we are on the CRYPTO tab...")
                clicked_crypto = False
                for selector in [
                    "button:has-text('CRYPTO')",
                    "text=CRYPTO",
                    "[role='button']:has-text('CRYPTO')",
                    "div:has-text('CRYPTO')"
                ]:
                    try:
                        loc = page.locator(selector).first
                        if await loc.is_visible():
                            await loc.click()
                            clicked_crypto = True
                            logger.info(f"Successfully clicked CRYPTO tab using selector: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed to click CRYPTO: {e}")
                
                if not clicked_crypto:
                    buttons = page.locator("button")
                    count = await buttons.count()
                    for idx in range(count):
                        btn = buttons.nth(idx)
                        text = await btn.inner_text()
                        if "CRYPTO" in text.upper():
                            await btn.click()
                            clicked_crypto = True
                            logger.info(f"Clicked CRYPTO tab by iterating buttons at index {idx}")
                            break
                            
                if clicked_crypto:
                    await asyncio.sleep(8)  # Wait for tab switch and render
            except Exception as e:
                logger.error(f"Error switching to CRYPTO tab: {e}")
                
            # --- Fallback & Global DOM Parser (Part 1: Crypto & Global Metrics) ---
            dom_data = {}
            dom_market_trend = "NEUTRAL"
            dom_market_volatility = 50
            
            try:
                # Capture inner text of the entire document to extract standard coin names, trend words, and global metrics
                body_text = await page.inner_text("body")
                body_lines = body_text.split('\n')
                
                # Check for "MARKET" exact label in DOM vicinity for global metrics (only visible on CRYPTO tab)
                for idx, line in enumerate(body_lines):
                    line_clean = line.strip().upper()
                    if line_clean == "MARKET":
                        vicinity_lines = [l.strip().upper() for l in body_lines[idx+1:idx+6] if l.strip()]
                        vicinity_text = " ".join(vicinity_lines)
                        
                        if "LONG" in vicinity_text or "BULL" in vicinity_text or "🟢" in vicinity_text:
                            dom_market_trend = "LONG"
                        elif "SHORT" in vicinity_text or "BEAR" in vicinity_text or "🔴" in vicinity_text:
                            dom_market_trend = "SHORT"
                        elif "NEUTRAL" in vicinity_text or "🟣" in vicinity_text:
                            dom_market_trend = "NEUTRAL"
                            
                        nums = re.findall(r'\d+', vicinity_text)
                        if nums:
                            try:
                                dom_market_volatility = int(nums[0])
                            except Exception:
                                pass
                        
                        logger.info(f"Robust DOM 'MARKET' scan parsed: Trend={dom_market_trend}, Volatility={dom_market_volatility}")
                        break
                        
                # Parse CRYPTO asset row fallbacks if sniffer missed them
                crypto_tickers = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR"]
                for ticker in crypto_tickers:
                    for i, line in enumerate(body_lines):
                        line_clean = line.upper().strip()
                        if line_clean == ticker or line_clean == f"{ticker}USDT" or line_clean == f"{ticker}-USDT":
                            # Gather lines to capture the row
                            row_lines = [l.strip() for l in body_lines[i:i+10]]
                            row_text = " ".join(row_lines).upper()
                            
                            trend = 'NEUTRAL'
                            if 'LONG' in row_text or '🟢' in row_text:
                                trend = 'LONG'
                            elif 'SHORT' in row_text or '🔴' in row_text:
                                trend = 'SHORT'
                                
                            volatility = 50
                            for r_line in row_lines[4:9]:
                                r_line_clean = r_line.replace('%', '').strip()
                                if r_line_clean.isdigit():
                                    val = int(r_line_clean)
                                    if 1 <= val <= 100:
                                        volatility = val
                                        break
                                        
                            dom_data[ticker] = {
                                'trend': trend,
                                'volatility': volatility,
                                'flags': []
                            }
                            break
            except Exception as e:
                logger.error(f"DOM parsing crypto / global metrics failed: {e}")
                
            # --- Switch to TRADFI Tab to scrape TradFi assets ---
            try:
                logger.info("Attempting to click the TRADFI tab on the dashboard...")
                clicked_tradfi = False
                for selector in [
                    "button:has-text('TRADFI')",
                    "text=TRADFI",
                    "[role='button']:has-text('TRADFI')",
                    "div:has-text('TRADFI')"
                ]:
                    try:
                        loc = page.locator(selector).first
                        if await loc.is_visible():
                            await loc.click()
                            clicked_tradfi = True
                            logger.info(f"Successfully clicked TRADFI tab using selector: {selector}")
                            break
                    except Exception as e:
                        logger.debug(f"Selector {selector} failed to click TRADFI: {e}")
                        
                if not clicked_tradfi:
                    buttons = page.locator("button")
                    count = await buttons.count()
                    for idx in range(count):
                        btn = buttons.nth(idx)
                        text = await btn.inner_text()
                        if "TRADFI" in text.upper():
                            await btn.click()
                            clicked_tradfi = True
                            logger.info(f"Clicked TRADFI tab by iterating buttons at index {idx}")
                            break
                            
                if clicked_tradfi:
                    # Wait for network requests and DOM updates on TRADFI tab
                    await asyncio.sleep(8)
                    
                    # Take a premium visual backup screenshot of the TRADFI page
                    screenshots_dir = Path("data/screenshots")
                    screenshots_dir.mkdir(parents=True, exist_ok=True)
                    screenshot_path = screenshots_dir / "mango_dashboard.png"
                    try:
                        await page.screenshot(path=str(screenshot_path))
                        logger.info(f"Visual backup screenshot saved to {screenshot_path}")
                    except Exception as e:
                        logger.warning(f"Could not take dashboard screenshot: {e}")
                        
                    # --- Fallback DOM Parser (Part 2: TradFi) ---
                    try:
                        tradfi_text = await page.inner_text("body")
                        tradfi_lines = tradfi_text.split('\n')
                        
                        tradfi_tickers = ["SPY", "QQQ", "GLD", "SLV", "USO"]
                        for ticker in tradfi_tickers:
                            for i, line in enumerate(tradfi_lines):
                                if ticker == line.upper().strip():
                                    row_lines = [l.strip() for l in tradfi_lines[i:i+10]]
                                    row_text = " ".join(row_lines).upper()
                                    
                                    trend = 'NEUTRAL'
                                    if 'LONG' in row_text or '🟢' in row_text:
                                        trend = 'LONG'
                                    elif 'SHORT' in row_text or '🔴' in row_text:
                                        trend = 'SHORT'
                                        
                                    volatility = 50
                                    for r_line in row_lines[4:9]:
                                        r_line_clean = r_line.replace('%', '').strip()
                                        if r_line_clean.isdigit():
                                            val = int(r_line_clean)
                                            if 1 <= val <= 100:
                                                volatility = val
                                                break
                                                
                                    dom_data[ticker] = {
                                        'trend': trend,
                                        'volatility': volatility,
                                        'flags': []
                                    }
                                    break
                    except Exception as e:
                        logger.error(f"DOM parsing tradfi failed: {e}")
                else:
                    logger.warning("Could not find or click the TRADFI tab button on the dashboard.")
            except Exception as e:
                logger.error(f"Error during TRADFI switching / scraping: {e}")
                
            # Determine final global values (sniffed has priority, DOM is fallback)
            final_market_trend = intercepted_global.get("market_trend", "NEUTRAL")
            if final_market_trend == "NEUTRAL" and dom_market_trend != "NEUTRAL":
                final_market_trend = dom_market_trend
                
            final_market_volatility = intercepted_global.get("market_volatility", 50)
            if final_market_volatility == 50 and dom_market_volatility != 50:
                final_market_volatility = dom_market_volatility
            
            # Combine sniffed and DOM data (sniffed has priority)
            final_assets = {**dom_data, **intercepted_data}
            # Explicitly store base timeframe "1D" for all assets
            for sym in final_assets:
                final_assets[sym]["timeframe"] = "1D"
            
            if not final_assets:
                logger.error("No coin data could be extracted from Mango Research Dashboard. Session might be expired!")
                await browser.close()
                return False
                
            # Core watchlist assets we actively track and trade
            CORE_SCRAPE_ASSETS = {
                "BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE",
                "TRX", "INJ", "ONDO", "NEAR",
                "SPY", "QQQ", "GLD", "SLV", "USO", "SPX", "NDX", "GOLD", "SILVER", "OIL"
            }

            # --- Per-asset timeframe breakdown scraping ---
            # Navigate each non-NEUTRAL core asset's detail page to capture TF alignment
            for sym, asset_info in list(final_assets.items()):
                sym_up = sym.upper()
                if sym_up not in CORE_SCRAPE_ASSETS:
                    continue
                if asset_info.get('trend', 'NEUTRAL') == 'NEUTRAL':
                    continue  # Only scrape detail for directional assets
                try:
                    tf_result = await self._scrape_asset_timeframes(page, sym)
                    if tf_result:
                        trends = tf_result.get('trends', {})
                        flags  = tf_result.get('flags', {})
                        vols   = tf_result.get('volatilities', {})
                        final_assets[sym]['timeframes']      = trends
                        final_assets[sym]['timeframe_flags'] = flags
                        final_assets[sym]['timeframe_volatilities'] = vols
                        mtf = self._evaluate_mtf_filters(trends, flags)
                        final_assets[sym]['mtf_bullish'] = mtf['mtf_bullish']
                        final_assets[sym]['mtf_bearish'] = mtf['mtf_bearish']
                        logger.info(
                            f"Captured {len(trends)} TF(s) for {sym} | "
                            f"Mango Bullish: {mtf['mtf_bullish']} | "
                            f"Mango Bearish: {mtf['mtf_bearish']}"
                        )
                except Exception as e:
                    logger.warning(f"Could not scrape timeframe detail for {sym}: {e}")

            # Create standardized payload with global market variables
            result = {
                "updated_at": datetime.utcnow().isoformat() + "Z",
                "timeframe": "1D",  # Base timeframe for the trend badges on the main dashboard page
                "market_trend": final_market_trend,
                "market_volatility": final_market_volatility,
                "assets": final_assets
            }
            
            # Save locally
            CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
            with open(CACHE_FILE, "w") as f:
                json.dump(result, f, indent=2)
            logger.info(f"Cached {len(final_assets)} dashboard assets and global market variables locally to {CACHE_FILE}")
            
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
        asset_name = asset_name.upper().replace('USDT', '').replace('.P', '').split(':')[0].strip()
        
        # Apply symbol mapping for TradFi index / commodity assets to ETF tickers
        SYMBOL_MAP = {
            "SPX": "SPY",
            "NDX": "QQQ",
            "GOLD": "GLD",
            "SILVER": "SLV",
            "OIL": "USO"
        }
        if asset_name in SYMBOL_MAP:
            asset_name = SYMBOL_MAP[asset_name]
        
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

    def get_global_metrics(self) -> dict:
        """Get the cached global market trend and volatility metrics"""
        # PostgreSQL first
        try:
            if self.datastore:
                db_data = self.datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
                if db_data:
                    data = json.loads(db_data)
                    return {
                        "market_trend": data.get("market_trend", "NEUTRAL"),
                        "market_volatility": data.get("market_volatility", 50)
                    }
        except Exception as e:
            logger.error(f"Failed to retrieve global metrics from DB: {e}")
            
        # Local fallback
        if CACHE_FILE.exists():
            try:
                with open(CACHE_FILE, "r") as f:
                    data = json.load(f)
                    return {
                        "market_trend": data.get("market_trend", "NEUTRAL"),
                        "market_volatility": data.get("market_volatility", 50)
                    }
            except Exception as e:
                logger.error(f"Failed to read local cache file for global metrics: {e}")
                
        return {"market_trend": "NEUTRAL", "market_volatility": 50}

    async def _scrape_asset_timeframes(self, page, symbol: str) -> dict:
        """
        Navigate to the asset detail page and extract per-timeframe trend AND flags.

        Returns:
            {
              'trends': {'4H': 'LONG', '1D': 'NEUTRAL', ...},
              'flags':  {'4H': ['Golden Cross'], '12H': [], '1D': ['Golden Cross'], ...}
            }
        """
        trends:  dict = {}
        flags:   dict = {}
        detail_url = f"https://app.mangoresearch.co/dashboard/{symbol.lower()}"

        # Intercept JSON on the detail page
        detail_intercepted: dict = {}  # tf_key -> {trend, flags}

        async def handle_tf_response(response):
            try:
                url = response.url.lower()
                content_type = response.headers.get("content-type", "").lower() if response.headers else ""
                is_api_request = (
                    "mangoresearch" in url and 
                    (
                        response.request.resource_type in ["fetch", "xhr"] or 
                        "application/json" in content_type or
                        "json" in url
                    )
                )
                if is_api_request:
                    try:
                        payload = await response.json()

                        def scan_tf(obj):
                            if isinstance(obj, dict):
                                tf_key = (obj.get('timeframe') or obj.get('tf')
                                          or obj.get('interval'))
                                trend  = (obj.get('trend') or obj.get('badge')
                                          or obj.get('direction'))
                                if tf_key and trend is not None:
                                    if isinstance(trend, int) or str(trend).isdigit():
                                        t_int = int(trend)
                                        mapped = 'NEUTRAL' if t_int == 0 else ('LONG' if t_int == 1 else ('SHORT' if t_int == 2 else 'NEUTRAL'))
                                    else:
                                        t_str  = str(trend).upper()
                                        mapped = ('LONG'    if 'LONG'  in t_str or 'BULL' in t_str
                                                  else 'SHORT'   if 'SHORT' in t_str or 'BEAR' in t_str
                                                  else 'NEUTRAL')
                                    # Capture indicator flags for this timeframe
                                    raw_flags = (obj.get('flags') or obj.get('indicators')
                                                 or obj.get('signals') or [])
                                    clean_flags = self.standardize_flags(raw_flags)

                                    # Capture bbwp volatility for this timeframe
                                    bbwp_val = obj.get('bbwp') or obj.get('volatility') or obj.get('vol')
                                    try:
                                        tf_vol = int(round(float(bbwp_val))) if bbwp_val is not None else 50
                                    except (ValueError, TypeError):
                                        tf_vol = 50

                                    tf_label = str(tf_key).upper()
                                    detail_intercepted[tf_label] = {
                                        'trend': mapped,
                                        'flags': clean_flags,
                                        'volatility': tf_vol
                                    }
                                for v in obj.values():
                                    scan_tf(v)
                            elif isinstance(obj, list):
                                for item in obj:
                                    scan_tf(item)

                        scan_tf(payload)
                    except Exception:
                        pass
            except Exception:
                pass

        page.on("response", handle_tf_response)
        try:
            await page.goto(detail_url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(5)  # Wait for SPA render

            if detail_intercepted:
                trends = {tf: v['trend'] for tf, v in detail_intercepted.items()}
                flags  = {tf: v['flags'] for tf, v in detail_intercepted.items()}
                vols   = {tf: v['volatility'] for tf, v in detail_intercepted.items()}
            else:
                # DOM fallback: look for rows containing a timeframe label + trend word
                body_text = await page.inner_text("body")
                tf_labels = ["15M", "1H", "2H", "4H", "8H", "12H", "1D", "2D", "3D", "4D", "1W"]
                lines = body_text.split('\n')
                for i, line in enumerate(lines):
                    line_up = line.upper().strip()
                    for label in tf_labels:
                        if label == line_up or (label in line_up and len(line_up) < 20):
                            block = " ".join(lines[i:i+5]).upper()
                            if 'LONG' in block or 'BULLISH' in block:
                                trends[label] = 'LONG'
                            elif 'SHORT' in block or 'BEARISH' in block:
                                trends[label] = 'SHORT'
                            elif 'NEUTRAL' in block:
                                trends[label] = 'NEUTRAL'
                            # Try to capture flags from the nearby block
                            tf_flags = []
                            block_up = block.upper()
                            if 'GOLDEN CROSS' in block_up or 'GOLDEN_CROSS' in block_up:
                                tf_flags.append('Golden Cross')
                            if 'DEATH CROSS' in block_up or 'DEATH_CROSS' in block_up:
                                tf_flags.append('Death Cross')
                            if 'BULLISH ICHIMOKU' in block_up or 'ICHIMOKU BULLISH' in block_up:
                                tf_flags.append('Bullish Ichimoku')
                            if 'BEARISH ICHIMOKU' in block_up or 'ICHIMOKU BEARISH' in block_up:
                                tf_flags.append('Bearish Ichimoku')
                            if 'RSI BULLISH DIVERGENCE' in block_up or 'RSI_BULLISH_DIV' in block_up:
                                tf_flags.append('RSI Bullish Divergence')
                            if 'RSI BEARISH DIVERGENCE' in block_up or 'RSI_BEARISH_DIV' in block_up:
                                tf_flags.append('RSI Bearish Divergence')
                            if 'CHEAP' in block_up or 'DISCOUNT' in block_up:
                                tf_flags.append('Cheap / Discount')
                            if 'EXPENSIVE' in block_up or 'PREMIUM' in block_up:
                                tf_flags.append('Expensive / Premium')
                            if 'HOTLIST' in block_up or 'MANGO HOTLIST' in block_up:
                                tf_flags.append('Mango Hotlist')
                                
                            if label in trends:
                                flags[label] = tf_flags
                            break
                vols = {tf: 50 for tf in trends}
        except Exception as e:
            logger.warning(f"Detail page navigation failed for {symbol}: {e}")
        finally:
            page.remove_listener("response", handle_tf_response)

        return {'trends': trends, 'flags': flags, 'volatilities': vols}

    def _evaluate_mtf_filters(self, trends: dict, flags: dict) -> dict:
        """
        Evaluate whether an asset passes the user's saved MTF presets on the
        Mango Research Dashboard.

        Mango Bullish (from dashboard preset):
            - 4H, 12H, 1D timeframes have the 'Golden Cross' indicator flag
            - 2D, 4D trend is LONG

        Mango Bearish (from dashboard preset):
            - 4H, 12H, 1D timeframes have the 'Death Cross' indicator flag
            - 2D, 4D trend is SHORT

        Returns:
            {'mtf_bullish': bool, 'mtf_bearish': bool}
        """
        def has_flag(tf: str, flag_name: str) -> bool:
            """True only if we scraped flag data for this TF AND the flag is present."""
            tf_flags = flags.get(tf)
            if tf_flags is None:
                return False  # No data = cannot confirm
            return any(flag_name.lower() in f.lower() for f in tf_flags)

        def has_trend(tf: str, required: str) -> bool:
            """True only if we have trend data for this TF AND it matches."""
            t = trends.get(tf)
            if not t:
                return False  # No data = cannot confirm
            return t.upper() == required.upper()

        # ── Mango Bullish ────────────────────────────────────────────────────
        mtf_bullish = (
            has_flag('4H',  'Golden Cross') and
            has_flag('12H', 'Golden Cross') and
            has_flag('1D',  'Golden Cross') and
            has_trend('2D', 'LONG') and
            has_trend('4D', 'LONG')
        )

        # ── Mango Bearish ────────────────────────────────────────────────────
        mtf_bearish = (
            has_flag('4H',  'Death Cross') and
            has_flag('12H', 'Death Cross') and
            has_flag('1D',  'Death Cross') and
            has_trend('2D', 'SHORT') and
            has_trend('4D', 'SHORT')
        )

        return {'mtf_bullish': mtf_bullish, 'mtf_bearish': mtf_bearish}

    def get_all_cached_assets(self) -> dict:
        """Return the full asset dict from cache (for the native signal detector)."""
        from pathlib import Path
        CACHE = Path("data/mango_dashboard.json")
        try:
            if self.datastore:
                raw = self.datastore.get_setting("MANGO_DASHBOARD_CACHED_DATA")
                if raw:
                    return json.loads(raw).get("assets", {})
        except Exception:
            pass
        if CACHE.exists():
            try:
                with open(CACHE) as f:
                    return json.load(f).get("assets", {})
            except Exception:
                pass
        return {}
