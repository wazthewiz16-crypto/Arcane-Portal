import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))
load_dotenv(override=True)

from scraper.mango_dashboard import MangoDashboardScraper
from detection.datastore import MangoDataStore

def main():
    mango = MangoDashboardScraper()
    datastore = MangoDataStore()
    
    print("Confluence Enabled:", mango.is_enabled())
    
    global_metrics = mango.get_global_metrics()
    print("\n--- Global Market Metrics ---")
    print(f"Market Trend: {global_metrics.get('market_trend')}")
    print(f"Market Volatility: {global_metrics.get('market_volatility')}")
    
    # Check strict mode settings
    strict_str = datastore.get_setting("MANGO_CONFLUENCE_STRICT")
    print(f"Strict Mode setting: {strict_str}")
    
    crypto_watchlist = ["BTC", "ETH", "SOL", "DOGE", "XRP", "BNB", "LINK", "ARB", "AVAX", "ADA", "HYPE", "TRX", "INJ", "ONDO", "NEAR"]
    
    print("\n--- Individual Asset Confluence Cached Details ---")
    for name in crypto_watchlist:
        confluence = mango.get_cached_confluence(name)
        if not confluence:
            print(f"{name}: NOT FOUND in dashboard cache")
            continue
            
        trend = confluence.get('trend')
        vol = confluence.get('volatility')
        flags = confluence.get('flags', [])
        tf_vols = confluence.get('timeframe_volatilities', {})
        
        print(f"{name}:")
        print(f"  Trend Badge: {trend}")
        print(f"  Volatility: {vol}")
        print(f"  TF Volatilities: {tf_vols}")
        print(f"  Flags: {flags}")

if __name__ == "__main__":
    main()
