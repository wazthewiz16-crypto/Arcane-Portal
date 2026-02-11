"""Background scraper scheduler"""
import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from config.assets import get_active_assets
from scraper.tradingview import TradingViewScraper
from detection.datastore import MangoDataStore

logger = logging.getLogger(__name__)

def run_scrape():
    """Run scraping job"""
    try:
        logger.info("🔄 Starting scheduled scrape...")
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        scraper = TradingViewScraper()
        assets = get_active_assets()
        
        results = loop.run_until_complete(scraper.scrape_all_assets(assets))
        
        datastore = MangoDataStore()
        datastore.save_scrapes(results)
        
        logger.info(f"✅ Scrape completed: {len(results)} records saved")
        
    except Exception as e:
        logger.error(f"❌ Scrape failed: {e}")
    finally:
        loop.close()

def start_background_scraper():
    """Start APScheduler in background"""
    scheduler = BackgroundScheduler()
    
    # Every 20 minutes
    scheduler.add_job(run_scrape, 'interval', minutes=20, id='scraper')
    
    # Run immediately on startup
    scheduler.add_job(run_scrape, 'date', id='startup_scrape')
    
    scheduler.start()
    logger.info("🚀 Background scraper started (every 20 min)")
