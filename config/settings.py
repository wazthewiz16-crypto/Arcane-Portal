"""Centralized configuration management"""
import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"
DATA_DIR.mkdir(exist_ok=True)

# Discord Configuration
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "")

# Database Configuration
DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR}/mango_scraper.db")

# Scraper Configuration
HEADLESS_BROWSER = os.getenv("HEADLESS_BROWSER", "true").lower() == "true"
TV_STATE_FILE = PROJECT_ROOT / "tv_state.json"

# Signal Confidence Thresholds (Optimized for win rate and accuracy)
MIN_CONFIDENCE_SWING = float(os.getenv("MIN_CONFIDENCE_SWING", "68"))
MIN_CONFIDENCE_SCALP = float(os.getenv("MIN_CONFIDENCE_SCALP", "72"))
MANGO_VOLATILITY_THRESHOLD = float(os.getenv("MANGO_VOLATILITY_THRESHOLD", "85"))

# Macro Trend & LTF Ribbon Alignment Filters
ALLOW_SWING_WEEKLY_MISMATCH = os.getenv("ALLOW_SWING_WEEKLY_MISMATCH", "true").lower() == "true"
ALLOW_SCALP_DAILY_MISMATCH = os.getenv("ALLOW_SCALP_DAILY_MISMATCH", "true").lower() == "true"
ALLOW_SCALP_WEEKLY_MISMATCH = os.getenv("ALLOW_SCALP_WEEKLY_MISMATCH", "true").lower() == "true"
STRICT_SCALP_LTF_ALIGNMENT = os.getenv("STRICT_SCALP_LTF_ALIGNMENT", "false").lower() == "true"

# Streamlit Configuration
STREAMLIT_SERVER_PORT = int(os.getenv("STREAMLIT_SERVER_PORT", "8501"))

# Scraping Intervals (in minutes)
SCRAPE_INTERVALS = {
    "3m": 3,
    "5m": 5,
    "15m": 15,
    "30m": 30,
    "1h": 60,
    "4h": 240,
    "12h": 720,
    "1d": 1440,
    "2d": 2880,
    "4d": 5760,
    "1w": 10080
}

# TradingView Layouts (Per-Timeframe Settings Support)
# Allows using different saved layouts (with different indicator settings) per timeframe
LAYOUTS = {
    "default": os.getenv("TRADINGVIEW_LAYOUT_ID", ""),
    "1w": os.getenv("TRADINGVIEW_LAYOUT_1W", ""),
    "4d": os.getenv("TRADINGVIEW_LAYOUT_4D", ""),
    "2d": os.getenv("TRADINGVIEW_LAYOUT_2D", ""),
    "1d": os.getenv("TRADINGVIEW_LAYOUT_1D", ""),
    "12h": os.getenv("TRADINGVIEW_LAYOUT_12H", ""),
    "4h": os.getenv("TRADINGVIEW_LAYOUT_4H", ""),
    "1h": os.getenv("TRADINGVIEW_LAYOUT_1H", ""),
    "30m": os.getenv("TRADINGVIEW_LAYOUT_30M", ""),
    "15m": os.getenv("TRADINGVIEW_LAYOUT_15M", ""),
    "5m": os.getenv("TRADINGVIEW_LAYOUT_5M", ""),
    "3m": os.getenv("TRADINGVIEW_LAYOUT_3M", "")
}

def validate_config():
    """Validate required configuration"""
    errors = []
    
    if not TV_STATE_FILE.exists():
        errors.append(f"TradingView state file not found: {TV_STATE_FILE}")
    
    if not DISCORD_WEBHOOK_URL:
        errors.append("DISCORD_WEBHOOK_URL not set in environment")
    
    if errors:
        raise ValueError(f"Configuration errors:\n" + "\n".join(f"  - {e}" for e in errors))
    
    return True
