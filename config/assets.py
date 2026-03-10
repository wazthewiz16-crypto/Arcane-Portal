"""Asset configuration - Your 18 trading assets"""

ASSETS = [
    # Crypto (11 assets) - 24/7 trading - BYBIT PERPETUAL CONTRACTS
    # All timeframes: 4D, 1D, 12H, 4H, 1H, 15m
    {"symbol": "BYBIT:BTCUSDT.P", "name": "BTC", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:ETHUSDT.P", "name": "ETH", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:SOLUSDT.P", "name": "SOL", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:DOGEUSDT.P", "name": "DOGE", "type": "crypto", "precision": 4, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:XRPUSDT.P", "name": "XRP", "type": "crypto", "precision": 4, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:BNBUSDT.P", "name": "BNB", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:LINKUSDT.P", "name": "LINK", "type": "crypto", "precision": 3, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:ARBUSDT.P", "name": "ARB", "type": "crypto", "precision": 4, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:AVAXUSDT.P", "name": "AVAX", "type": "crypto", "precision": 3, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:ADAUSDT.P", "name": "ADA", "type": "crypto", "precision": 4, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "BYBIT:HYPEUSDT.P", "name": "HYPE", "type": "crypto", "precision": 4, "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    
    # TradFi / Indices (8 assets) - Monday-Friday only
    {"symbol": "OANDA:NAS100USD", "name": "NDX", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:SPX500USD", "name": "SPX", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:US30USD", "name": "US30", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:AU200AUD", "name": "AUS200", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "CAPITALCOM:DXY", "name": "DXY", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:XAUUSD", "name": "GOLD", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:WTICOUSD", "name": "OIL", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
    {"symbol": "OANDA:XAGUSD", "name": "SILVER", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m"]},
]

# Context-only assets: scraped for macro filters but never generate trade signals themselves.
# BTC.D tracks Bitcoin Dominance — essential for understanding altcoin direction.
CONTEXT_ASSETS = [
    {"symbol": "CRYPTOCAP:BTC.D", "name": "BTCD", "type": "context", "timeframes": ["4h", "1h"]},
]

def get_active_assets():
    """Return all enabled assets, filtering based on weekend rules.
    Context assets (e.g., BTC.D) are always included regardless of the day."""
    from datetime import datetime
    import pytz
    import copy
    
    # Check if it is the weekend (Saturday or Sunday)
    est = pytz.timezone('America/New_York')
    now = datetime.now(est)
    is_weekend = now.weekday() >= 5  # 5 = Saturday, 6 = Sunday
    
    active_assets = []
    
    for base_asset in ASSETS:
        # Deep copy so we don't accidentally mutate the global list
        asset = copy.deepcopy(base_asset)
        
        # 1. Skip TradFi completely on weekends (markets are closed)
        if is_weekend and asset.get('type') == 'tradfi':
            continue
            
        # 2. For Crypto on weekends, reduce timeframes to only 4H, 1H, and 15m 
        # (Saves ~50% compute cost per coin, while still allowing for 1H Swings and 15m Scalps)
        if is_weekend and asset.get('type') == 'crypto':
            asset['timeframes'] = [tf for tf in asset['timeframes'] if tf in ['4h', '1h', '15m']]
            
        active_assets.append(asset)
    
    # Always include context assets (weekday and weekend)
    for ctx_asset in CONTEXT_ASSETS:
        active_assets.append(copy.deepcopy(ctx_asset))
        
    return active_assets
