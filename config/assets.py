"""Asset configuration - Your 18 trading assets"""

ASSETS = [
    # Crypto (11 assets) - 24/7 trading - BYBIT PERPETUAL CONTRACTS
    # All timeframes: 4D, 1D, 12H, 4H, 1H, 15m, 3m
    {"symbol": "BYBIT:BTCUSDT.P", "name": "BTC", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:ETHUSDT.P", "name": "ETH", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:SOLUSDT.P", "name": "SOL", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:DOGEUSDT.P", "name": "DOGE", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:XRPUSDT.P", "name": "XRP", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:BNBUSDT.P", "name": "BNB", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:LINKUSDT.P", "name": "LINK", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:ARBUSDT.P", "name": "ARB", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:AVAXUSDT.P", "name": "AVAX", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:ADAUSDT.P", "name": "ADA", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "BYBIT:HYPEUSDT.P", "name": "HYPE", "type": "crypto", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    
    # TradFi / Indices (7 assets) - Monday-Friday only
    {"symbol": "OANDA:NAS100USD", "name": "NDX", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "OANDA:SPX500USD", "name": "SPX", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "OANDA:AU200AUD", "name": "AUS200", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "CAPITALCOM:DXY", "name": "DXY", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "OANDA:XAUUSD", "name": "GOLD", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "OANDA:WTICOUSD", "name": "OIL", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
    {"symbol": "OANDA:XAGUSD", "name": "SILVER", "type": "tradfi", "timeframes": ["4d", "1d", "12h", "4h", "1h", "15m", "3m"]},
]

def get_active_assets():
    """Return all enabled assets"""
    return ASSETS
