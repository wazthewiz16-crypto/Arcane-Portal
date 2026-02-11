"""TradingView Mango Dynamic scraper"""
import asyncio
import logging
from datetime import datetime
from playwright.async_api import async_playwright
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_FILE = "tv_state.json"

class TradingViewScraper:
    """Scrapes Mango Dynamic indicator data from TradingView"""
    
    def __init__(self, state_file=STATE_FILE):
        self.state_file = Path(state_file)
    
    async def scrape_asset(self, symbol, name, timeframe):
        """Scrape a single asset/timeframe"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=True,
                args=['--no-sandbox', '--disable-gpu']
            )
            
            if self.state_file.exists():
                context = await browser.new_context(
                    storage_state=str(self.state_file),
                    viewport={'width': 1920, 'height': 1080}
                )
            else:
                logger.error("tv_state.json not found!")
                return None
            
            page = await context.new_page()
            
            try:
                url = f"https://www.tradingview.com/chart/qR1XTue9/?symbol={symbol}"
                logger.info(f"Scraping {name} [{timeframe}]...")
                
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                await asyncio.sleep(8)
                
                # Ensure layout loaded
                has_mango = await page.evaluate("() => document.body.innerText.includes('Mango')")
                if not has_mango:
                    await page.keyboard.type(".")
                    await asyncio.sleep(1)
                    await page.keyboard.type("Arcane Portal")
                    await asyncio.sleep(1)
                    await page.keyboard.press("Enter")
                    await asyncio.sleep(8)
                
                # Ensure Data Window open
                is_dw = await page.evaluate("() => document.body.innerText.includes('Entry Zone Upper')")
                if not is_dw:
                    await page.keyboard.press("Alt+D")
                    await asyncio.sleep(2)
                
                # Map timeframe to TradingView format
                # TradingView uses: 1, 3, 5, 15, 30, 45 (minutes), 1H, 2H, 3H, 4H, D, W, M
                timeframe_map = {
                    "3m": "3",
                    "15m": "15",
                    "1h": "1H",
                    "4h": "4H",
                    "12h": "12H",
                    "1d": "D",
                    "4d": "4D"
                }
                
                tv_timeframe = timeframe_map.get(timeframe, timeframe)
                
                # Switch timeframe
                await page.keyboard.type(tv_timeframe)
                await page.keyboard.press("Enter")
                
                # Wait for timeframe to load (longer for daily/4D charts)
                if timeframe in ['1d', '4d']:
                    await asyncio.sleep(4)  # Daily charts need more time to load
                else:
                    await asyncio.sleep(2)
                
                # Hover current candle (with retry for 1D)
                max_retries = 3 if timeframe == '1d' else 1
                data = None
                
                for attempt in range(max_retries):
                    await page.mouse.move(1150, 400)
                    await asyncio.sleep(1 if timeframe in ['1d', '4d'] else 0.5)
                    
                    # Extract data
                    data = await page.evaluate(r"""(() => {
                    const res = { PlotValues: {}, Timestamp: new Date().toISOString() };
                    const txt = document.body.innerText;
                    
                    const findVal = (key, rawChar) => {
                        const safeKey = key.replace(/ /g, '[\\s\\n]+');
                        const re1 = new RegExp(safeKey + "[:\\s\\n]*([0-9,.]+)", "i");
                        let m = txt.match(re1);
                        if (m) return parseFloat(m[1].replace(/,/g, ''));
                        
                        if (rawChar) {
                            const re2 = new RegExp("\\b" + rawChar + "[:\\s]*([0-9,.]+)", "i");
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
                    
                    res.PlotValues = {
                        Open: findVal('Open', 'O'),
                        High: findVal('High', 'H'),
                        Low: findVal('Low', 'L'),
                        Close: findVal('Close', 'C'),
                        Volume: parseVol(),
                        D1: findVal('MangoD1'),
                        D2: findVal('MangoD2'),
                        EntryUp: findVal('Entry Zone Upper'),
                        EntryDown: findVal('Entry Zone Lower')
                    };
                    
                    return res;
                })()""")
                    
                    # Validate data (especially for 1D)
                    close_price = data['PlotValues'].get('Close')
                    
                    # Check if price is valid (not $1.00 or None)
                    if close_price and close_price > 5:  # Valid price
                        break  # Data is good, exit retry loop
                    elif attempt < max_retries - 1:
                        # Invalid data, retry
                        logger.warning(f"⚠️  {name} [{timeframe}] attempt {attempt + 1}: Invalid price ${close_price}, retrying...")
                        await asyncio.sleep(1)  # Wait before retry
                    else:
                        # Last attempt failed
                        logger.error(f"✗ {name} [{timeframe}]: Failed to get valid price after {max_retries} attempts")
                
                result = {
                    "symbol": symbol,
                    "name": name,
                    "timeframe": timeframe,
                    "timestamp": datetime.utcnow().isoformat(),
                    **data
                }
                
                logger.info(f"✓ {name} [{timeframe}] - Close: {data['PlotValues'].get('Close')}")
                return result
                
            except Exception as e:
                logger.error(f"✗ Error scraping {name} [{timeframe}]: {e}")
                return None
            finally:
                await page.close()
                await context.close()
                await browser.close()
    
    async def scrape_all_assets(self, assets, use_smart_scheduling=True):
        """Scrape all assets across configured timeframes (with optional smart scheduling)"""
        from scraper.scheduler import TimeframeScheduler
        
        results = []
        total_assets = len(assets)
        
        # Initialize scheduler if using smart scheduling
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
        
        for idx, asset in enumerate(assets, 1):
            logger.info(f"Scraping {idx}/{total_assets}: {asset['name']}")
            print(f"\n  [{idx}/{total_assets}] {asset['name']} - {asset['type'].upper()}")
            
            # Filter timeframes based on smart scheduling
            timeframes_for_asset = asset['timeframes']
            if use_smart_scheduling:
                timeframes_for_asset = [tf for tf in asset['timeframes'] if tf in timeframes_to_scrape]
            
            if not timeframes_for_asset:
                print(f"    ⏭️  No timeframes to scrape for this asset")
                continue
            
            # Scrape filtered timeframes for this asset
            for timeframe in timeframes_for_asset:
                data = await self.scrape_asset(asset["symbol"], asset["name"], timeframe)
                if data:
                    results.append(data)
                    self._print_timeframe_data(timeframe, data)
                else:
                    print(f"    ✗ {timeframe} failed (no data)")
            
            # Minimal delay between assets
            if idx < total_assets:
                await asyncio.sleep(0.5)
        
        logger.info(f"Scrape completed: {len(results)} timeframes")
        return results
    
    def _print_timeframe_data(self, timeframe, data):
        """Helper to print timeframe data"""
        price = data.get('PlotValues', {}).get('Close', 0)
        mango_d1 = data.get('PlotValues', {}).get('D1', 0)
        mango_d2 = data.get('PlotValues', {}).get('D2', 0)
        entry_up = data.get('PlotValues', {}).get('EntryUp', 0)
        entry_down = data.get('PlotValues', {}).get('EntryDown', 0)
        
        if price and mango_d2:
            # Determine trend (BULLISH, BEARISH, or NEUTRAL)
            if mango_d1 and mango_d2:
                if price > mango_d2:
                    trend = "BULLISH"
                elif price < mango_d1:
                    trend = "BEARISH"
                else:
                    trend = "NEUTRAL"
            else:
                trend = "UNKNOWN"
            
            in_zone = "YES" if (entry_down <= price <= entry_up) else "NO"
            
            print(f"    {timeframe:>3} | Price: ${price:>10,.2f} | Trend: {trend:>8} | In Bid Zone: {in_zone}")
            print(f"         Bid Zone: ${entry_down:,.2f} - ${entry_up:,.2f}")
        else:
            print(f"    ✗ {timeframe} failed (no data)")
