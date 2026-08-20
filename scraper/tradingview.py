"""TradingView Mango Dynamic scraper"""
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_FILE = "tv_state.json"

class TradingViewScraper:
    """Scrapes Mango Dynamic indicator data from TradingView"""
    
    def __init__(self, state_file=STATE_FILE):
        self.state_file = Path(state_file)
        
        import os
        import json
        from detection.datastore import MangoDataStore
        
        # Try to restore from Postgres DataStore first (Rolling Sessions feature)
        try:
            self.datastore = MangoDataStore()
            db_state = self.datastore.get_setting("TV_STATE")
            if db_state:
                logger.info("Restoring TradingView session state from Database...")
                with open(self.state_file, "w") as f:
                    f.write(db_state)
        except Exception as e:
            logger.error(f"Failed to check DB for TV_STATE: {e}")
            self.datastore = None

        # Support cloud deployment: Restore state from Env Var if file missing
        if not self.state_file.exists() and os.getenv("TRADINGVIEW_STATE_JSON"):
            try:
                logger.info("Restoring TradingView session state from environment variable...")
                with open(self.state_file, "w") as f:
                    f.write(os.getenv("TRADINGVIEW_STATE_JSON"))
            except Exception as e:
                logger.error(f"Failed to restore state from env: {e}")
    
    async def scrape_asset(self, context, asset, timeframe):
        """Scrape a single asset/timeframe using existing browser context"""
        symbol = asset['symbol']
        name = asset['name']
        
        import os
        from config import settings
        page = await context.new_page()
        
        try:
            # Determine Layout ID (Timeframe specific > Default > None)
            layout_id = settings.LAYOUTS.get(timeframe.lower())
            if not layout_id:
                layout_id = settings.LAYOUTS.get('default')
            
            # Extract ID if URL is provided (e.g. from https://www.tradingview.com/chart/ID/)
            if layout_id and 'tradingview.com/chart/' in str(layout_id):
                try:
                    import re
                    match = re.search(r'chart/([^/]+)', str(layout_id))
                    if match:
                        layout_id = match.group(1)
                except Exception:
                    pass
                
            if layout_id:
                url = f"https://www.tradingview.com/chart/{layout_id}/?symbol={symbol}"
            else:
                # Default generic URL
                url = f"https://www.tradingview.com/chart/?symbol={symbol}"

            logger.info(f"Scraping {name} [{timeframe}] - URL: {url}")
            
            # Increased timeout to 60s
            await page.goto(url, wait_until="domcontentloaded", timeout=60000)
            await asyncio.sleep(8)
            
            # Ensure layout loaded
            try:
                has_mango = await page.evaluate("() => document.body.innerText.includes('Mango')")
                if not has_mango:
                    await page.keyboard.type(".")
                    await asyncio.sleep(1)
                    await page.keyboard.type("Arcane Portal")
                    await asyncio.sleep(1)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(8)
            except Exception:
                pass # Continue if check fails
                
            # FORCE SYMBOL CHANGE VIA KEYBOARD
            # Custom layouts often ignore the ?symbol= parameter in the URL.
            # Typing the symbol directly (starting with a letter) opens Symbol Search.
            try:
                await page.keyboard.press("Escape")
                await asyncio.sleep(0.5)
                # Type the full exchange:symbol string
                await page.keyboard.type(symbol, delay=50) # Small delay to ensure letters register
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                await asyncio.sleep(3) # Wait for new asset to render
            except Exception as e:
                logger.warning(f"Failed to force keyboard symbol change for {symbol}: {e}")
            
            # Ensure Data Window open
            try:
                is_dw = await page.evaluate("() => document.body.innerText.includes('Entry Zone Upper')")
                if not is_dw:
                    await page.keyboard.press("Alt+D")
                    await asyncio.sleep(2)
            except Exception:
                pass
            
            # Map timeframe to TradingView format
            timeframe_map = {
                "3m": "3",
                "5m": "5",
                "15m": "15",
                "30m": "30",
                "1h": "1H",
                "4h": "4H",
                "12h": "12H",
                "1d": "1D",    # Was "D", but typing a letter first triggers Symbol Search!
                "4d": "4D",
                "1w": "1W"
            }
            
            tv_timeframe = timeframe_map.get(timeframe, timeframe)
            
            # Switch timeframe via keyboard
            # Numbers open the "Change Interval" dialog.
            await page.keyboard.type(tv_timeframe, delay=50)
            await asyncio.sleep(0.5)
            await page.keyboard.press("Enter")
            await asyncio.sleep(1)
            
            # Join 'data' and 'screenshots' path
            import os
            screenshots_dir = os.path.join("data", "screenshots")
            os.makedirs(screenshots_dir, exist_ok=True)
            
            # Reset chart view to latest candle
            await asyncio.sleep(1)
            await page.keyboard.press("Alt+R")
            
            # Wait for timeframe to load
            # Daily and 4-day charts take significantly longer for the Mango Dynamic
            # indicator to fully render all its values — previous 5s was too short.
            if timeframe in ['4d']:
                wait_time = 15
            elif timeframe in ['1d', '12h']:
                wait_time = 12
            else:
                wait_time = 4
            await asyncio.sleep(wait_time)
            
            # Hide floating toolbars, dialogs/popups (like Easter sale), and banners (user request)
            try:
                await page.add_style_tag(content="""
                    /* Toolbars */
                    .tv-floating-toolbar, 
                    .drawing-toolbar, 
                    .tv-favorited-drawings-toolbar,
                    [class*="floating-toolbar"],
                    [class*="floatingToolbar"],
                    [data-name="drawing-toolbar"],
                    
                    /* Dialogs & Popups (Easter Sale, etc.) */
                    [role="dialog"],
                    [class*="dialog-"],
                    [class*="modal-"],
                    [class*="popup-"],
                    .tv-dialog,
                    .tv-modal,
                    
                    /* Banners & Promo */
                    [class*="banner-"],
                    [class*="promo-"],
                    [class*="toast-"],
                    [class*="onboarding-"] {
                        display: none !important;
                    }
                """)
            except Exception:
                pass

            # Take screenshot (after wait, before scraping values)
            # Filename: BTC_4h.png
            screenshot_path = os.path.join(screenshots_dir, f"{name}_{timeframe}.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception as e:
                logger.warning(f"Failed to save screenshot for {name} {timeframe}: {e}")
            
            # Hover current candle with retries
            # More retries for slower HTF timeframes
            max_retries = 5 if timeframe in ['1d', '4d', '12h'] else 3
            data = None
            
            for attempt in range(max_retries):
                # Move mouse to far right to trigger data window update for LATEST candle
                # Viewport is 1920 wide. 1150 was fetching historical candles.
                await page.mouse.move(1800, 500)
                await asyncio.sleep(1)
                
                # Extract data
                data = await page.evaluate(r"""(() => {
                    const res = { PlotValues: {}, Timestamp: new Date().toISOString() };
                    const txt = document.body.innerText;
                    
                    const findVal = (key, rawChar) => {
                        const safeKey = key.replace(/ /g, '[\\s\\n]+');
                        const re1 = new RegExp(safeKey + "[:\\s\\n\\-]*(-?[0-9,.]+)", "i");
                        let m = txt.match(re1);
                        if (m) return parseFloat(m[1].replace(/,/g, ''));
                        
                        if (rawChar) {
                            const re2 = new RegExp("\\b" + rawChar + "[:\\s\\-]*(-?[0-9,.]+)", "i");
                            m = txt.match(re2);
                            if (m) return parseFloat(m[1].replace(/,/g, ''));
                        }
                        return null;
                    };
                    
                    const parseVol = () => {
                        const re = /Vol(?:ume)?[:\s]*([0-9,.]+)([KMB]?)/i;
                        const m = txt.match(re);
                        if (!m) return null;
                        let v = parseFloat(m[1].replace(/,/g, ''));
                        const s = m[2].toUpperCase();
                        if (s === 'K') v *= 1000;
                        else if (s === 'M') v *= 1000000;
                        else if (s === 'B') v *= 1000000000;
                        return v;
                    };
                    
                    const parseTrend = () => {
                        // Matches "Trend: Neutral", "Trend: Bullish", etc.
                        const re = /Trend[:\s]*([A-Za-z]+)/i;
                        const m = txt.match(re);
                        return m ? m[1].trim() : null;
                    };
                    
                    res.PlotValues = {
                        Open: findVal('Open', 'O'),
                        High: findVal('High', 'H'),
                        Low: findVal('Low', 'L'),
                        Close: findVal('Close', 'C'),
                        Volume: parseVol(),
                        Trend: parseTrend(),
                        D1: findVal('MangoD1'),
                        D2: findVal('MangoD2'),
                        EntryUp: findVal('Entry Zone Upper'),
                        EntryDown: findVal('Entry Zone Lower'),
                        // Mango Equilibrium Tracker fields
                        UpperVolB: findVal('Upper VolB'),
                        LowerVolB: findVal('Lower VolB'),
                        EqBand1: (() => {
                            // Match 'eqband' NOT followed by '2' (i.e. exclude eqband2)
                            const re = /eqband(?!2)[:\s\n\-]*(-?[0-9,.]+)/i;
                            const m = txt.match(re);
                            return m ? parseFloat(m[1].replace(/,/g, '')) : null;
                        })(),
                        EqBand2: findVal('eqband2'),
                        // Mutanabby AI Confluences
                        MutanabbySig: (() => {
                            const lines = txt.split('\n');
                            let mutSection = [];
                            let inMut = false;
                            for (let i = 0; i < lines.length; i++) {
                                const clean = lines[i].trim();
                                if (clean.includes('Mutanabby_AI')) {
                                    inMut = true;
                                    continue;
                                }
                                if (inMut) {
                                    if (/Mango Dynamic|Mango Ribbon|Mango Equilibrium|Vol |Volume|Open|Date|Time/i.test(clean)) {
                                        inMut = false;
                                        continue;
                                    }
                                    mutSection.push(clean.toLowerCase());
                                }
                            }
                            let isStrong = false;
                            let isBuy = false;
                            let isSell = false;
                            for (let i = 0; i < mutSection.length; i++) {
                                const term = mutSection[i];
                                if (term.includes('strong')) isStrong = true;
                                if (term.includes('buy')) isBuy = true;
                                if (term.includes('sell')) isSell = true;
                            }
                            if (isBuy) return isStrong ? 2.0 : 1.0;
                            if (isSell) return isStrong ? -2.0 : -1.0;
                            return 0.0;
                        })(),
                        // Mango Ribbon TK Crosses
                        TKCross: (() => {
                            const bull = findVal('TK Bull Cross');
                            const bear = findVal('TK Bear Cross');
                            if (bull !== null && bull > 0.0) return 1.0;
                            if (bear !== null && bear > 0.0) return -1.0;
                            return 0.0;
                        })()
                    };
                    
                    return res;
                })()""")
                
                # Validate data
                close_price = data['PlotValues'].get('Close')
                is_valid = close_price is not None and close_price != 1.0
                
                if is_valid:
                    break
                elif attempt < max_retries - 1:
                    logger.warning(f"⚠️  {name} [{timeframe}] attempt {attempt + 1}: Invalid price ${close_price}, retrying...")
                    await asyncio.sleep(3)  # Wait longer between retries on slow TFs
                else:
                    logger.error(f"✗ {name} [{timeframe}]: Failed to get valid price after {max_retries} attempts")
            
            # Read screenshot bytes
            screenshot_bytes = None
            if os.path.exists(screenshot_path):
                 try:
                     with open(screenshot_path, 'rb') as f:
                         screenshot_bytes = f.read()
                 except Exception:
                     pass

            # --- CRITICAL VALIDATION ---
            # close=1.0 is TradingView's placeholder value when the indicator hasn't loaded.
            # Storing it overwrites good historical data. Always reject it.
            final_close = data['PlotValues'].get('Close') if data else None
            if not data or not final_close or final_close == 1.0:
                logger.error(f"✗ {name} [{timeframe}]: Discarding invalid close={final_close} — not saving to DB.")
                return None
            # ---------------------------

            result = {
                "symbol": symbol,
                "name": name,
                "timeframe": timeframe,
                "timestamp": datetime.utcnow().isoformat(),
                "screenshot_bytes": screenshot_bytes,
                **data
            }
            
            logger.info(f"✓ {name} [{timeframe}] - Close: {data['PlotValues'].get('Close')}")
            return result
            
        except Exception as e:
            logger.error(f"✗ Error scraping {name} [{timeframe}]: {e}")
            return None
        finally:
            await page.close()
    
    async def scrape_all_assets(self, assets, use_smart_scheduling=True):
        """Scrape all assets using a persistent browser instance"""
        from scraper.scheduler import TimeframeScheduler
        
        results = []
        total_assets = len(assets)
        
        # Initialize scheduler
        scheduler = TimeframeScheduler() if use_smart_scheduling else None
        
        if use_smart_scheduling:
            timeframes_to_scrape = scheduler.get_timeframes_to_scrape()
            print(f"\n🧠 SMART SCHEDULING ENABLED")
            print(f"   Timeframes to scrape: {timeframes_to_scrape}")
            print(f"   Skipping: {[tf for tf in ['3m', '15m', '1h', '4h', '12h', '1d', '4d'] if tf not in timeframes_to_scrape]}")
            print()
            
            if not timeframes_to_scrape:
                print("⏭️  No timeframes need scraping right now. Skipping this run.")
                return []
        
        # Launch browser once
        async with async_playwright() as p:
            print("Starting Container (Browser)...")
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            
            if not self.state_file.exists():
                logger.error("tv_state.json not found!")
                print("❌ TV State file not found!")
                return []
                
            context = await browser.new_context(
                storage_state=str(self.state_file),
                viewport={'width': 1920, 'height': 1080}
            )
            
            for idx, asset in enumerate(assets, 1):
                logger.info(f"Scraping {idx}/{total_assets}: {asset['name']}")
                print(f"\n  [{idx}/{total_assets}] {asset['name']} - {asset['type'].upper()}")
                
                # Filter timeframes
                timeframes_for_asset = asset['timeframes']
                if use_smart_scheduling:
                    timeframes_for_asset = [tf for tf in asset['timeframes'] if tf in timeframes_to_scrape]
                
                if not timeframes_for_asset:
                    print(f"    ⏭️  No timeframes to scrape")
                    continue
                
                for timeframe in timeframes_for_asset:
                    data = await self.scrape_asset(context, asset, timeframe)
                    if data:
                        results.append(data)
                        self._print_timeframe_data(timeframe, data, asset)
                    else:
                        print(f"    ✗ {timeframe} failed (no data)")
                
                if idx < total_assets:
                    await asyncio.sleep(0.5)
            
            # Save refreshed state back to DB for rolling session
            try:
                import json
                new_state = await context.storage_state()
                if self.datastore:
                    self.datastore.set_setting("TV_STATE", json.dumps(new_state))
                # Also save locally so next run picks it up immediately
                with open(self.state_file, "w") as f:
                    json.dump(new_state, f)
            except Exception as e:
                logger.error(f"Failed to save rolling session state: {e}")

            await context.close()
            await browser.close()
        
        logger.info(f"Scrape completed: {len(results)} timeframes")
        return results
    
    def _print_timeframe_data(self, timeframe, data, asset):
        """Helper to print timeframe data with precision and Mango values"""
        vals = data.get('PlotValues', {})
        price = vals.get('Close', 0)
        mango_d1 = vals.get('D1', 0)
        mango_d2 = vals.get('D2', 0)
        entry_up = vals.get('EntryUp', 0)
        entry_down = vals.get('EntryDown', 0)
        
        precision = asset.get('precision', 2)
        
        if price and mango_d2:
            if mango_d1 and mango_d2:
                if price > mango_d2: trend = "BULLISH"
                elif price < mango_d1: trend = "BEARISH"
                else: trend = "NEUTRAL"
            else:
                trend = "UNKNOWN"
            
            in_zone = "YES" if (entry_down <= price <= entry_up) else "NO"
            
            # Formatted output
            print(f"    {timeframe:>3} | Price: ${price:>10,.{precision}f} | Trend: {trend:>8} | In Bid Zone: {in_zone}")
            print(f"         Bid Zone: ${entry_down:,.{precision}f} - ${entry_up:,.{precision}f}")
            print(f"         Mango: D1=${mango_d1:,.{precision}f} | D2=${mango_d2:,.{precision}f}")
        else:
            print(f"    ✗ {timeframe} failed (no data)")

    async def stream_assets(self, assets, use_smart_scheduling=True):
        """Yield results per asset immediately for streaming processing"""
        from playwright.async_api import async_playwright
        from scraper.scheduler import TimeframeScheduler
        
        # Scheduler logic
        scheduler = TimeframeScheduler() if use_smart_scheduling else None
        timeframes_to_scrape = []
        if use_smart_scheduling:
            timeframes_to_scrape = scheduler.get_timeframes_to_scrape()
            if not timeframes_to_scrape:
                logger.info("No timeframes to scrape.")
                return

        # Launch browser once
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage']
            )
            
            if not self.state_file.exists():
                logger.error("tv_state.json not found!")
                return 

            context = await browser.new_context(
                storage_state=str(self.state_file),
                viewport={'width': 1920, 'height': 1080}
            )

            total = len(assets)
            for idx, asset in enumerate(assets, 1):
                asset_results = []
                
                # Filter timeframes (if smart scheduling)
                tfs = asset['timeframes']
                if use_smart_scheduling:
                    tfs = [tf for tf in tfs if tf in timeframes_to_scrape]
                
                if not tfs:
                    continue

                print(f"\nProcessing {idx}/{total}: {asset['name']} ({len(tfs)} TFs)...")

                # Parallelize timeframe scraping for this asset
                # Limit concurrency to 2 tabs to manage RAM usage (Cost optimization)
                semaphore = asyncio.Semaphore(2)
                
                async def scrape_with_limit(tf):
                    async with semaphore:
                        try:
                            # 90 second timeout per asset per timeframe to prevent Playwright deadlocks
                            return await asyncio.wait_for(self.scrape_asset(context, asset, tf), timeout=90)
                        except asyncio.TimeoutError:
                            logger.error(f"Timeout scraping {asset['name']} {tf}")
                            return None

                # Create tasks for all timeframes
                tasks = [scrape_with_limit(timeframe) for timeframe in tfs]
                
                # Execute all timeframes concurrently
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                for res in results:
                    if isinstance(res, Exception):
                        logger.error(f"Error scraping timeframe: {res}")
                    elif res:
                        asset_results.append(res)
                        self._print_timeframe_data(res['timeframe'], res, asset)
                
                if asset_results:
                    yield asset_results
            
            # Save refreshed state back to DB for rolling session
            try:
                import json
                new_state = await context.storage_state()
                if self.datastore:
                    self.datastore.set_setting("TV_STATE", json.dumps(new_state))
                # Also save locally so next run picks it up immediately
                with open(self.state_file, "w") as f:
                    json.dump(new_state, f)
            except Exception as e:
                logger.error(f"Failed to save rolling session state: {e}")
                
            await context.close()
            await browser.close()

    async def scrape_single_asset_all_tfs(self, asset_name: str) -> Dict[str, Dict]:
        """
        Perform a targeted live Playwright scrape for a single asset across 
        all 7 timeframes (1w, 4d, 1d, 12h, 4h, 1h, 15m).
        Ensures 100% chart accuracy over speed.
        """
        from config.assets import ASSETS
        from datetime import timezone
        
        # Find asset config entry
        asset_info = None
        for a in ASSETS:
            if a['name'].strip().upper() == asset_name.strip().upper():
                asset_info = a
                break
                
        if not asset_info:
            asset_info = {
                "symbol": f"BYBIT:{asset_name.strip().upper()}USDT.P",
                "name": asset_name.strip().upper(),
                "type": "crypto"
            }

        scraped_data = {}
        timeframes = ["1w", "4d", "1d", "12h", "4h", "1h", "15m"]

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=["--no-sandbox", "--disable-setuid-sandbox"]
            )
            
            context_kwargs = {
                "viewport": {"width": 1920, "height": 1080},
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            }
            if self.state_file.exists():
                context_kwargs["storage_state"] = str(self.state_file)

            context = await browser.new_context(**context_kwargs)
            page = await context.new_page()

            try:
                import os
                import re
                from config import settings
                
                symbol = asset_info['symbol']
                layout_id = settings.LAYOUTS.get('default') or os.getenv("TRADINGVIEW_LAYOUT_ID", "")
                if layout_id and 'tradingview.com/chart/' in str(layout_id):
                    m = re.search(r'chart/([^/]+)', str(layout_id))
                    if m:
                        layout_id = m.group(1)

                if layout_id:
                    url = f"https://www.tradingview.com/chart/{layout_id}/?symbol={symbol}"
                else:
                    url = f"https://www.tradingview.com/chart/?symbol={symbol}"

                logger.info(f"🎯 Targeted Live Scrape starting for {asset_name} ({symbol}) - URL: {url}")

                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(8)

                try:
                    await page.keyboard.press("Escape")
                    await asyncio.sleep(0.5)
                    await page.keyboard.type(symbol, delay=50)
                    await asyncio.sleep(1)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(4)
                except Exception as se:
                    logger.warning(f"Symbol load warning: {se}")

                try:
                    is_dw = await page.evaluate("() => document.body.innerText.includes('Entry Zone Upper')")
                    if not is_dw:
                        await page.keyboard.press("Alt+D")
                        await asyncio.sleep(2)
                except Exception:
                    pass

                timeframe_map = {
                    "15m": "15",
                    "1h": "1H",
                    "4h": "4H",
                    "12h": "12H",
                    "1d": "1D",
                    "4d": "4D",
                    "1w": "1W"
                }

                for tf in timeframes:
                    tv_tf = timeframe_map.get(tf, tf)
                    logger.info(f"📸 Live scraping chart for {asset_name} [{tf.upper()}]...")

                    await page.keyboard.type(tv_tf, delay=50)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(1)
                    await page.keyboard.press("Alt+R")

                    # Generous render wait time for 100% chart accuracy
                    wait_sec = 8.0 if tf in ['1w', '4d', '1d'] else 4.5
                    await asyncio.sleep(wait_sec)

                    await page.mouse.move(1800, 500)
                    await asyncio.sleep(1)

                    plot_data = await page.evaluate(r"""(() => {
                        const txt = document.body.innerText;
                        
                        const findVal = (key) => {
                            const safeKey = key.replace(/ /g, '[\\s\\n]+');
                            const re = new RegExp(safeKey + "[:\\s\\n\\-]*(-?[0-9,.]+)", "i");
                            const m = txt.match(re);
                            return m ? parseFloat(m[1].replace(/,/g, '')) : null;
                        };

                        const parseTrend = () => {
                            const re = /Trend[:\s]*([A-Za-z]+)/i;
                            const m = txt.match(re);
                            return m ? m[1].trim() : null;
                        };

                        const mutSig = (() => {
                            let text = "";
                            const nodes = document.querySelectorAll('[class*="item-"], [class*="legend-"], [class*="dataWindow-"], [class*="cell-"]');
                            nodes.forEach(n => {
                                text += " " + (n.innerText || n.textContent || "");
                            });

                            if (!text || text.length < 5) {
                                text = document.body.innerText;
                            }

                            const lower = text.toLowerCase();

                            if (lower.includes('strong sell')) return -2.0;
                            if (lower.includes('strong buy')) return 2.0;

                            const lines = text.split('\n');
                            for (let i = 0; i < lines.length; i++) {
                                const l = lines[i].trim().toLowerCase();
                                if (l.includes('mutanabby') || l.includes('peak profit') || l.includes('ultimate algo')) {
                                    if (l.includes('sell') || l.includes('-')) return -1.0;
                                    if (l.includes('buy') || l.includes('+')) return 1.0;
                                }
                            }

                            const rePeak = /peak\s*profit[:\s]*([+-]?[0-9,.]+%?)/i;
                            const mPeak = text.match(rePeak);
                            if (mPeak) {
                                return mPeak[1].includes('-') ? -1.0 : 1.0;
                            }

                            return 0.0;
                        })();

                        const tkCross = (() => {
                            const bull = findVal('TK Bull Cross');
                            const bear = findVal('TK Bear Cross');
                            if (bull && bull > 0) return 1.0;
                            if (bear && bear > 0) return -1.0;
                            return 0.0;
                        })();

                        return {
                            close: findVal('Close') || findVal('C') || 0.0,
                            open: findVal('Open') || findVal('O') || 0.0,
                            high: findVal('High') || findVal('H') || 0.0,
                            low: findVal('Low') || findVal('L') || 0.0,
                            trend: parseTrend(),
                            mango_d1: findVal('MangoD1') || 0.0,
                            mango_d2: findVal('MangoD2') || 0.0,
                            entry_up: findVal('Entry Zone Upper') || 0.0,
                            entry_down: findVal('Entry Zone Lower') || 0.0,
                            mutanabby_sig: mutSig,
                            tk_cross: tkCross
                        };
                    })()""")

                    if plot_data and plot_data.get('close', 0) > 0:
                        scrape_row = {
                            'name': asset_name.upper(),
                            'timeframe': tf,
                            'close': plot_data['close'],
                            'open': plot_data['open'],
                            'high': plot_data['high'],
                            'low': plot_data['low'],
                            'trend': plot_data['trend'],
                            'mango_d1': plot_data['mango_d1'],
                            'mango_d2': plot_data['mango_d2'],
                            'entry_up': plot_data['entry_up'],
                            'entry_down': plot_data['entry_down'],
                            'mutanabby_sig': plot_data['mutanabby_sig'],
                            'tk_cross': plot_data['tk_cross'],
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                        if self.datastore:
                            try:
                                with self.datastore.get_connection() as conn:
                                    self.datastore.save_scrape(conn, scrape_row)
                            except Exception as dbe:
                                logger.warning(f"Error saving live scrape: {dbe}")
                                
                        scraped_data[tf] = scrape_row

            except Exception as e:
                logger.error(f"Error during targeted live scrape for {asset_name}: {e}")
            finally:
                await context.close()
                await browser.close()

        return scraped_data
