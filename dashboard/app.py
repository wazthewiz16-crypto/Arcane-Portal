"""Arcane Portal V2 - Streamlit Dashboard"""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import time
from detection.datastore import MangoDataStore
from detection.signals import MangoSignalDetector
from config.assets import get_active_assets
from utils.logger import setup_logger

# Setup logging
logger = setup_logger(__name__)

# Page configuration
st.set_page_config(
    page_title="Arcane Portal V2",
    page_icon="🔮",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS for styling
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        font-weight: bold;
        text-align: center;
        background: linear-gradient(90deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 1rem;
    }
    .signal-card {
        padding: 1.5rem;
        border-radius: 10px;
        margin-bottom: 1rem;
        border-left: 5px solid;
    }
    .signal-long {
        border-left-color: #00ff00;
        background-color: rgba(0, 255, 0, 0.05);
    }
    .signal-short {
        border-left-color: #ff0000;
        background-color: rgba(255, 0, 0, 0.05);
    }
    .metric-card {
        background-color: #f0f2f6;
        padding: 1rem;
        border-radius: 8px;
        text-align: center;
    }
    .stButton>button {
        width: 100%;
    }
</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'last_refresh' not in st.session_state:
    st.session_state.last_refresh = datetime.now()
if 'auto_refresh' not in st.session_state:
    st.session_state.auto_refresh = True

def render_header():
    """Render dashboard header"""
    import pytz
    
    st.markdown('<h1 class="main-header">🔮 Arcane Portal V2</h1>', unsafe_allow_html=True)
    st.markdown("**Mango Dynamic Trading Signals** • Real-time signal detection and analysis")
    
    # Last update time (Convert to EST)
    est = pytz.timezone('America/New_York')
    utc = pytz.utc
    
    last_refresh = st.session_state.last_refresh
    # Handle naive datetime (assume UTC if server time)
    if last_refresh.tzinfo is None:
        last_refresh = utc.localize(last_refresh)
    
    est_time = last_refresh.astimezone(est)
    
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        st.caption(f"Last updated: {est_time.strftime('%Y-%m-%d %I:%M:%S %p')} EST")
    with col2:
        if st.button("🔄 Refresh Now"):
            st.session_state.last_refresh = datetime.now()
            st.rerun()
    with col3:
        st.session_state.auto_refresh = st.checkbox("Auto-refresh (60s)", value=st.session_state.auto_refresh, key="auto_refresh_cb")

def render_active_signals():
    """Render active trading signals"""
    st.header("🚨 Active Signals")
    
    # Get signals
    datastore = MangoDataStore()
    detector = MangoSignalDetector(datastore)
    
    try:
        signals = detector.get_all_signals()
        
        if not signals:
            st.info("No active signals at the moment. Waiting for setups...")
            return
        
        # Filter options
        col1, col2, col3 = st.columns(3)
        with col1:
            signal_type_filter = st.selectbox(
                "Signal Type",
                ["All", "Swing", "Scalp"],
                key="signal_type_filter"
            )
        with col2:
            direction_filter = st.selectbox(
                "Direction",
                ["All", "Long", "Short"],
                key="direction_filter"
            )
        with col3:
            asset_type_filter = st.selectbox(
                "Asset Type",
                ["All", "Crypto", "TradFi"],
                key="asset_type_filter"
            )
        
        # Apply filters
        filtered_signals = signals
        if signal_type_filter != "All":
            filtered_signals = [s for s in filtered_signals if signal_type_filter.upper() in s['signal_type']]
        if direction_filter != "All":
            filtered_signals = [s for s in filtered_signals if direction_filter.upper() in s['signal_type']]
        if asset_type_filter != "All":
            filtered_signals = [s for s in filtered_signals if s['asset_type'] == asset_type_filter.lower()]
        
        st.caption(f"Showing {len(filtered_signals)} of {len(signals)} signals")
        
        # Display signals in cards
        for signal in filtered_signals:
            render_signal_card(signal)
            
    except Exception as e:
        st.error(f"Error loading signals: {e}")
        logger.error(f"Error in render_active_signals: {e}")

def render_signal_card(signal):
    """Render individual signal card"""
    from datetime import datetime
    import pytz
    
    # Determine card style
    is_long = 'LONG' in signal['signal_type']
    card_class = "signal-long" if is_long else "signal-short"
    
    # Signal type emoji
    if 'SWING' in signal['signal_type']:
        type_emoji = "🎯"
    else:
        type_emoji = "⚡"
    
    direction_emoji = "📈" if is_long else "📉"
    
    # Convert entry time to EST
    entry_time_utc = datetime.fromisoformat(signal['entry_time'].replace('Z', '+00:00'))
    est = pytz.timezone('America/New_York')
    entry_time_est = entry_time_utc.astimezone(est)
    
    # Determine decimal precision based on price
    entry_price = signal['entry_price']
    if entry_price < 1:
        decimals = 4  # Low price assets (ADA, etc.)
    elif entry_price < 100:
        decimals = 3  # Medium price assets (LINK, etc.)
    else:
        decimals = 2  # High price assets (BTC, ETH, etc.)
    
    with st.container():
        col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
        
        with col1:
            st.markdown(f"### {type_emoji} {signal['asset_name']}")
            st.caption(f"{signal['signal_type'].replace('_', ' ')}")
            st.caption(f"⏰ {entry_time_est.strftime('%Y-%m-%d %I:%M %p EST')}")
        
        with col2:
            st.metric("Entry Price", f"${signal['entry_price']:.{decimals}f}")
            st.caption(f"Timeframes: {signal['htf']} → {signal['ltf']}")
        
        with col3:
            st.metric("Take Profit", f"${signal['take_profit']:.{decimals}f}", delta=f"+{((signal['take_profit'] - signal['entry_price']) / signal['entry_price'] * 100):.1f}%")
            st.metric("Stop Loss", f"${signal['stop_loss']:.{decimals}f}", delta=f"{((signal['stop_loss'] - signal['entry_price']) / signal['entry_price'] * 100):.1f}%")
        
        with col4:
            # Confidence gauge
            confidence = signal['confidence']
            if confidence >= 75:
                conf_color = "🟢"
            elif confidence >= 50:
                conf_color = "🟡"
            else:
                conf_color = "🟠"
            
            st.metric("Confidence", f"{confidence:.0f}%")
            st.caption(f"RR: {signal['rr_ratio']:.1f}:1")
        
        st.divider()

def render_signal_history():
    """Render signal history table"""
    st.header("📊 Signal History")
    
    # Time range selector
    col1, col2 = st.columns([1, 3])
    with col1:
        hours = st.selectbox("Time Range", [6, 12, 24, 48, 72], index=2, key="history_hours")
    
    datastore = MangoDataStore()
    
    try:
        history = datastore.get_signal_history(hours=hours)
        
        if not history:
            st.info(f"No signals in the last {hours} hours")
            return
        
        # Convert to DataFrame
        df = pd.DataFrame(history)
        
        # Format entry_time with better error handling
        import pytz
        from datetime import datetime
        
        def format_entry_time(time_str):
            """Convert entry_time to EST formatted string"""
            try:
                # Try parsing as ISO format
                dt = pd.to_datetime(time_str, format='mixed', utc=True)
                # Convert to EST
                est = pytz.timezone('America/New_York')
                dt_est = dt.tz_convert(est)
                return dt_est.strftime('%Y-%m-%d %I:%M %p')
            except:
                # Fallback: return as-is if parsing fails
                return str(time_str)
        
        df['entry_time'] = df['entry_time'].apply(format_entry_time)
        df['confidence'] = df['confidence'].round(0).astype(int)
        
        # Select and rename columns for display
        display_df = df[[
            'entry_time', 'asset_name', 'signal_type', 'confidence',
            'entry_price', 'take_profit', 'stop_loss', 'rr_ratio', 'status'
        ]].copy()
        
        display_df.columns = [
            'Time', 'Asset', 'Type', 'Conf%',
            'Entry', 'TP', 'SL', 'RR', 'Status'
        ]
        
        # Display table
        st.dataframe(
            display_df,
            use_container_width=True,
            hide_index=True
        )
        
        # Summary stats
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Total Signals", len(df))
        with col2:
            active_count = len(df[df['status'] == 'ACTIVE'])
            st.metric("Active", active_count)
        with col3:
            avg_confidence = df['confidence'].mean()
            st.metric("Avg Confidence", f"{avg_confidence:.0f}%")
        with col4:
            avg_rr = df['rr_ratio'].mean()
            st.metric("Avg RR", f"{avg_rr:.1f}:1")
            
    except Exception as e:
        st.error(f"Error loading history: {e}")
        logger.error(f"Error in render_signal_history: {e}")
        import traceback
        st.code(traceback.format_exc())

def render_asset_monitor():
    """Render asset monitoring section"""
    st.header("👁️ Asset Monitor")
    
    assets = get_active_assets()
    datastore = MangoDataStore()
    
    try:
        latest_data = datastore.get_latest_for_all_assets()
        
        # Group by asset
        asset_data = {}
        for row in latest_data:
            name = row['name']
            if name not in asset_data:
                asset_data[name] = {'htf': None, 'ltf': None}
            
            if row['tf_type'] == 'htf':
                asset_data[name]['htf'] = row
            else:
                asset_data[name]['ltf'] = row
        
        # Display in grid
        cols = st.columns(3)
        for idx, asset in enumerate(assets):
            name = asset['name']
            data = asset_data.get(name, {})
            
            with cols[idx % 3]:
                with st.container():
                    st.subheader(f"{name}")
                    htf_tf = data.get('htf', {}).get('timeframe', 'HTF') if data.get('htf') else 'HTF'
                    ltf_tf = data.get('ltf', {}).get('timeframe', 'LTF') if data.get('ltf') else 'LTF'
                    st.caption(f"{asset['type'].upper()} • {htf_tf}/{ltf_tf}")
                    
                    if data.get('ltf'):
                        ltf = data['ltf']
                        precision = asset.get('precision', 2)
                        st.metric("Price", f"${ltf.get('close', 0):,.{precision}f}")
                        
                        # Show if in entry zone
                        if ltf.get('entry_up') and ltf.get('entry_down'):
                            price = ltf.get('close', 0)
                            in_zone = ltf['entry_down'] <= price <= ltf['entry_up']
                            if in_zone:
                                st.success("✅ In Entry Zone")
                            else:
                                st.caption("Waiting for pullback")
                    else:
                        st.caption("No data available")
                    
                    st.divider()
                    
    except Exception as e:
        st.error(f"Error loading asset data: {e}")
        logger.error(f"Error in render_asset_monitor: {e}")

def render_system_health():
    """Render system health section"""
    with st.sidebar:
        st.header("⚙️ System Health")
        
        datastore = MangoDataStore()
        
        try:
            # Check database
            latest = datastore.get_latest_for_all_assets()
            if latest:
                last_scrape = latest[0]['timestamp']
                last_scrape_dt = datetime.fromisoformat(last_scrape.replace('Z', '+00:00'))
                time_since = datetime.now() - last_scrape_dt.replace(tzinfo=None)
                
                if time_since.total_seconds() < 1800:  # 30 minutes
                    st.success("✅ Scraper Active")
                else:
                    st.warning("⚠️ Scraper Delayed")
                
                st.caption(f"Last scrape: {time_since.seconds // 60}m ago")
            else:
                st.error("❌ No data")
            
            # Asset count
            assets = get_active_assets()
            st.metric("Tracked Assets", len(assets))
            
            # Signal count
            signals = datastore.get_active_signals()
            st.metric("Active Signals", len(signals))
            
        except Exception as e:
            st.error(f"Health check failed: {e}")

def main():
    """Main dashboard function"""
    # Render header
    render_header()
    
    # Render system health in sidebar
    render_system_health()
    
    # Main content tabs
    tab1, tab2, tab3 = st.tabs(["🚨 Active Signals", "📊 History", "👁️ Assets"])
    
    with tab1:
        render_active_signals()
    
    with tab2:
        render_signal_history()
    
    with tab3:
        render_asset_monitor()
    
    # Auto-refresh
    if st.session_state.auto_refresh:
        time.sleep(60)
        st.session_state.last_refresh = datetime.now()
        st.rerun()

if __name__ == "__main__":
    main()